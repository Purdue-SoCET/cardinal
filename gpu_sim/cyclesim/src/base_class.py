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

import csv
from collections import defaultdict

class PerfDomain:
    """
    Hierarchical performance counter.
    Each stage or functional unit can own one and propagate updates upward.
    """
    def __init__(self, name, parent=None, dump_interval=100, csv_path=None):
        self.name = name
        self.parent = parent
        self.dump_interval = dump_interval
        self.counters = defaultdict(int)
        self.derived = {}
        self.cycle = 0
        self.csv_path = csv_path or f"{name}_perf.csv"
        self._csv_initialized = False

    # ------------------ Core API ------------------
    def tick(self, n=1):
        self.cycle += n
        self.incr("cycles", n)
        if self.cycle % self.dump_interval == 0:
            self.dump_to_csv()

    def incr(self, name, amount=1):
        self.counters[name] += amount
        if self.parent:
            self.parent.incr(f"{self.name}.{name}", amount)

    def set(self, name, value):
        self.counters[name] = value

    def derive(self, name, func):
        """Register a derived metric: func(counters)->float."""
        self.derived[name] = func

    def compute_derived(self):
        return {n: f(self.counters) for n, f in self.derived.items()}

    def snapshot(self):
        return dict(self.counters)
    
    def set_gauge(self, name, value):
        self.set(name, value)
    # ------------------ CSV Dump ------------------
    def _init_csv(self):
        with open(self.csv_path, "w", newline="") as f:
            csv.writer(f).writerow(["cycle", "metric", "value"])
        self._csv_initialized = True

    def dump_to_csv(self):
        if not self._csv_initialized:
            self._init_csv()
        with open(self.csv_path, "a", newline="") as f:
            w = csv.writer(f)
            for k, v in self.counters.items():
                w.writerow([self.cycle, k, v])


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
class LatchInterface:
    """
    Generalized handshake latch with wait-based backpressure.
    Handles valid/ready signaling and optional latency internally.
    """
    name: str
    latency: int = 1
    is_feedback: bool = False

    def __post_init__(self):
        self.data: Optional[Any] = None
        self.next_data: Optional[Any] = None
        self.valid: bool = False
        self.next_valid: bool = False

        # Downstream backpressure
        self.wait: int = 0
        self.next_wait: int = 0

        # Pipeline timing
        self.remaining_latency: int = 0

    # -------------------------------
    # Upstream interface
    # -------------------------------
    def send(self, data: Any) -> bool:
        """
        Upstream stage attempts to send data.
        Returns True if accepted, False if stalled due to wait/backpressure.
        """
        if not self.can_accept():
            return False

        self.next_data = data
        self.next_valid = True
        self.remaining_latency = self.latency if not self.is_feedback else 0
        return True

    def can_accept(self) -> bool:
        """Returns True if latch can accept new data."""
        if self.is_feedback:
            return True
        return (self.wait == 0) and (not self.valid) and (self.remaining_latency <= 0)

    # -------------------------------
    # Downstream interface
    # -------------------------------
    def receive(self) -> Optional[Any]:
        """
        Downstream tries to read data from latch.
        Only succeeds if wait == 0 and data is valid.
        """
        if self.is_feedback:
            return self.data if self.valid else None

        if self.valid and self.wait == 0 and self.remaining_latency <= 0:
            d = self.data
            self.valid = False
            self.data = None
            return d
        return None

    def set_wait(self, cycles: int):
        """Downstream sets wait cycles (backpressure)."""
        self.next_wait = cycles

    # -------------------------------
    # Simulation control
    # -------------------------------
    def tick(self):
        """Advance one simulation cycle (clock edge)."""
        # Handle wait countdown
        self.wait = max(0, self.next_wait - 1)
        self.next_wait = self.wait  # keep steady if not reset

        if self.remaining_latency > 0:
            self.remaining_latency -= 1

        # Commit new data when latency resolves
        if self.next_valid:
            self.data = self.next_data
            self.valid = True
        self.next_data = None
        self.next_valid = False

    def flush(self):
        """Clear latch state."""
        self.data = None
        self.next_data = None
        self.valid = False
        self.next_valid = False
        self.wait = 0
        self.next_wait = 0
        self.remaining_latency = 0

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

from dataclasses import dataclass
from typing import Optional
from collections import OrderedDict

# assume we already have:
# - LatchInterface (the new version with wait/valid)
# - PipelineStage or StageBase (stages that use .compute(), .execute(), etc.)
# - LoggerBase, PerfDomain classes


@dataclass
class SM:
    """
    Streaming Multiprocessor model with latch-based handshake interfaces
    replacing legacy StageInterface connections.
    """
    def __init__(self,
                stage_defs=None,
                connections=None,
                feedbacks=None,
                logger: Optional["LoggerBase"] = None,
                perf: Optional["PerfDomain"] = None):

        # === 0. Initialize logging + perf BEFORE building stages ===
        self.global_cycle = 0
        self.logger = logger if logger else LoggerBase(name="SM")
        self.perf = perf if perf else PerfDomain(name="SM_Global")

        # Derived metrics
        self.perf.derive("IPC", lambda c: c.get("instructions", 0) / max(c.get("cycles", 1), 1))
        self.perf.derive("StallRatio", lambda c: c.get("stall_cycles", 0) / max(c.get("cycles", 1), 1))

        # === 1. Define stages ===
        if stage_defs is not None:
            self.stages = dict(stage_defs)
        else:
            self.stages = OrderedDict({
                "warp_scheduler": PipelineStage("WarpScheduler", self),
                "fetch": PipelineStage("Fetch", self),
                "decode": PipelineStage("Decode", self),
                "execute": PipelineStage("Execute", self),
                "writeback": PipelineStage("Writeback", self),
            })

        self.interfaces: list[LatchInterface] = []

        # === 2. Build pipeline connections ===
        pipeline_connections = connections or [
            ("warp_scheduler", "fetch"),
            ("fetch", "decode"),
            ("decode", "execute"),
            ("execute", "writeback"),
        ]

        for src, dst in pipeline_connections:
            iface = LatchInterface(f"if_{src}_{dst}", latency=1)
            self.stages[src].out_latch = iface
            self.stages[dst].in_latch = iface

            self.stages[src].add_output(iface)
            self.stages[dst].add_input(iface)

            print(f"[SM] Connected {src} → {dst} via {iface.name}")
            self.interfaces.append(iface)

        # === 3. Build feedback connections (non-pipelined control) ===
        feedbacks = feedbacks or []
        for src, dst in feedbacks:
            fb = LatchInterface(f"FB_{src}_{dst}", is_feedback=True)
            self.stages[src].feedbacks[dst] = fb
            self.stages[dst].feedbacks[src] = fb
            print(f"[SM] Feedback {src} ↔ {dst}")
        
        print("[SM] Stage connections summary:")
        for name, st in self.stages.items():
            print(f"  {name:>8}: inputs={len(st.inputs)} outputs={len(st.outputs)}")

    # ---------------------------------------
    # Interface helpers
    # ---------------------------------------

    def get_interface(self, name: str):
        return next((iface for iface in self.interfaces if iface.name == name), None)

    def push_instruction(self, inst, at_stage: str = "if_user_fetch"):
        """Inject instruction/data into a latch or stage."""
        target_if = None

        # Case 1: direct interface name
        if at_stage.startswith("if_"):
            target_if = self.get_interface(at_stage)
            if not target_if:
                print(f"[SM] No interface named '{at_stage}'.")
                return False
        else:
            # Case 2: stage name
            stage = self.stages.get(at_stage)
            if not stage:
                print(f"[SM] No stage named '{at_stage}'.")
                return False
            if not stage.in_latch:
                print(f"[SM] Stage '{at_stage}' has no input latch.")
                return False
            target_if = stage.in_latch

        if target_if.can_accept():
            print(f"[SM] Injecting into {target_if.name}: {inst}")
            target_if.send(inst)
            return True
        else:
            print(f"[SM] Interface {target_if.name} not ready (stall).")
            return False

    # ---------------------------------------
    # Simulation cycle
    # ---------------------------------------

    def cycle(self):
        """Advance one pipeline cycle."""
        self.global_cycle += 1
        self.perf.tick(1)
        self.perf.set_gauge("global_cycle", self.global_cycle)

        # PHASE 1: Run all stages (their compute() or cycle())
        for stage in self.stages.values():
            stage.compute()

        # PHASE 2: Tick all latch interfaces (commit + wait countdown)
        for iface in self.interfaces:
            iface.tick()

        self.logger.debug(f"Completed cycle {self.global_cycle}")

    def print_pipeline_state(self):
        print(f"\n=== Cycle {self.global_cycle} ===")
        for name, stage in self.stages.items():
            curr = getattr(stage, "current_inst", None)
            print(f"{name:>12}: {curr if curr else '-'}")
        print()


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
    """
    Generic pipeline stage that uses handshake-based LatchInterface connections.
    Handles inputs, outputs, feedbacks, and optional sub-units.
    """
    def __init__(self, name, parent_core):
        self.name = name
        self.parent_core = parent_core
        self.perf = PerfDomain(self.name, parent=getattr(self.parent_core, "perf", None))
        self.inputs: list[LatchInterface] = []
        self.outputs: list[LatchInterface] = []
        self.feedbacks: dict[str, LatchInterface] = {}
        self.subunits = []

        self.cycle_count = 0
        self.active_cycles = 0
        self.stall_cycles = 0
        self.instruction_count = 0
        self.current_inst = None

    # -------------------------
    # Interface management
    # -------------------------
    def add_input(self, latch: LatchInterface):
        self.inputs.append(latch)

    def add_output(self, latch: LatchInterface):
        self.outputs.append(latch)

    def connect_interfaces(self, input_latch: LatchInterface, output_latch: LatchInterface):
        self.add_input(input_latch)
        self.add_output(output_latch)

    def add_feedback(self, name: str, latch: LatchInterface):
        """Attach a combinational (non-pipelined) feedback connection."""
        self.feedbacks[name] = latch

    def add_subunit(self, fu):
        self.subunits.append(fu)

    # -------------------------
    # Core stage operation
    # -------------------------
    def process(self, inst):
        """Main stage logic. Override this in subclasses."""
        self.current_inst = inst
        return inst

    def compute(self):
        """Main pipeline execution logic, called once per cycle."""
        self.perf.tick()
        self.cycle_count += 1
        received = None

        # Try to receive from first available valid input latch
        for inp in self.inputs:
            data = inp.receive()
            if data:
                received = data
                break

        # If instruction/data received, process it
        if received:
            self.active_cycles += 1
            self.instruction_count += 1
            result = self.process(received)
            self.current_inst = result or received

            # Try to send output downstream
            if result is not None and self.outputs:
                out_latch = self.outputs[0]
                sent = out_latch.send(result)
                if not sent:
                    inp.set_wait(1)  # Backpressure: stall upstream one cycle
                    self.stall_cycles += 1
                    print(f"[{self.name}] Output stalled, backpressure applied.")
            else:
                self.stall_cycles += 1
        else:
            self.stall_cycles += 1
            self.current_inst = None

        # Tick all functional subunits (for stages that contain ALUs, etc.)
        self.tick_subunits()

    # -------------------------
    # Subunit handling
    # -------------------------
    def tick_subunits(self):
        for fu in self.subunits:
            if hasattr(fu, "tick"):
                fu.tick()

                # Automatically retrieve and forward results
                result = None
                if hasattr(fu, "get_output"):
                    result = fu.get_output()

                if result is not None and self.outputs:
                    out_latch = self.outputs[0]
                    sent = out_latch.send(result)
                    if sent:
                        print(f"[{self.name}] Auto-forwarded from {fu.name}: {result}")
                    else:
                        self.stall_cycles += 1
                        print(f"[{self.name}] FU {fu.name} stalled downstream.")
                elif result is not None:
                    print(f"[{self.name}] No output latch for FU {fu.name} result: {result}")

    # -------------------------
    # Debugging / visualization
    # -------------------------
    def debug_state(self):
        """Summarize current state for pretty-printing."""
        inst_info = None
        if self.current_inst is not None:
            inst = self.current_inst
            if isinstance(inst, dict):
                if "pc" in inst:
                    inst_info = f"pc=0x{inst['pc']:x}"
                elif "decoded_fields" in inst and "orig_inst" in inst["decoded_fields"]:
                    pc = inst["decoded_fields"]["orig_inst"].get("pc", None)
                    inst_info = f"pc=0x{pc:x}" if pc else str(inst)
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
