"""
sm-from-bin.py
==============
Drop-in replacement for sm-no-mem.py that sources its instruction stream from
a binary or hex file instead of a hard-coded test_cases list.

Supported file formats
----------------------
bin  : one 32-bit instruction per line as a text string of '0'/'1' characters,
       comments after '//' or '#' are stripped (matches Memory.py / test.bin).
hex  : two sub-formats are accepted:
       • bare 8-char hex per line  (e.g.  40184080)
       • "0xADDR 0xDATA" pair       (e.g.  0x00001000 0x40184080,  memsim.hex style)

The file is decoded with the same bit-field layout used by decode_class.py:
  bits[ 6: 0]  opcode (7 bits)
  bits[12: 7]  rd     (6 bits)
  bits[18:13]  rs1    (6 bits)
  bits[24:19]  rs2 / imm (6 bits)
  bits[29:25]  pred   (5 bits)
  bit 30       start
  bit 31       end-of-packet

Golden model
------------
Each decoded instruction is examined and the matching Python computation is
applied to the golden RegisterFile on the fly – no hard-coded lambdas needed.
"""
from __future__ import annotations
from builtins import float
from dataclasses import dataclass
from pathlib import Path
from copy import deepcopy
from typing import Any, Dict, List, Optional
from contextlib import redirect_stdout
import argparse
import io
import math
import sys
from pathlib import Path
from typing import List, Optional

from bitstring import Bits

# ── path setup ────────────────────────────────────────────────────────────────
FILE_ROOT     = Path(__file__).resolve().parent
GPU_SIM_ROOT  = Path(__file__).resolve().parents[3]
sys.path.append(str(GPU_SIM_ROOT))

# ── simulator imports ──────────────────────────────────────────────────────────
from gpu.common.custom_enums_multi import (
    Instr_Type, R_Op, I_Op, F_Op, S_Op, B_Op, U_Op, J_Op, P_Op, H_Op, C_Op, Op
)

from simulator.latch_forward_stage import (
    LatchIF, ForwardingIF, Instruction, DecodeType
)
from simulator.execute.stage import ExecuteStage, FunctionalUnitConfig
from simulator.writeback.stage import WritebackStage, WritebackBufferConfig, RegisterFileConfig, PredicateRegisterFileConfig
from simulator.issue.regfile import RegisterFile
from simulator.issue.stage import IssueStage
from simulator.scheduler.csrtable import CsrTable
from simulator.kernel_base_pointers import KernelBasePointers
from simulator.scheduler.scheduler import SchedulerStage
from simulator.tbs.tbs import ThreadBlockScheduler
from simulator.mem.icache_stage import ICacheStage
from simulator.mem.mem_controller import MemController
from simulator.mem.Memory import Mem
from simulator.mem.dcache import LockupFreeCacheStage
from simulator.decode.decode_class import DecodeStage
from simulator.decode.predicate_reg_file import PredicateRegFile

# ── global constants ───────────────────────────────────────────────────────────
START_PC    = 0x1000
MEM_LATENCY = 2
WARP_COUNT  = 32

# ==============================================================================
#  File loading & decoding
# ==============================================================================

def load_program(file_path: Path, fmt: str = "bin") -> List[int]:

    program = []

    with file_path.open("r") as fh:

        for line_no, raw in enumerate(fh, start=1):

            # strip comments
            for marker in ("//", "#"):
                idx = raw.find(marker)
                if idx != -1:
                    raw = raw[:idx]

            line = raw.strip().replace("_", "")
            if not line:
                continue

            parts = line.split()

            if len(parts) != 2:
                raise ValueError(
                    f"Line {line_no}: expected format 'addr data'"
                )

            addr_str, data_str = parts

            addr = int(addr_str, 0)

            if addr % 4 != 0:
                raise ValueError(
                    f"Line {line_no}: address {addr:#x} not word aligned"
                )

            if fmt == "bin":

                if len(data_str) != 32:
                    raise ValueError(
                        f"Line {line_no}: expected 32-bit binary"
                    )

                word = int(data_str, 2)

            elif fmt == "hex":

                word = int(data_str, 16)

            else:
                raise ValueError("format must be bin or hex")

            program.append((addr, word & 0xFFFFFFFF))

    # --------------------------------------------------
    # Sort by address so pipeline executes correctly
    # --------------------------------------------------

    program.sort(key=lambda x: x[0])

    words = [w for _, w in program]

    return words

def _find_opcode_enum(opcode7: int):
    """Return the enum member whose .value matches the 7-bit opcode, or None."""
    opcode_bits = Bits(uint=opcode7, length=7)
    for enum_cls in (R_Op, I_Op, F_Op, C_Op, S_Op, B_Op, U_Op, J_Op, P_Op, H_Op):
        for member in enum_cls:
            if member.value == opcode_bits:
                return member
    return None

def deep_update(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_update(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out

def decode_word(raw: int) -> dict:
    """
    Decode a single 32-bit instruction word using the canonical field layout.

    Returns a dictionary with keys:
        raw, opcode_enum, opcode_family,
        rd, rs1, rs2, imm,
        pred, start, end_of_packet,
        is_R, is_I, is_F, is_C, is_S, is_B, is_U, is_J, is_P, is_H,
        is_halt
    """
    opcode7     = raw & 0x7F
    rd          = (raw >> 7)  & 0x3F
    rs1         = (raw >> 13) & 0x3F
    rs2_or_imm  = (raw >> 19) & 0x3F
    pred        = (raw >> 25) & 0x1F
    start_bit   = (raw >> 30) & 0x1
    eop_bit     = (raw >> 31) & 0x1

    opcode_enum = _find_opcode_enum(opcode7)
    opcode_family = type(opcode_enum) if opcode_enum is not None else None

    is_R = opcode_family is R_Op
    is_I = opcode_family is I_Op
    is_F = opcode_family is F_Op
    is_C = opcode_family is C_Op
    is_S = opcode_family is S_Op
    is_B = opcode_family is B_Op
    is_U = opcode_family is U_Op
    is_J = opcode_family is J_Op
    is_P = opcode_family is P_Op
    is_H = opcode_family is H_Op

    return {
        "raw":           raw,
        "opcode_enum":   opcode_enum,
        "opcode_family": opcode_family,
        "rd":            rd,
        "rs1":           rs1,
        # rs2 only meaningful for R/S/B; imm for I-type; same bits
        "rs2":           rs2_or_imm,
        "imm":           rs2_or_imm,
        "pred":          pred,
        "start":         start_bit,
        "eop":           eop_bit,
        "is_R": is_R, "is_I": is_I, "is_F": is_F, "is_C": is_C,
        "is_S": is_S, "is_B": is_B, "is_U": is_U, "is_J": is_J,
        "is_P": is_P, "is_H": is_H,
        "is_halt": (opcode_enum == H_Op.HALT) if is_H else False,
    }

def build_pipeline(input_file: Path, 
                   fmt: str = "bin", 
                   sm_config: dict | None = None,
                   sm_id: int = 0) -> dict:
    """Instantiate all pipeline stages and return them as a dict."""
    # Latches
    tbs_ws_if               = LatchIF("TBS-WS Latch")
    sched_icache_if         = LatchIF("Sched-ICache Latch")
    icache_mem_req_if       = LatchIF("ICache-Mem Latch")
    mem_icache_resp_if      = LatchIF("Mem-ICache Latch")
    icache_decode_if        = LatchIF("ICache-Decode Latch")
    decode_issue_if         = LatchIF("Decode-Issue Latch")
    is_ex_latch             = LatchIF("IS-EX Latch")
    # D-Cache latches (LSU ↔ DCache ↔ MemController)
    lsu_dcache_latch        = LatchIF("LSU-DCache Latch")
    dcache_lsu_forward      = ForwardingIF(name="dcache_lsu_forward")
    lsu_dcache_latch.forward_if = dcache_lsu_forward   # binds response IF onto request latch
    dcache_mem_latch        = LatchIF("DCache-Mem Latch")
    mem_dcache_latch        = LatchIF("Mem-DCache Latch")

    # Forwarding IFs
    scheduler_tbs_fwif      = ForwardingIF(name="scheduler_tbs_if")
    icache_scheduler_fwif   = ForwardingIF(name="icache_forward_if")
    decode_scheduler_fwif   = ForwardingIF(name="decode_forward_if")
    issue_scheduler_fwif    = ForwardingIF(name="issue_forward_if")
    branch_scheduler_fwif   = ForwardingIF(name="branch_forward_if")
    writeback_scheduler_fwif = ForwardingIF(name="Writeback_forward_if")
    decode_issue_fwif       = ForwardingIF(name="Decode_issue_fwif")
    scheduler_ldst_fwif     = ForwardingIF(name="scheduler_ldst_fwif")
    ldst_scheduler_fwif     = ForwardingIF(name="ldst_scheduler_fwif")

    cfg = deep_update(DEFAULT_SM_CONFIG, sm_config or {})
    
    start_pc = cfg["sim"]["start_pc"]
    warp_count = cfg["sim"]["warp_count"]
    mem_latency = cfg["mem"]["latency"]
    
    mem = Mem(start_pc=start_pc, input_file=str(input_file), fmt=fmt)

    memc = MemController(
        name="Mem_Controller",
        ic_req_latch=icache_mem_req_if,
        dc_req_latch=dcache_mem_latch,
        ic_serve_latch=mem_icache_resp_if,
        dc_serve_latch=mem_dcache_latch,
        mem_backend=mem,
        latency=mem_latency,
        policy="rr",
    )

    # D-Cache stage
    dcache_stage = LockupFreeCacheStage(
        name="dCache",
        behind_latch=lsu_dcache_latch,
        forward_ifs_write={"DCache_LSU_Resp": dcache_lsu_forward},
        mem_req_if=dcache_mem_latch,
        mem_resp_if=mem_dcache_latch,
        cache_config=cfg["dcache"]
    )

    fu_config = FunctionalUnitConfig.get_default_config()
    # update the mem branch config with the word size and block size for the Ldst FU
    fu_config.membranchjump_config.block_size_words = cfg["dcache"]["block_size_words"]
    fu_config.membranchjump_config.word_size_bytes = cfg["dcache"]["word_size_bytes"]

    fust      = fu_config.generate_fust_dict()

    csr_table = CsrTable()
    
    tbs = ThreadBlockScheduler(
        name="Thread_Block_Scheduler",
        behind_latch=None,
        ahead_latch=tbs_ws_if,
        forward_ifs_read={
            "Scheduler_TBS": scheduler_tbs_fwif
        },
        forward_ifs_write=None
    )

    scheduler_stage = SchedulerStage(
        name="Scheduler_Stage",
        behind_latch=tbs_ws_if,
        ahead_latch=sched_icache_if,
        forward_ifs_read={
            "ICache_Scheduler":    icache_scheduler_fwif,
            "Decode_Scheduler":    decode_scheduler_fwif,
            "Issue_Scheduler":     issue_scheduler_fwif,
            "Branch_Scheduler":    branch_scheduler_fwif,
            "Writeback_Scheduler": writeback_scheduler_fwif,
            "LDST_Scheduler":      ldst_scheduler_fwif
        },
        # forward_ifs_write=None,
        forward_ifs_write={
            "Scheduler_LDST": scheduler_ldst_fwif, 
            "Scheduler_TBS": scheduler_tbs_fwif
        },
        csrtable = csr_table,
        warp_count=WARP_COUNT,
    )

    # NOTE Kai Ze: Remove after we bring in TBS
    # tbs_ws_if.push([0, tb_size, start_pc])

    icache_stage = ICacheStage(
        name="ICache_Stage",
        behind_latch=sched_icache_if,
        ahead_latch=icache_decode_if,
        mem_req_if=icache_mem_req_if,
        mem_resp_if=mem_icache_resp_if,
        cache_config=cfg["icache"],
        forward_ifs_write={"ICache_Scheduler": icache_scheduler_fwif},
    )

    prf = PredicateRegFile(num_preds_per_warp=cfg["predicates"]["num_preds_per_warp"], num_warps=WARP_COUNT)
    for warp in range(WARP_COUNT):
        for pred in range(cfg["predicates"]["num_preds_per_warp"]):
            prf.reg_file[warp][pred] = [True] * 32

    kernel_base_ptrs = KernelBasePointers(max_kernels_per_SM=1)

    # should i change this?
    kernel_base_ptrs.write(0, Bits(uint=cfg["sim"]["kern_base_ptr"], length=32))

    decode_stage = DecodeStage(
        name="Decode Stage",
        behind_latch=icache_decode_if,
        ahead_latch=decode_issue_if,
        prf=prf,
        fust=fust,
        csr_table=csr_table,
        kernel_base_ptrs=kernel_base_ptrs,
        forward_ifs_read={"ICache_Decode_Ihit": icache_scheduler_fwif},
        forward_ifs_write={"Decode_Scheduler_Pckt": decode_scheduler_fwif},
    )

    pipeline_rf = RegisterFile()
    golden_rf   = RegisterFile()

    ex_stage = ExecuteStage.create_pipeline_stage(
        functional_unit_config=fu_config,
        fust=fust
    )
    ex_stage.behind_latch = is_ex_latch
    ex_stage.functional_units["MemBranchJumpUnit_0"].subunits["Jump_0"].schedule_if = (
        branch_scheduler_fwif
    )

    # Wire LSU to D-Cache
    ldst = ex_stage.functional_units["MemBranchJumpUnit_0"].subunits["Ldst_Fu_0"]
    ldst.connect_interfaces(
        dcache_if=lsu_dcache_latch,
        sched_ldst_if=scheduler_ldst_fwif,
        ldst_sched_if=ldst_scheduler_fwif,
    )

    wb_buffer_config = WritebackBufferConfig.get_default_config()
    wb_buffer_config.validate_config(fsu_names=list(fust.keys()))
    rf_config = RegisterFileConfig.get_config_from_reg_file(reg_file=pipeline_rf)
    pred_reg_file_config = PredicateRegisterFileConfig.get_config_from_pred_reg_file(pred_reg_file=prf)
    
    wb_stage = WritebackStage.create_pipeline_stage(
        wb_config=wb_buffer_config,
        rf_config=rf_config,
        pred_rf_config=pred_reg_file_config,
        ex_stage_ahead_latches=ex_stage.ahead_latches,
        reg_file=pipeline_rf,
        pred_reg_file=prf,
        forward_ifs_write=scheduler_stage.forward_ifs_read,
        fsu_names=list(fust.keys()),
    )

    issue_stage = IssueStage(
        fust_latency_cycles=1,
        regfile=pipeline_rf,
        fust=fust,
        name="IssueStage",
        behind_latch=decode_issue_if,
        ahead_latch=is_ex_latch,
        forward_ifs_read=None,
        forward_ifs_write={
            "issue_scheduler_fwif": issue_scheduler_fwif,
            "decode_issue_fwif":    decode_issue_fwif,
        },
    )

    # Bootstrap forwarding IFs so the scheduler never sees None on cycle 0
    filler_decode  = {"type": DecodeType.MOP, "warp_id": 0, "pc": 0}
    filler_issue   = [0] * scheduler_stage.num_groups
    icache_scheduler_fwif.payload    = None
    decode_scheduler_fwif.push(filler_decode)
    issue_scheduler_fwif.push(filler_issue)
    branch_scheduler_fwif.payload    = None
    writeback_scheduler_fwif.payload = None

    return {
        "tbs":         tbs,
        "scheduler":   scheduler_stage,
        "icache":      icache_stage,
        "decode":      decode_stage,
        "issue":       issue_stage,
        "ex":          ex_stage,
        "wb":          wb_stage,
        "memc":        memc,
        "dcache":      dcache_stage,
        "ldst":        ldst,
        "pipeline_rf": pipeline_rf,
        "golden_rf":   golden_rf,
        "csr_table":   csr_table,
        "kbp":         kernel_base_ptrs,
        "fust":        fust,
        "prf":         prf,
        "mem":         mem,
    }

def tick_all(p: dict):
    """Tick every pipeline stage once (same order as sm-no-mem.py)."""
    p["wb"].tick()
    p["ex"].tick()
    p["ex"].compute()
    p["dcache"].compute()
    p["issue"].compute()
    p["decode"].compute()
    p["memc"].compute()
    p["icache"].compute()
    p["scheduler"].compute()
    p["tbs"].compute()

DEFAULT_SM_CONFIG = {
    "sim": {
        "start_pc": 0x0,
        "warp_count": 32,
        "bdim": 32,
        "max_cycles": 20000,
        "test_name": "vertex_shader_pranav.bin",
        "kern_base_ptr": 3889068044, # keeping this a decimal value 
        "dump_root": "sweep_dumps",
    },
    "mem": {
        "latency": 4,
        "policy": "rr",
    },
    "icache": {
        "cache_size": 32 * 1024,
        "block_size": 4,
        "associativity": 1,
    },
    "dcache": {
        "num_banks": 2,
        "num_sets_per_bank": 16,
        "num_ways": 8,
        "block_size_words": 32,
        "word_size_bytes": 4,
        "uuid_size": 8,
        "mshr_buffer_len": 16,
        "hit_latency": 2,
    },
    "predicates": {
        "num_preds_per_warp": 32,
    },
}


@dataclass
class SM:
    sm_id: int
    fmt: str = "bin"
    config: Optional[dict] = None

    def __post_init__(self):
        self.config = deep_update(DEFAULT_SM_CONFIG, self.config or {})
        self.program_path = Path(f"gpu/tests/simulator/integration3/test_binaries/{self.config['sim']['test_name']}")
        self.words = load_program(file_path=self.program_path, fmt=self.fmt)
        self.decoded_instrs = [decode_word(w) for w in self.words]
        self.num_loaded_words = len(self.words)
        self.num_decoded_words = sum(
            1 for d in self.decoded_instrs if d["opcode_enum"] is not None
        )
        self.pipeline = build_pipeline(
            input_file=self.program_path,
            fmt=self.fmt,
            sm_config=self.config,
            sm_id=self.sm_id,
        )
        self.cycle = 0
        self.finished = False

        self.pipeline["tbs"].add_SM()  # add ONE SM to this TBS
        self.pipeline["tbs"].append_block(
            bdim=self.config["sim"]["bdim"],
            spc=self.config["sim"]["start_pc"],
            apc=self.config["sim"]["kern_base_ptr"],
        )

    def tick(self):
        if self.finished:
            print(f"{self.sm_id:02d} Simulation complete in {self.cycle} cycles with lat {MEM_LATENCY} cycle memory latency.")
            return
        tick_all(self.pipeline)
        print(f"{self.sm_id:02d}: Cycle {self.cycle}")
        self.cycle += 1
        self.finished = self.pipeline["scheduler"].system_finished

    def run_to_completion(self, max_cycles: Optional[int] = None):
        limit = max_cycles or self.config["sim"]["max_cycles"]
        while not self.finished and self.cycle < limit:
            self.tick()

        self.dump_files()

        return {
            "sm_id": self.sm_id,
            "finished": self.finished,
            "cycles": self.cycle,
            "icache": deepcopy(self.config["icache"]),
            "dcache": deepcopy(self.config["dcache"]),
        }
    
    def print_banks(self):
        # --- 1. Calculate Bit Widths for Reconstruction ---
        # Offset: 32 words * 4 bytes = 128 bytes -> 7 bits (usually)
        dCache = self.pipeline["dcache"]
        offset_bits = int(math.log2(self.config["dcache"]["block_size_words"] * 4))
        
        # Bank Bits: log2(number of banks)
        num_banks = len(dCache.banks)
        bank_bits = int(math.log2(num_banks)) if num_banks > 1 else 0
        
        # Set Bits: log2(number of sets per bank)
        num_sets = len(dCache.banks[0].sets)
        set_bits = int(math.log2(num_sets))

        # Calculate Shift Amounts (Assuming Addr Structure: [ Tag | Set | Bank | Offset ])
        shift_bank = offset_bits
        shift_set = offset_bits + bank_bits
        shift_tag = offset_bits + bank_bits + set_bits
        # --------------------------------------------------

        for bank_id, bank in enumerate(dCache.banks):
            print(f"\n======== Bank {bank_id} ========")
            found_valid_line = False

            for set_id, cache_set in enumerate(bank.sets):
                set_has_valid_lines = any(frame.valid for frame in cache_set)

                if set_has_valid_lines:
                    found_valid_line = True
                    print(f"  ---- Set {set_id} ----")

                    lru_list = bank.lru[set_id]
                    print(f"    LRU Order: {lru_list} (Front=MRU, Back=LRU)")

                    for way_id, frame in enumerate(cache_set):
                        if frame.valid:
                            tag_hex = f"0x{frame.tag:X}"
                            dirty_str = "D" if frame.dirty else " "
                            
                            # --- 2. Reconstruct the Address ---
                            # (Tag << shifts) | (Set << shifts) | (Bank << shifts)
                            full_addr = (frame.tag << shift_tag) | (set_id << shift_set) | (bank_id << shift_bank)
                            addr_hex = f"0x{full_addr:08X}" # Format as 8-digit Hex
                            # ----------------------------------

                            # Print Tag AND Address
                            print(f"    [Way {way_id}] V:1 {dirty_str} Tag: {tag_hex:<6} (Addr: {addr_hex})")

                            for i in range(0, self.config["dcache"]["block_size_words"], 4):
                                # FIX: Add '& 0xFFFFFFFF' to force unsigned 32-bit representation
                                w0 = f"0x{(frame.block[i] & 0xFFFFFFFF):08X}"
                                w1 = f"0x{(frame.block[i+1] & 0xFFFFFFFF):08X}"
                                w2 = f"0x{(frame.block[i+2] & 0xFFFFFFFF):08X}"
                                w3 = f"0x{(frame.block[i+3] & 0xFFFFFFFF):08X}"
                                
                                print(f"        Block[{i:02d}:{i+3:02d}]: {w0} {w1} {w2} {w3}")

            if not found_valid_line:
                print(f"  (Bank is empty)")
        
    def dump_files(self, dump_root: Optional[Path] = None):
        root = Path(dump_root) if dump_root else Path("gpu/tests/simulator/integration3/sweep_dumps") / self.config["sim"]["dump_root"]
        sm_dir = root / f"sm_{self.sm_id:02d}"
        sm_dir.mkdir(parents=True,exist_ok=True)

        output_file = sm_dir / "output.txt"

        with output_file.open("w", encoding="utf-8") as f:
            with redirect_stdout(f):
                print(f"===== SM {self.sm_id:02d} DUMP =====")
                print(f"Program   : {self.program_path} (format={self.fmt})")
                print(f"Finished  : {self.finished}")
                print(f"Loaded    : {self.num_loaded_words} words")
                print(f"Decoded   : {self.num_decoded_words} instructions")
                print(f"Cycles    : {self.cycle}")
                print(f"I$ config : {self.config['icache']}")
                print(f"D$ config : {self.config['dcache']}")
                print()

                print("===== DCACHE =====")
                self.print_banks()
                print()

                print("===== PIPELINE RF =====")
                self.pipeline["pipeline_rf"].dump()
                print()

                print("===== PRF =====")
                self.pipeline["prf"].dump()
                print()
        
        mem_sim_dump_file = sm_dir / "memsim.hex"

        self.pipeline["mem"].dump(path=mem_sim_dump_file)  # prevent automatic dump on program exit since we already dumped here
        
        return output_file, mem_sim_dump_file

def build_sweep_configs() -> List[Dict[str, Any]]:
    # sweep_points: List[Dict[str, Any]] = []

    mem_sweep = [
        deep_update(DEFAULT_SM_CONFIG, {"mem": {"latency": 4}, "sim": {"dump_root": "mem_pranav_vertex_shader_dump", "kern_base_ptr": 3889068044, "test_name": "vertex_shader_pranav.bin"}}), # baseline
        deep_update(DEFAULT_SM_CONFIG, {"mem": {"latency": 6}, "sim": {"dump_root": "mem_pranav_vertex_shader_dump", "kern_base_ptr": 3889068044, "test_name": "vertex_shader_pranav.bin"}}), # higher latency
        deep_update(DEFAULT_SM_CONFIG, {"mem": {"latency": 10}, "sim": {"dump_root": "mem_pranav_vertex_shader_dump", "kern_base_ptr": 3889068044, "test_name": "vertex_shader_pranav.bin"}}), # even higher latency
        deep_update(DEFAULT_SM_CONFIG, {"mem": {"latency": 14}, "sim": {"dump_root": "mem_pranav_vertex_shader_dump", "kern_base_ptr": 3889068044, "test_name": "vertex_shader_pranav.bin"}}),
    ]
    dcache_sweep = [
        DEFAULT_SM_CONFIG,

        # 32 KB total, 2 banks baseline
        deep_update(DEFAULT_SM_CONFIG, {
            "dcache": {
                "num_banks": 2,
                "num_sets_per_bank": 16,
                "num_ways": 8,
                "block_size_words": 32,
            },
            "sim": {"test_name": "vertex_shader_pranav.bin", "dump_root": "dcache_pranav_vertex_shader_dump"}
        }),

        # 32 KB total, more banks, lower associativity
        deep_update(DEFAULT_SM_CONFIG, {
            "dcache": {
                "num_banks": 4,
                "num_sets_per_bank": 16,
                "num_ways": 4,
                "block_size_words": 32,
            },
            "sim": {"test_name": "vertex_shader_pranav.bin", "dump_root": "dcache_pranav_vertex_shader_dump"}
        }),

        deep_update(DEFAULT_SM_CONFIG, {
            "dcache": {
                "num_banks": 8,
                "num_sets_per_bank": 16,
                "num_ways": 2,
                "block_size_words": 32,
            },
            "sim": {"test_name": "vertex_shader_pranav.bin", "dump_root": "dcache_pranav_vertex_shader_dump"}
        }),

        deep_update(DEFAULT_SM_CONFIG, {
            "dcache": {
                "num_banks": 16,
                "num_sets_per_bank": 16,
                "num_ways": 1,
                "block_size_words": 32,
            },
            "sim": {"test_name": "vertex_shader_pranav.bin", "dump_root": "dcache_pranav_vertex_shader_dump"}
        }),
    ]
    
    icache_sweep = [
        deep_update(DEFAULT_SM_CONFIG, {"icache": {"associativity": 1}, "sim": {"dump_root": "icache_sweep_dumps"}}),
        deep_update(DEFAULT_SM_CONFIG, {"icache": {"associativity": 2}, "sim": {"dump_root": "icache_sweep_dumps"}}),
        deep_update(DEFAULT_SM_CONFIG, {"icache": {"associativity": 4}, "sim": {"dump_root": "icache_sweep_dumps"}}),
        deep_update(DEFAULT_SM_CONFIG, {"icache": {"associativity": 8}, "sim": {"dump_root": "icache_sweep_dumps"}}),
    ]
    
    DCACHE_SWEEPS = {
    "num_ways": [
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "sim": {
                    "dump_root": "SAXPY_dcache_sweeps/num_ways",
                    "test_name": "baseline",
                }
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 128,
                    "num_ways": 1,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "SAXPY_dcache_sweeps/num_ways",
                    "test_name": "ways_1",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 64,
                    "num_ways": 2,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/num_ways",
                    "test_name": "ways_2",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 32,
                    "num_ways": 4,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/num_ways",
                    "test_name": "ways_4",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 16,
                    "num_ways": 8,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/num_ways",
                    "test_name": "ways_8",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 8,
                    "num_ways": 16,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/num_ways",
                    "test_name": "ways_16",
                },
            },
        ),
    ],

    "num_sets_per_bank": [
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "sim": {
                    "dump_root": "dcache_sweeps/num_sets_per_bank",
                    "test_name": "baseline",
                }
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 8,
                    "num_ways": 16,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/num_sets_per_bank",
                    "test_name": "sets_8",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 16,
                    "num_ways": 8,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/num_sets_per_bank",
                    "test_name": "sets_16",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 32,
                    "num_ways": 4,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/num_sets_per_bank",
                    "test_name": "sets_32",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 64,
                    "num_ways": 2,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/num_sets_per_bank",
                    "test_name": "sets_64",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 128,
                    "num_ways": 1,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/num_sets_per_bank",
                    "test_name": "sets_128",
                },
            },
        ),
    ],

    "block_size_words": [
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "sim": {
                    "dump_root": "dcache_sweeps/block_size_words",
                    "test_name": "baseline",
                }
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 128,
                    "num_ways": 8,
                    "block_size_words": 4,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/block_size_words",
                    "test_name": "block_4",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 64,
                    "num_ways": 8,
                    "block_size_words": 8,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/block_size_words",
                    "test_name": "block_8",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 32,
                    "num_ways": 8,
                    "block_size_words": 16,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/block_size_words",
                    "test_name": "block_16",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 16,
                    "num_ways": 8,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/block_size_words",
                    "test_name": "block_32",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 8,
                    "num_ways": 8,
                    "block_size_words": 64,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/block_size_words",
                    "test_name": "block_64",
                },
            },
        ),
    ],

    "num_banks": [
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "sim": {
                    "dump_root": "dcache_sweeps/num_banks",
                    "test_name": "baseline",
                }
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 1,
                    "num_sets_per_bank": 32,
                    "num_ways": 8,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/num_banks",
                    "test_name": "banks_1",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 16,
                    "num_ways": 8,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/num_banks",
                    "test_name": "banks_2",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 4,
                    "num_sets_per_bank": 8,
                    "num_ways": 8,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/num_banks",
                    "test_name": "banks_4",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 8,
                    "num_sets_per_bank": 4,
                    "num_ways": 8,
                    "block_size_words": 32,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/num_banks",
                    "test_name": "banks_8",
                },
            },
        ),
    ],

    "mshr_buffer_len": [
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "sim": {
                    "dump_root": "dcache_sweeps/mshr_buffer_len",
                    "test_name": "baseline",
                }
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {"mshr_buffer_len": 1},
                "sim": {
                    "dump_root": "dcache_sweeps/mshr_buffer_len",
                    "test_name": "mshr_1",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {"mshr_buffer_len": 2},
                "sim": {
                    "dump_root": "dcache_sweeps/mshr_buffer_len",
                    "test_name": "mshr_2",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {"mshr_buffer_len": 4},
                "sim": {
                    "dump_root": "dcache_sweeps/mshr_buffer_len",
                    "test_name": "mshr_4",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {"mshr_buffer_len": 8},
                "sim": {
                    "dump_root": "dcache_sweeps/mshr_buffer_len",
                    "test_name": "mshr_8",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {"mshr_buffer_len": 16},
                "sim": {
                    "dump_root": "dcache_sweeps/mshr_buffer_len",
                    "test_name": "mshr_16",
                },
            },
        ),
    ],

    "cache_size": [
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "sim": {
                    "dump_root": "dcache_sweeps/cache_size",
                    "test_name": "baseline",
                }
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 8,
                    "num_ways": 8,
                    "block_size_words": 32,
                    "cache_size": 16384,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/cache_size",
                    "test_name": "cache_16kb",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 16,
                    "num_ways": 8,
                    "block_size_words": 32,
                    "cache_size": 32768,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/cache_size",
                    "test_name": "cache_32kb",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 32,
                    "num_ways": 8,
                    "block_size_words": 32,
                    "cache_size": 65536,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/cache_size",
                    "test_name": "cache_64kb",
                },
            },
        ),
        deep_update(
            DEFAULT_SM_CONFIG,
            {
                "dcache": {
                    "num_banks": 2,
                    "num_sets_per_bank": 64,
                    "num_ways": 8,
                    "block_size_words": 32,
                    "cache_size": 131072,
                },
                "sim": {
                    "dump_root": "dcache_sweeps/cache_size",
                    "test_name": "cache_128kb",
                },
            },
        ),
    ],
}
    
    return dcache_sweep 

def run_sweep(
    fmt: str = "bin",
    sweep_configs: Optional[List[Dict[str, Any]]] = None,
    max_global_cycles: int = 10000,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    configs = sweep_configs or build_sweep_configs()

    sms: List[SM] = [
        SM(sm_id=i, fmt=fmt, config=cfg)
        for i, cfg in enumerate(configs)
    ]

    global_cycle = 0
    while global_cycle < max_global_cycles:
        unfinished = [sm for sm in sms if not sm.finished]
        if not unfinished: # if it is finished 
            break
        
        for sm in unfinished:
            sm.tick()

        global_cycle += 1

        if verbose and global_cycle % 100 == 0:
            done = sum(1 for sm in sms if sm.finished)
            print(f"[sweep] global_cycle={global_cycle} done={done}/{len(sms)}")

    # dump every SM after the sweep loop
    dump_paths = {}
    for sm in sms:
        dump_paths[sm.sm_id] = sm.dump_files()

    results = []
    for sm in sms:
        results.append(
            {
                "sm_id": sm.sm_id,
                "mem_latency": sm.config["mem"]["latency"],
                "finished": sm.finished,
                "cycles": sm.cycle,
                "icache_assoc": sm.config["icache"]["associativity"],
                "dcache_ways": sm.config["dcache"]["num_ways"],
                "dcache_hit_latency": sm.config["dcache"]["hit_latency"],
                "dcache_num_banks": sm.config["dcache"]["num_banks"],
                "dump_file": [str(dump_paths[sm.sm_id][0]), str(dump_paths[sm.sm_id][1])]
            }
        )

    results.sort(key=lambda x: (not x["finished"], x["cycles"]))
    return results

def print_sweep_results(results: List[Dict[str, Any]]) -> None:
    print("\n===== SWEEP RESULTS =====")
    for r in results:
        status = "DONE" if r["finished"] else "TIMEOUT"
        print(
            f"SM {r['sm_id']:02d} | {status:7s} | "
            f"MEM LAT={r['mem_latency']} | "
            f"cycles={r['cycles']:5d} | "
            f"I$ assoc={r['icache_assoc']} | "
            f"D$ ways={r['dcache_ways']} | "
            f"D$ hit_lat={r['dcache_hit_latency']} | "
            f"D$ banks={r['dcache_num_banks']} | "
            f"dump={r['dump_file']}"
        )

def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "program",
        nargs="?",
        default="gpu/tests/simulator/integration3/test_binaries/vertex_shader_pranav.bin",
    )
    parser.add_argument("--fmt", choices=["bin", "hex"], default="bin")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    # can enter toml file of configs to be turned into a list of dicts to sweep over, or just hardcode some in build_sweep_configs()
    results = run_sweep(
        fmt=args.fmt,
        sweep_configs=build_sweep_configs(),
        max_global_cycles=len(build_sweep_configs()) * 100000,  # heuristic: allow 5000 cycles per config
        verbose=not args.quiet,
    )
    print_sweep_results(results)
    