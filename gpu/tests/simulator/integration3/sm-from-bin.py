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
from simulator.csr_table import CsrTable
from simulator.kernel_base_pointers import KernelBasePointers
from simulator.scheduler.scheduler import SchedulerStage
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

# ==============================================================================
#  Pipeline setup
# ==============================================================================

def build_pipeline(input_file: Path, fmt: str = "bin", start_pc: int = 0x1000, tb_size: int = 1024):
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
    icache_scheduler_fwif   = ForwardingIF(name="icache_forward_if")
    decode_scheduler_fwif   = ForwardingIF(name="decode_forward_if")
    issue_scheduler_fwif    = ForwardingIF(name="issue_forward_if")
    branch_scheduler_fwif   = ForwardingIF(name="branch_forward_if")
    writeback_scheduler_fwif = ForwardingIF(name="Writeback_forward_if")
    decode_issue_fwif       = ForwardingIF(name="Decode_issue_fwif")
    scheduler_ldst_fwif     = ForwardingIF(name="scheduler_ldst_fwif")
    ldst_scheduler_fwif     = ForwardingIF(name="ldst_scheduler_fwif")

    mem = Mem(start_pc=start_pc, input_file=str(input_file), fmt=fmt)

    memc = MemController(
        name="Mem_Controller",
        ic_req_latch=icache_mem_req_if,
        dc_req_latch=dcache_mem_latch,
        ic_serve_latch=mem_icache_resp_if,
        dc_serve_latch=mem_dcache_latch,
        mem_backend=mem,
        latency=MEM_LATENCY,
        policy="rr",
    )

    # D-Cache stage
    dcache_stage = LockupFreeCacheStage(
        name="dCache",
        behind_latch=lsu_dcache_latch,
        forward_ifs_write={"DCache_LSU_Resp": dcache_lsu_forward},
        mem_req_if=dcache_mem_latch,
        mem_resp_if=mem_dcache_latch,
    )

    fu_config = FunctionalUnitConfig.get_default_config()
    fust      = fu_config.generate_fust_dict()

    csr_table = CsrTable()
    
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
            "LDST_Scheduler": ldst_scheduler_fwif
        },
        # forward_ifs_write=None,
        forward_ifs_write={"Scheduler_LDST": scheduler_ldst_fwif},
        csrtable = csr_table,
        warp_count=WARP_COUNT,
    )

    # NOTE Kai Ze: Remove after we bring in TBS
    tbs_ws_if.push([0, tb_size, start_pc])

    icache_stage = ICacheStage(
        name="ICache_Stage",
        behind_latch=sched_icache_if,
        ahead_latch=icache_decode_if,
        mem_req_if=icache_mem_req_if,
        mem_resp_if=mem_icache_resp_if,
        cache_config={"cache_size": 32 * 1024, "block_size": 4, "associativity": 1},
        forward_ifs_write={"ICache_Scheduler": icache_scheduler_fwif},
    )

    prf = PredicateRegFile(num_preds_per_warp=16, num_warps=WARP_COUNT)
    for warp in range(WARP_COUNT):
        for pred in range(16):
            prf.reg_file[warp][pred] = [True] * 32

    kernel_base_ptrs = KernelBasePointers(max_kernels_per_SM=1)
    kernel_base_ptrs.write(0, Bits(uint=9203930, length=32))

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
        fust=fust,
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

# ==============================================================================
#  Test driver
# ==============================================================================

def get_test_values(warp_id: int, threads_per_warp: int) -> dict:
    """Initial register values identical to sm-no-mem.py."""
    return {
        # 1:  [0  + i + warp_id for i in range(threads_per_warp)],
        # 2:  [5  + i + warp_id for i in range(threads_per_warp)],
        # 3:  [3  for _ in range(threads_per_warp)],
        # 4:  [2  for _ in range(threads_per_warp)],
        # 5:  [-5 - i + warp_id for i in range(threads_per_warp)],
        # 10: [10.5 + i * 0.5  + warp_id for i in range(threads_per_warp)],
        # 11: [2.5  + i * 0.25 + warp_id for i in range(threads_per_warp)],
        # 12: [1.57 for _ in range(threads_per_warp)],
        # 13: [4.0  for _ in range(threads_per_warp)],
        1: [31 - i for i in range(threads_per_warp)],
        2: [i for i in range(threads_per_warp)],
        8: [100 for i in range(threads_per_warp)],
        9: [100 for i in range(threads_per_warp)],
    }

# ==============================================================================
#  L/S unit + D-Cache integration test driver
# ==============================================================================
BLOCK_SIZE_WORDS = 32

def print_banks(dCache):
    # --- 1. Calculate Bit Widths for Reconstruction ---
    # Offset: 32 words * 4 bytes = 128 bytes -> 7 bits (usually)
    offset_bits = int(math.log2(BLOCK_SIZE_WORDS * 4))
    
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

                        for i in range(0, BLOCK_SIZE_WORDS, 4):
                            # FIX: Add '& 0xFFFFFFFF' to force unsigned 32-bit representation
                            w0 = f"0x{(frame.block[i] & 0xFFFFFFFF):08X}"
                            w1 = f"0x{(frame.block[i+1] & 0xFFFFFFFF):08X}"
                            w2 = f"0x{(frame.block[i+2] & 0xFFFFFFFF):08X}"
                            w3 = f"0x{(frame.block[i+3] & 0xFFFFFFFF):08X}"
                            
                            print(f"        Block[{i:02d}:{i+3:02d}]: {w0} {w1} {w2} {w3}")

        if not found_valid_line:
            print(f"  (Bank is empty)")

def run_test(
    # program_file: Path = FILE_ROOT / "test.bin",
    # program_file: Path = FILE_ROOT / "test_binaries/predicated_halt.bin", THESE DON'T MATTER
    program_file: Path = FILE_ROOT / "test_binaries/ldst_sequence.bin",
    fmt:          str  = "bin",
    verbose:      bool = True,
) -> tuple[int, int]:
    """
    Main entry point.

    Returns (passed_count, failed_count).
    """
    print(f"\nLoading program: {program_file}  (format={fmt})")
    
    words = load_program(program_file, fmt=fmt)

    # Decode the instruction stream (skip HALTs & instructions with no rd write)
    decoded_instrs = [decode_word(w) for w in words]
    print(f"Loaded {len(words)} instruction words, "
          f"{sum(1 for d in decoded_instrs if d['opcode_enum'] is not None)} decoded.")

    # ── build pipeline ────────────────────────────────────────────────────────
    p = build_pipeline(program_file, fmt=fmt, start_pc=0)
    pipeline_rf  = p["pipeline_rf"]
    golden_rf    = p["golden_rf"]
    csr_table    = p["csr_table"]
    kbp          = p["kbp"]
    prf = p["prf"]

    threads = pipeline_rf.threads_per_warp

    # ── warp IDs under test ───────────────────────────────────────────────────
    warp_ids = list(range(WARP_COUNT + (1 if WARP_COUNT % 2 else 0)))

    # ── pipeline simulation ───────────────────────────────────────────────────
    n_instr = len(decoded_instrs)
    print(f"\nRunning pipeline: {n_instr} issue cycles ...")
    for cycle in range(n_instr):
        tick_all(p)

    #FLUSH_CYCLES = n_instr + 2300
    #cycle = 0
    #print(f"Flushing pipeline ({FLUSH_CYCLES} cycles)...")
    #for _ in range(FLUSH_CYCLES):
    #    tick_all(p)
    #print("Flush complete.")

    cycle = 0
    print(f"Flushing pipeline")
    while not p["scheduler"].system_finished:
        tick_all(p)
        print(f"Cycle : {cycle}")
        cycle += 1
    print("Simulation complete.")
    
    print_banks(p["dcache"])
    pipeline_rf.dump()
    prf.dump()


# ==============================================================================
#  CLI
# ==============================================================================

def _parse_args():
    parser = argparse.ArgumentParser(
        description="Run GPU pipeline test driven by a binary/hex program file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "program",
        nargs="?",
        # default=str(FILE_ROOT / "test.bin"),
        # default=str(FILE_ROOT / "test_binaries/jump.bin"),
        # default=str(FILE_ROOT / "test_binaries/predicated_halt.bin"),
        default=str(FILE_ROOT / "test_binaries/ldst_sequence.bin"),
        help="Path to the program file (.bin or .hex).",
    )
    parser.add_argument(
        "--fmt", "-f",
        choices=["bin", "hex"],
        default="bin",
        help="File format: 'bin' (32-char binary strings) or 'hex' (8-char hex / 'addr data' pairs).",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress per-warp progress output.",
    )
    return parser.parse_args()

if __name__ == "__main__":
    args    = _parse_args()
    run_test(
        program_file=Path(args.program),
        fmt=args.fmt,
        verbose=not args.quiet,
    )
    sys.exit(0)

    # run_ldst_test(
    #     program_file=Path(args.program),
    #     fmt=args.fmt,
    # )
    # sys.exit(1)
    
