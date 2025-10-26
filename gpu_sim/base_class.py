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


@dataclass
class tb_data_params:
	gridX_dim: int
	gridY_dim: int
	gridZ_dim: int
	blockX_dim: int
	blockY_dim: int
	blockZ_dim: int
	

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
from dataclasses import dataclass, field
from typing import Optional


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
        for fu in self.subunits:
            if hasattr(fu, "tick"):
                fu.tick()

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
            self.active_cycles += 1
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
    
class DecodeStage(PipelineStage):
    def __init__(self, parent_core):
        super().__init__("Decode", parent_core)
        self.flush_flag = False
        self.halt = False

    def process(self, inst):
        if not inst:
            return None

        # Interpret instruction as a 32-bit integer and extract the low 7-bit opcode.
        raw = int(inst.get("raw", 0)) & 0xFFFFFFFF
        opcode_upper = raw & 0x7  # bits 6-3
        opcode_lower = (raw >> 3) & 0xF  # bits 2-0
        opcode_r0_dict = {
            "000": "add",
            "001": "sub",
            "010": "mul",
            "011": "div",
            "100": "and",
            "101": "or",
            "110": "xor",
            "111": "slt",
        }
        opcode_r1_dict = {
            "000": "sltu",
            "001": "addf",
            "010": "subf",
            "011": "mulf",
            "100": "divf",
            "101": "sll",
            "110": "srl",
            "111": "sra",
        }
        opcode_i0_dict = {
            "000": "addi",
            "001": "subi",
            "101": "ori",
            "111": "slti",
        }
        opcode_i1_dict = {
            "000": "sltiu",
            "001": "srli",
            "101": "srai",
        }
        opcode_i2_dict = {
            "000": "lw",
            "001": "st",
            "010": "lb",
            "011": "jalr"
        }

        def sign_extend(value: int, bits: int) -> int:
            sign_bit = 1 << (bits - 1)
            return (value & (sign_bit - 1)) - (value & sign_bit)

        # Field extraction according to the provided ISA layout
        opcode7 = raw & 0x7F
        rd = (raw >> 7) & 0x3F
        rs1 = (raw >> 13) & 0x3F
        # bits [24:19] used either as rs2 (6 bits) or imm field depending on type
        mid6 = (raw >> 19) & 0x3F
        pred = (raw >> 25) & 0x1F
        packet_start = bool((raw >> 30) & 0x1)
        packet_end = bool((raw >> 31) & 0x1)

        high4 = (opcode7 >> 3) & 0xF
        low3 = opcode7 & 0x7

        # Build opcode -> mnemonic map from the provided table (subset implemented)
        opcode_map = {
            # R-type (high4 = 0b0000)
            0b0000000: "add",
            0b0000001: "sub",
            0b0000010: "mul",
            0b0000011: "div",
            0b0000100: "and",
            0b0000101: "or",
            0b0000110: "xor",
            0b0000111: "slt",
            # R-type / FP and shifts (high4 = 0b0001)
            0b0001000: "sltu",  # 0001 000 -> 8
            0b0001001: "addf",
            0b0001010: "subf",
            0b0001011: "mulf",
            0b0001100: "divf",
            0b0001101: "sll",
            0b0001110: "srl",
            0b0001111: "sra",
            # I-type (0010, 0011)
            0b0010000: "addi",
            0b0010001: "subi",
            0b0010101: "ori",
            0b0010111: "slti",
            0b0011000: "sltiu",  # 0011 000 -> 24
            0b0011110: "srli",
            0b0011111: "srai",
            0b0100000: "lw",    # 0100 000 -> 32
            0b0100001: "lh",
            0b0100010: "lb",
            0b0100011: "jalr",
            # F-type (0101)
            0b0101000: "isqrt",
            0b0101001: "sin",
            0b0101010: "cos",
            0b0101011: "itof",
            0b0101100: "ftoi",
            # S-type (0110)
            0b0110000: "sw",
            0b0110001: "sh",
            0b0110010: "sb",
            # B-type (1000)
            0b1000000: "beq",
            0b1000001: "bne",
            0b1000010: "bge",
            0b1000011: "bgeu",
            0b1000100: "blt",
            0b1000101: "bltu",
            # U-type (1010)
            0b1010000: "auipc",
            0b1010001: "lli",
            0b1010010: "lmi",
            0b1010100: "lui",
            # C-type (1011)
            0b1011000: "csrr",
            0b1011001: "csrw",
            # J-type (1100)
            0b1100000: "jal",
            # P-type (1101)
            0b1101000: "jpnz",
            # H-type: halt is all ones (0b1111111 -> 127)
            0b1111111: "halt",
        }

        mnemonic = opcode_map.get(opcode7, "nop")

        # Interpret fields according to determined instruction class (best-effort)
        decoded: dict = {
            "raw": raw,
            "opcode7": opcode7,
            "mnemonic": mnemonic,
            "predication": pred,
            "packet_start": packet_start,
            "packet_end": packet_end,
        }

        # Classify by high4 nibble
        if high4 in (0x0, 0x1):
            # R-type family (register-register)
            decoded.update({"type": "R", "rd": rd, "rs1": rs1, "rs2": mid6})
        elif high4 in (0x2, 0x3, 0x4):
            # I-type family (immediates and loads/jalr)
            imm6 = sign_extend(mid6, 6)
            decoded.update({"type": "I", "rd": rd, "rs1": rs1, "imm": imm6})
        elif high4 == 0x5:
            # F-type / unary ops: rd, rs1
            decoded.update({"type": "F", "rd": rd, "rs1": rs1})
        elif high4 in (0x6, 0x7):
            # S-type family (store / memory write)
            decoded.update({"type": "S", "imm": mid6, "rs1": rs1, "rs2": rd})
        elif high4 == 0x8:
            # B-type (branch): preddest in rd field
            decoded.update({"type": "B", "pred_dest": rd, "rs1": rs1, "rs2": mid6})
        elif high4 == 0xA:
            # U-type: 12-bit immediate occupies bits [24:13]
            imm12 = (raw >> 13) & 0xFFF
            decoded.update({"type": "U", "rd": rd, "imm12": sign_extend(imm12, 12)})
        elif high4 == 0xB:
            # C-type: CSR op
            decoded.update({"type": "C", "rd": rd, "csr": (raw >> 13) & 0x3FF})
        elif high4 == 0xC:
            # J-type: jal
            imm12 = (raw >> 13) & 0xFFF
            decoded.update({"type": "J", "rd": rd, "imm12": sign_extend(imm12, 12)})
        elif high4 == 0xD:
            # P-type: predicated jump
            decoded.update({"type": "P", "rs1": rs1, "rs2": mid6})
        elif opcode7 == 0x7F:
            decoded.update({"type": "H", "mnemonic": "halt"})
        else:
            decoded.update({"type": "UNKNOWN"})

        # Attach the original instruction for reference
        decoded["orig_inst"] = inst

        return {"decoded": True, "decoded_fields": decoded}

    def flush(self):
        """Flush the stage and its interfaces."""
        if self.input_if:
            self.input_if.flush()
        if self.output_if:
            self.output_if.flush()
        self.flush_flag = True

    def debug_state(self):
        return {
            "name": self.name,
            "flush_flag": self.flush_flag,
            "halt": self.halt,
        }
       
# this function is for the building the test instruction sequences out of fields
def make_raw(op7: int, rd: int = 1, rs1: int = 2, mid6: int = 3, pred: int = 0, packet_start: bool = False, packet_end: bool = False) -> int:
    """Construct a 32-bit instruction word according to the DecodeStage layout:
    bits [6:0]   = opcode7
    bits [12:7]  = rd (6)
    bits [18:13] = rs1 (6)
    bits [24:19] = mid6 (6)
    bits [29:25] = pred (5)
    bit  [30]    = packet_start
    bit  [31]    = packet_end
    """
    raw = (
        (int(packet_end) << 31)
        | (int(packet_start) << 30)
        | ((pred & 0x1F) << 25)
        | ((mid6 & 0x3F) << 19)
        | ((rs1 & 0x3F) << 13)
        | ((rd & 0x3F) << 7)
        | (op7 & 0x7F)
    )
    return raw

#--------------------------------------------------------
# THIS IS A SAMPLE CODE SEQUENCE TO TEST THE DECODER.
# REPLACE WITH NAMING FOR YOUR UNIT CLASS NAME AS NEEDED.
#--------------------------------------------------------
# # Build a small sequence of instructions that align with the decoder's expected opcode values
# test_in = StageInterface("IF_FetchDecode", latency=1)
# test_out = StageInterface("IF_DecodeExec", latency=1)
# decode = DecodeStage("SM_1") # putting in some bull shit SM right now
# decode.connect_interfaces(test_in, test_out)
# # 
# # UNCOMMENT THIS WHEN YOU'RE READY TO TEST!
# # THIS IS NOT A CYCLE ACCURATE SIM JUST YET--JUST FUNCTIONAL. 
# # SM MODULE FOR SIMULATING CYCLE ACCURATE PROCESSES IS IN PROGRESS.
# instructions = [
#     {"pc": 0x100, "raw": make_raw(0x00, rd=1, rs1=2, mid6=3)},    # add (R-type)
#     {"pc": 0x104, "raw": make_raw(0x10, rd=5, rs1=6, mid6=0)},    # addi (I-type)
#     {"pc": 0x108, "raw": make_raw(0x20, rd=2, rs1=3, mid6=4)},    # lw  (I-type / load)
#     {"pc": 0x10C, "raw": make_raw(0x30, rd=2, rs1=3, mid6=4)},    # sw  (S-type)
#     {"pc": 0x110, "raw": make_raw(0x40, rd=0, rs1=1, mid6=2, pred=1, packet_start=True)},  # beq (B-type) with packet start
#     {"pc": 0x114, "raw": make_raw(0x7F, rd=0, rs1=0, mid6=0)},    # halt (H-type)
# ]


# # this is only functional for modular testing of ONE stage. 
# for inst in instructions:
#     print(f"\nIssuing instruction pc=0x{inst['pc']:x} raw=0x{inst['raw']:08x}")
    
#     # Wait until decode can accept a new one
#     while not test_in.can_accept():
#         test_in.tick() 
#         test_out.tick()
#         decode.cycle()

#     # Send and advance one cycle
#     test_in.send(inst)
#     test_in.tick()
#     test_out.tick()
    
#     #REPLACE WITH YOUR UNIT CLASS.cycle()
#     #EX. decode.cycle()

#     # Next cycle: promote and observe decode output
#     test_in.tick()
#     test_out.tick()
#     decode.cycle()

#     print(f"Output IF: valid={test_out.valid}, ready={test_out.ready}, data={test_out.data}")