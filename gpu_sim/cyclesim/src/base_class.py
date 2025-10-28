#!/usr/bin/env python3


from __future__ import annotations

import argparse
import logging
import struct
import sys
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional
from unicodedata import name
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class tb_data_params:
	gridX_dim: int
	gridY_dim: int
	gridZ_dim: int
	blockX_dim: int
	blockY_dim: int
	blockZ_dim: int

from dataclasses import dataclass, field
from typing import Optional, Any, List, Dict

@dataclass
class FunctionalUnitBase:
    """
    Base class for all functional units (FUs) that can exchange data
    via StageInterface objects and operate in parallel.
    """
    name: str
    latency: int = 1
    busy: bool = False
    current_op: Optional[dict] = None
    remaining_latency: int = 0
    output: Optional[Any] = None

    # IO connections
    inputs: List[Any] = field(default_factory=list)
    outputs: List[Any] = field(default_factory=list)
    feedback_links: Dict[str, Any] = field(default_factory=dict)
    parent_stage: Optional[Any] = field(default=None, repr=False)

    def add_input(self, iface):
        self.inputs.append(iface)

    def add_output(self, iface):
        self.outputs.append(iface)

    def add_feedback(self, name: str, iface):
        self.feedback_links[name] = iface

    # =====================================================
    # Core Lifecycle
    # =====================================================

    def accept(self, op: dict) -> bool:
        """Accept a new operation if not busy."""
        if self.busy:
            return False
        self.current_op = op
        self.busy = True
        self.remaining_latency = self.latency
        print(f"[{self.name}] Accepted op: {op}")
        return True

    def tick(self):
        """Advance by one cycle."""
        # Receive new data from input interfaces
        for inp in self.inputs:
            data = inp.receive()
            if data and not self.busy:
                self.accept(data)

        if self.busy:
            if self.remaining_latency > 0:
                self.remaining_latency -= 1
                print(f"[{self.name}] ticking... ({self.remaining_latency} cycles left)")

            if self.remaining_latency == 0:
                result = self.process(self.current_op)
                self.output = result
                self.busy = False
                self.current_op = None

                # Send output downstream
                for out in self.outputs:
                    if out.can_accept():
                        out.send(result)
                        print(f"[{self.name}] → sent result {result}")
                    else:
                        print(f"[{self.name}] Output stalled.")

    def process(self, op: dict) -> Any:
        """Override this method in subclasses."""
        raise NotImplementedError(f"{self.__class__.__name__}.process() not implemented.")

    def get_output(self):
        out = self.output
        self.output = None
        return out

@dataclass
class StageInterface:
    """Handshake data path between two pipeline stages."""
    def __init__(self, name, latency=1, is_feedback=False):
        self.name = name
        self.latency = latency
        self.is_feedback = is_feedback  # control feedback paths bypass tick
        self.data = None
        self.next_data = None
        self.valid = False
        self.next_valid = False
        self.ready = True
        self.stall = False
        self.remaining_latency = 0

    def send(self, data):
        if not self.ready:
            self.stall = True
            return False
        self.next_data = data
        self.next_valid = True
        if not self.is_feedback:
            self.remaining_latency = self.latency
        else:
            # Feedback bypasses delay
            self.data = data
            self.valid = True
        return True

    def receive(self):
        if self.is_feedback:
            # Control paths behave as combinational connections
            return self.data if self.valid else None

        if self.valid and self.remaining_latency <= 0:
            d = self.data
            self.data = None
            self.valid = False
            self.ready = True
            return d
        return None

    def flush(self):
        self.data = None
        self.next_data = None
        self.valid = self.next_valid = False
        self.remaining_latency = 0
        self.ready = True
        self.stall = False

    def tick(self):
        if self.is_feedback:
            return  # bypass pipeline timing

        if self.remaining_latency > 0:
            self.remaining_latency -= 1
        if self.next_valid:
            self.data = self.next_data
            self.valid = True
            self.ready = False
        elif not self.valid:
            self.ready = True
        self.next_data = None
        self.next_valid = False
        self.stall = False

    def can_accept(self):
        if self.is_feedback:
            return True
        return bool(self.ready and not self.next_valid and self.remaining_latency <= 0)


class LoggerBase:
    """Minimal logger base class used by SM and stages.

    Features:
    - Configurable python logging.Logger backend
    - In-memory ring buffer of recent log records (for quick inspection)
    - Thread-safe API
    """

    def __init__(self, name: str = "SoCET", level: int = logging.INFO, buffer_size: int = 1024):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        if not self._logger.handlers:
            # default handler to stdout
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
            self._logger.addHandler(ch)

        self._buf_size = buffer_size
        self._buffer = []  # list of (ts, levelname, msg)
        self._lock = threading.Lock()

    def _record(self, level: int, msg: str):
        with self._lock:
            ts = time.time()
            entry = (ts, logging.getLevelName(level), msg)
            self._buffer.append(entry)
            if len(self._buffer) > self._buf_size:
                # simple ring behavior
                self._buffer.pop(0)
        self._logger.log(level, msg)

    def info(self, msg: str):
        self._record(logging.INFO, msg)

    def debug(self, msg: str):
        self._record(logging.DEBUG, msg)

    def warning(self, msg: str):
        self._record(logging.WARNING, msg)

    def error(self, msg: str):
        self._record(logging.ERROR, msg)

    def get_buffer(self):
        with self._lock:
            return list(self._buffer)


class PerfCounterBase:
    """Simple performance counter base for cycle-level metrics.

    API:
    - tick(n=1): advance cycles and update cycle counter
    - incr(name, amount=1): increment arbitrary counter
    - set(name, value): set gauge
    - snapshot(): return a shallow copy of counters
    - reset(): clear counters
    Thread-safe.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.cycle = 0
        self.counters = defaultdict(int)  # event counters
        self.gauges = {}  # named gauges

    def tick(self, n: int = 1):
        with self._lock:
            self.cycle += n
            self.counters["cycles"] += n

    def incr(self, name: str, amount: int = 1):
        with self._lock:
            self.counters[name] += amount

    def set_gauge(self, name: str, value):
        with self._lock:
            self.gauges[name] = value

    def snapshot(self) -> dict:
        with self._lock:
            return {"cycle": self.cycle, "counters": dict(self.counters), "gauges": dict(self.gauges)}

    def reset(self):
        with self._lock:
            self.cycle = 0
            self.counters.clear()
            self.gauges.clear()
    
@dataclass
class SoCET_GPU():
	"""A minimal base class used for demos and tests.

	Attributes:
		name: The name to process.
		times: How many times to repeat the greeting.
	"""

	def __init__(self, name: str = "World", times: int = 1):
		self.name = "SoCET GPU"
		self.semester = "F25"
		self.version = "0.1.0"

@dataclass
class SM:
    def __init__(self, stage_defs=None, connections=None, feedbacks=None, logger: Optional[LoggerBase]=None, perf: Optional[PerfCounterBase]=None):
        # 1. Define stages (can be overridden)
        if stage_defs is not None:
            stages = dict(stage_defs)
        else:
            stages = {
                "warp_scheduler": PipelineStage("WarpScheduler", self),
                "fetch": PipelineStage("Fetch", self),
                "decode": PipelineStage("Decode", self),
                "execute": PipelineStage("Execute", self),
                "writeback": PipelineStage("Writeback", self),
            }
        self.stages = stages
        self.interfaces = []

        # 2. Build normal pipeline / parallel connections
        if connections is not None:
            pipeline_connections = connections
        else:
            pipeline_connections = [
                ("warp_scheduler", "fetch"),
                ("fetch", "decode"),
                ("decode", "execute"),
                ("execute", "writeback"),
            ]
        for src, dst in pipeline_connections:
            iface = StageInterface(f"if_{src}_{dst}", latency=1)
            stages[src].add_output(iface)
            stages[dst].add_input(iface)
            stages[src].output_if = iface
            stages[dst].input_if = iface
            print(f"Made: if_{src}_{dst}")
            self.interfaces.append(iface)

        # 3. Build control feedback connections (non-pipelined)
        feedbacks = feedbacks or []
        for src, dst in feedbacks:
            fb = StageInterface(f"FB_{src}_{dst}", is_feedback=True)
            stages[src].add_feedback(dst, fb)
            stages[dst].add_feedback(src, fb)

        self.global_cycle = 0
        # Attach logger and perf counters (create defaults if none supplied)
        self.logger = logger if logger is not None else LoggerBase(name="SM")
        self.perf = perf if perf is not None else PerfCounterBase()

    def get_interface(self, name):
        return next((iface for iface in self.interfaces if iface.name == name), None)
    
    def push_instruction(self, inst, at_stage: str = "if_user_fetch"):
        """
        Inject an instruction or data payload into any pipeline stage or interface.

        Parameters
        ----------
        inst : dict
            The instruction or payload to inject.
        at_stage : str
            Target injection point. Can be a stage name ("fetch", "decode", etc.)
            or a pipeline interface name ("if_user_fetch", "if_fetch_decode", etc.).
        """
        target_if = None

        # --- Case 1: Direct interface name (e.g., "if_user_fetch", "if_fetch_decode")
        if at_stage.startswith("if_"):
            target_if = self.get_interface(at_stage)
            if not target_if:
                print(f"[SM] No interface named '{at_stage}' found.")
                return False

        # --- Case 2: Stage name (inject into first input)
        else:
            stage = self.stages.get(at_stage)
            if not stage:
                print(f"[SM] No stage named '{at_stage}' found.")
                return False

            if stage.inputs:
                target_if = stage.inputs[0]
            else:
                print(f"[SM] Stage '{at_stage}' has no input interfaces.")
                return False

        # --- Perform send if ready
        if target_if.can_accept():
            print(f"[SM] Injecting into {target_if.name}: {inst}")
            target_if.send(inst)
            return True
        else:
            print(f"[SM] Interface {target_if.name} not ready (stall).")
            return False

    # def push_instruction(self, inst):
    #     target_if = None
    #     fetch = self.stages.get("fetch")
    #     if fetch and fetch.outputs and fetch.outputs[0].can_accept():
    #         print(f"[SM] Pushing instruction to fetch stage: {inst}")
    #         fetch.outputs[0].send(inst)

    def cycle(self):
        self.global_cycle += 1
        self.perf.tick(1)
        self.perf.set_gauge("global_cycle", self.global_cycle)


        # === PHASE 1: Commit all interface values (clock edge)
        for iface in self.interfaces:
            iface.tick()


        # === PHASE 1: Evaluate stages (back-to-front prevents overwrite)
        for stage in reversed(self.stages.values()):
            stage.tick_internal()
            stage.cycle()

        self.logger.debug(f"Completed cycle {self.global_cycle}")

    def print_pipeline_state(self):
        print(f"\n=== Cycle {self.global_cycle} ===")
        for name, stage in self.stages.items():
            inst = stage.debug_state().get("current_inst", None)
            print(f"{name:>10}: {inst if inst else '-'}")
        print("\n")

@dataclass
class TB_Scheduler:
	def __init__(self):
		self.num_threads = 32
		self.gridX_dim = 32
		# tb_data_params expects (gridX_dim, gridY_dim, gridZ_dim, blockX_dim, blockY_dim, blockZ_dim)
		self.data_params_struct = tb_data_params(
			gridX_dim=32,
			gridY_dim=32,
			gridZ_dim=1,
			blockX_dim=32,
			blockY_dim=32,
			blockZ_dim=1,
		)
		self.data_address = 0x000

@dataclass
class PipelineStage:
    name: str
    parent_core: object

    inputs: list[StageInterface] = field(default_factory=list)
    outputs: list[StageInterface] = field(default_factory=list)
    feedback_links: dict = field(default_factory=dict)
    subunits: list = field(default_factory=list)

    cycle_count: int = 0
    active_cycles: int = 0
    stall_cycles: int = 0
    instruction_count: int = 0

    def add_input(self, interface: StageInterface):
        self.inputs.append(interface)

    def add_output(self, interface: StageInterface):
        self.outputs.append(interface)
    
    def connect_interfaces(self, input_if: "StageInterface", output_if: "StageInterface"):
        self.add_input(input_if)
        self.add_output(output_if)

    def add_feedback(self, name: str, interface: StageInterface):
        """Add a non-pipelined feedback signal."""
        self.feedback_links[name] = interface

    def add_subunit(self, fu):
        self.subunits.append(fu)

    def process(self, inst):
        """Process an instruction; to be overridden by subclasses."""
        self.current_inst = inst
        return inst
    
    def tick_internal(self):
        """
        Advance all subunits (functional units) and automatically handle their outputs.
        This makes every FU behave consistently w.r.t. clocking and result propagation.
        """
        for fu in self.subunits:
            if hasattr(fu, "tick"):
                fu.tick()

                # Automatically retrieve results if FU completed this cycle
                result = None
                if hasattr(fu, "get_output"):
                    result = fu.get_output()

                if result is not None:
                    # Forward to next stage (default first output)
                    if self.outputs:
                        sent = False
                        for out in self.outputs:
                            if out.can_accept():
                                out.send(result)
                                sent = True
                                print(f"[{self.name}] auto-forwarded result from {fu.name}: {result}")
                                break
                        if not sent:
                            print(f"[{self.name}] Output stalled for result from {fu.name}")
                            self.stall_cycles += 1

                    # Send feedbacks automatically (if FU defines ihit, etc.)
                    if hasattr(self, "feedback_links"):
                        for fb_name, fb_if in self.feedback_links.items():
                            if fb_if.is_feedback:
                                fb_if.send(result)
                                print(f"[{self.name}] Sent feedback {fb_name} from {fu.name}: {result}")


    def cycle(self):
        """Advance one cycle; handle multiple input/output interfaces."""
        self.cycle_count += 1
        received = None

        # Try to receive from any valid input (simple priority arbiter)
        for inp in self.inputs:
            data = inp.receive()
            if data:
                received = data
                break

        if received:
            result = self.process(received)

            self.current_inst = result if result is not None else received
            if result is not None:
                print(f"[{self.name}] Outputting result: {result}")
                if isinstance(result, tuple):
                    data, out_idx = result
                    print("Info: ", format(data))
                    if self.outputs[out_idx].can_accept():
                        self.outputs[out_idx].send(data)
                    else:
                        self.stall_cycles += 1
                else:
                    if self.outputs and self.outputs[0].can_accept():
                        self.outputs[0].send(result)
                    else:
                        self.stall_cycles += 1
        else:
            self.stall_cycles += 1
            self.current_inst = None

    def debug_state(self):
        # Show a summary of the current instruction (e.g., PC or mnemonic)
        inst_info = None
        if hasattr(self, 'current_inst') and self.current_inst is not None:
            inst = self.current_inst
            if isinstance(inst, dict):
                if 'pc' in inst:
                    inst_info = inst['pc']
                elif 'decoded_fields' in inst and 'orig_inst' in inst['decoded_fields'] and 'pc' in inst['decoded_fields']['orig_inst']:
                    inst_info = f"pc=0x{inst['decoded_fields']['orig_inst']['pc']:x}"
                else:
                    inst_info = str(inst)
            else:
                inst_info = str(inst)
        return {
            "name": self.name,
            "cycle_count": self.cycle_count,
            "active_cycles": self.active_cycles,
            "stall_cycles": self.stall_cycles,
            "instruction_count": self.instruction_count,
            "current_inst": inst_info,
        }
       