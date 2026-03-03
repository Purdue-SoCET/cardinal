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
    """
    Load a program file and return a list of 32-bit instruction words
    (as plain Python ints) in program order.

    Parameters
    ----------
    file_path : Path
        Path to the instruction file.
    fmt : {"bin", "hex"}
        "bin"  – each line is a 32-character '0'/'1' string
        "hex"  – each line is either:
                   • 8 hex characters  (e.g.  40184080)
                   • "0xADDR 0xDATA"   (e.g.  0x00001000 0x40184080)
    """
    words: List[int] = []
    with file_path.open("r", encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh, start=1):
            # strip inline comments
            for marker in ("//", "#"):
                idx = raw_line.find(marker)
                if idx != -1:
                    raw_line = raw_line[:idx]
            line = raw_line.strip().replace("_", "")
            if not line:
                continue

            if fmt == "bin":
                if len(line) != 32 or not all(c in "01" for c in line):
                    raise ValueError(
                        f"[load_program] line {line_no}: expected 32-bit binary string, "
                        f"got {line!r}"
                    )
                words.append(int(line, 2))

            elif fmt == "hex":
                parts = line.split()
                if len(parts) == 2:
                    # "0xADDR 0xDATA" style – we only care about DATA
                    words.append(int(parts[1], 16) & 0xFFFF_FFFF)
                elif len(parts) == 1:
                    if len(parts[0]) != 8:
                        raise ValueError(
                            f"[load_program] line {line_no}: expected 8 hex chars, "
                            f"got {parts[0]!r}"
                        )
                    words.append(int(parts[0], 16) & 0xFFFF_FFFF)
                else:
                    raise ValueError(
                        f"[load_program] line {line_no}: unexpected token count: {line!r}"
                    )
            else:
                raise ValueError(f"Unknown format {fmt!r}; use 'bin' or 'hex'")

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
#  Golden-model computation
# ==============================================================================

def _is_float_op(dec: dict) -> bool:
    """Return True if the instruction produces a floating-point result."""
    op = dec["opcode_enum"]
    return (
        (dec["is_F"])
        or op in (R_Op.ADDF, R_Op.SUBF, R_Op.MULF, R_Op.DIVF)
    )


def compute_golden_result(
    dec:              dict,
    rs1_vals:         list,   # List[Bits], one per thread
    rs2_vals:         list,   # List[Bits], one per thread (None for I/F/C)
    threads_per_warp: int,
    csr_table:        CsrTable,
    kernel_base_ptrs: KernelBasePointers,
    warp_id:          int,
) -> Optional[List[Bits]]:
    """
    Compute the per-thread golden result for one decoded instruction.

    Returns a list of Bits (one per thread), or None if the instruction does
    not write to rd (stores, branches, halts, etc.).
    """
    op  = dec["opcode_enum"]
    imm = Bits(uint=dec["imm"], length=6)     # 6-bit signed immediate

    # Instructions that don't write to rd
    if dec["is_S"] or dec["is_B"] or dec["is_H"] or dec["is_J"] or dec["is_P"]:
        return None
    if op is None:
        return None

    results: List[Bits] = []

    for i in range(threads_per_warp):
        a = rs1_vals[i]   # Bits

        # ── C-type: CSRR ────────────────────────────────────────────────────
        if dec["is_C"] and op == C_Op.CSRR:
            csr_param = dec["rs1"]    # rs1 field carries the CSR selector
            if csr_param == 0:
                csr_val = int(csr_table.read_base_id(warp_id)) + i
            elif csr_param == 1:
                csr_val = int(csr_table.read_tb_id(warp_id))
            elif csr_param == 2:
                csr_val = int(csr_table.read_tb_size(warp_id))
            elif csr_param == 3:
                csr_val = kernel_base_ptrs.read(0).uint
            else:
                csr_val = 0
            results.append(Bits(uint=csr_val & 0xFFFF_FFFF, length=32))
            continue

        # ── F-type: SIN / COS / ISQRT ───────────────────────────────────────
        if dec["is_F"]:
            af = a.float
            if op == F_Op.SIN:
                res = math.sin(af)
            elif op == F_Op.COS:
                res = math.cos(af)
            elif op == F_Op.ISQRT:
                res = 0.0 if af <= 0.0 else 1.0 / math.sqrt(af)
            elif op == F_Op.ITOF:
                res = float(a.int)
            elif op == F_Op.FTOI:
                # result is integer even though input is float
                int_res = int(af)
                results.append(Bits(int=int_res & 0xFFFF_FFFF if int_res < 0
                                     else int_res & 0xFFFF_FFFF, length=32))
                continue
            else:
                res = 0.0
            results.append(Bits(float=res, length=32))
            continue

        # ── R-type float: ADDF / SUBF / MULF / DIVF ─────────────────────────
        if dec["is_R"] and op in (R_Op.ADDF, R_Op.SUBF, R_Op.MULF, R_Op.DIVF):
            b = rs2_vals[i]
            af, bf = a.float, b.float
            if op == R_Op.ADDF:
                res = af + bf
            elif op == R_Op.SUBF:
                res = af - bf
            elif op == R_Op.MULF:
                res = af * bf
            else:  # DIVF
                res = af / bf if bf != 0.0 else 0.0
            results.append(Bits(float=res, length=32))
            continue

        # ── R-type integer ───────────────────────────────────────────────────
        if dec["is_R"]:
            b = rs2_vals[i]
            ai, bi = a.int, b.int
            au, bu = a.uint, b.uint
            if op == R_Op.ADD:
                res = (ai + bi) & 0xFFFF_FFFF
            elif op == R_Op.SUB:
                res = (ai - bi) & 0xFFFF_FFFF
            elif op == R_Op.MUL:
                res = (ai * bi) & 0xFFFF_FFFF
            elif op == R_Op.DIV:
                res = (ai // bi) & 0xFFFF_FFFF if bi != 0 else 0
            elif op == R_Op.AND:
                res = au & bu
            elif op == R_Op.OR:
                res = au | bu
            elif op == R_Op.XOR:
                res = au ^ bu
            elif op == R_Op.SLT:
                res = 1 if ai < bi else 0
            elif op == R_Op.SLTU:
                res = 1 if au < bu else 0
            elif op == R_Op.SLL:
                res = (au << bi) & 0xFFFF_FFFF if bi < 32 else 0
            elif op == R_Op.SRL:
                res = (au >> bi) if bi < 32 else 0
            elif op == R_Op.SRA:
                res = (ai >> bi) & 0xFFFF_FFFF if bi < 32 else (0 if ai >= 0 else 0xFFFF_FFFF)
            else:
                res = 0
            # sign-extend / keep as unsigned depending on result
            if res > 0x7FFF_FFFF:
                results.append(Bits(uint=res & 0xFFFF_FFFF, length=32))
            else:
                results.append(Bits(int=res, length=32) if res < 0
                                else Bits(uint=res, length=32))
            continue

        # ── I-type integer ───────────────────────────────────────────────────
        if dec["is_I"]:
            # imm is 6-bit unsigned from the field; sign-extend to 32-bit int
            imm_int = imm.int   # 6-bit signed
            ai = a.int
            au = a.uint
            if op == I_Op.ADDI:
                res = (ai + imm_int) & 0xFFFF_FFFF
            elif op == I_Op.SUBI:
                res = (ai - imm_int) & 0xFFFF_FFFF
            elif op == I_Op.ORI:
                res = au | (imm_int & 0xFFFF_FFFF)
            elif op == I_Op.XORI:
                res = au ^ (imm_int & 0xFFFF_FFFF)
            elif op == I_Op.SLTI:
                res = 1 if ai < imm_int else 0
            elif op == I_Op.SLTIU:
                res = 1 if au < (imm_int & 0xFFFF_FFFF) else 0
            elif op == I_Op.SLLI:
                sh = imm_int & 0x1F
                res = (au << sh) & 0xFFFF_FFFF
            elif op == I_Op.SRLI:
                sh = imm_int & 0x1F
                res = au >> sh
            elif op == I_Op.SRAI:
                sh = imm_int & 0x1F
                res = (ai >> sh) & 0xFFFF_FFFF
            else:
                # load / jalr: no golden RF update from instruction stream alone
                results.append(Bits(uint=0, length=32))
                continue
            results.append(Bits(uint=res & 0xFFFF_FFFF, length=32))
            continue

        # ── U-type ───────────────────────────────────────────────────────────
        if dec["is_U"]:
            # Upper-immediate instructions (LUI, AUIPC, LLI, LMI)
            # imm field is only 6 bits here; full logic requires wider field
            # For now append zero to avoid crashing; extend as needed.
            results.append(Bits(uint=0, length=32))
            continue

        # fallback
        results.append(Bits(uint=0, length=32))

    return results


# ==============================================================================
#  Register-file comparison
# ==============================================================================

def compare_register_files(pipeline_rf, golden_rf, warp_id=0, reg_list=None, verbose=False):
    """
    Compare two register files and return True if they match, False otherwise.
    """
    mismatches = []
    if warp_id < 0:
        raise ValueError(f"warp_id must be >= 0, got {warp_id}")
    if warp_id >= pipeline_rf.warps:
        raise ValueError(f"warp_id {warp_id} out of range for pipeline_rf.warps={pipeline_rf.warps}")
    if warp_id >= golden_rf.warps:
        raise ValueError(f"warp_id {warp_id} out of range for golden_rf.warps={golden_rf.warps}")
    
    # Determine which registers to check
    if reg_list is None:
        reg_range = range(pipeline_rf.regs_per_warp)
    else:
        reg_range = reg_list
    
    for reg_num in reg_range:
        if reg_num < 0 or reg_num >= pipeline_rf.regs_per_warp:
            raise ValueError(
                f"reg_num {reg_num} out of range for pipeline_rf.regs_per_warp={pipeline_rf.regs_per_warp}"
            )
        for thread_id in range(pipeline_rf.threads_per_warp):
            pipeline_val = pipeline_rf.read_thread_gran(
                warp_id=warp_id,
                src_operand=Bits(uint=reg_num, length=32),
                thread_id=thread_id,
            )
            golden_val = golden_rf.read_thread_gran(
                warp_id=warp_id,
                src_operand=Bits(uint=reg_num, length=32),
                thread_id=thread_id,
            )
            
            # For float registers (typically >= 10 in our test), allow small tolerance
            # Regs 57-60 hold integer CSR values even though they are > 50
            is_float_reg = (reg_num >= 50 and reg_num <= 56) or (reg_num >= 10 and reg_num < 20)
            
            # Special handling for trig/isqrt results which have higher error margins in CORDIC/FastApprox
            is_approx_reg = reg_num in [54, 55, 56] # SIN, COS, ISQRT

            if is_float_reg:
                if pipeline_val is not None:
                    p_float = pipeline_val.float
                else:                    p_float = float('nan')  # Treat None as NaN for comparison
                if golden_val is not None:  
                    g_float = golden_val.float
                else:                    g_float = float('nan')  # Treat None as NaN for comparison

                # Treat NaN == NaN for comparison purposes
                if math.isnan(p_float) and math.isnan(g_float):
                    continue
                
                # Dynamic tolerance based on operation type
                if is_approx_reg:
                     # 5% relative error for approx functions
                    tolerance = abs(g_float * 0.05) + 1e-4
                else:
                    # 1% relative error + epsilon for standard float
                    tolerance = abs(g_float * 0.01) + 1e-6

                if abs(p_float - g_float) > tolerance:
                    mismatches.append({
                        'reg': reg_num,
                        'thread': thread_id,
                        'pipeline': pipeline_val,
                        'golden': golden_val,
                        'diff': abs(p_float - g_float)
                    })
            else:
                if pipeline_val != golden_val:
                    mismatches.append({
                        'reg': reg_num,
                        'thread': thread_id,
                        'pipeline': pipeline_val,
                        'golden': golden_val
                    })
    
    if verbose and mismatches:
        print(f"\n❌ Found {len(mismatches)} mismatches:")
        for m in mismatches:
            is_float_display = (m['reg'] >= 50 and m['reg'] <= 56) or (m['reg'] >= 10 and m['reg'] < 20)
            if is_float_display:
                print(f"  Reg[{m['reg']}][{m['thread']}]: "
                      f"Pipe={m['pipeline'].float:.6f} "
                      f"Gold={m['golden'].float:.6f} "
                      f"Diff={m.get('diff', 0):.6f}")
            else:
                print(f"  Reg[{m['reg']}][{m['thread']}]: "
                      f"Pipe={m['pipeline'].uint} "
                      f"Gold={m['golden'].uint}")

    return len(mismatches) == 0

# ==============================================================================
#  Pipeline setup
# ==============================================================================

def build_pipeline(input_file: Path, fmt: str = "bin"):
    """Instantiate all pipeline stages and return them as a dict."""
    

    # Latches
    tbs_ws_if               = LatchIF("TBS-WS Latch")
    sched_icache_if         = LatchIF("Sched-ICache Latch")
    icache_mem_req_if       = LatchIF("ICache-Mem Latch")
    dummy_dcache_req_if     = LatchIF("Dummy-DCache-Mem Latch")
    mem_icache_resp_if      = LatchIF("Mem-ICache Latch")
    dummy_dcache_resp_if    = LatchIF("Mem-Dummy-DCache Latch")
    icache_decode_if        = LatchIF("ICache-Decode Latch")
    decode_issue_if         = LatchIF("Decode-Issue Latch")
    is_ex_latch             = LatchIF("IS-EX Latch")

    # Forwarding IFs
    icache_scheduler_fwif   = ForwardingIF(name="icache_forward_if")
    decode_scheduler_fwif   = ForwardingIF(name="decode_forward_if")
    issue_scheduler_fwif    = ForwardingIF(name="issue_forward_if")
    branch_scheduler_fwif   = ForwardingIF(name="branch_forward_if")
    writeback_scheduler_fwif = ForwardingIF(name="Writeback_forward_if")
    decode_issue_fwif       = ForwardingIF(name="Decode_issue_fwif")
    scheduler_ldst_fwif     = ForwardingIF(name="scheduler_ldst_fwif")

    mem = Mem(start_pc=START_PC, input_file=str(input_file), fmt=fmt)

    memc = MemController(
        name="Mem_Controller",
        ic_req_latch=icache_mem_req_if,
        dc_req_latch=dummy_dcache_req_if,
        ic_serve_latch=mem_icache_resp_if,
        dc_serve_latch=dummy_dcache_resp_if,
        mem_backend=mem,
        latency=MEM_LATENCY,
        policy="rr",
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
        },
        # forward_ifs_write=None,
        forward_ifs_write={"Scheduler_LDST": scheduler_ldst_fwif},
        csrtable = csr_table,
        warp_count=WARP_COUNT,
    )

    # NOTE Kai Ze: Remove after we bring in TBS
    tbs_ws_if.push([0, 1024, START_PC])

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
            for neg in range(2):
                prf.reg_file[warp][pred][neg] = [True] * 32

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
        "pipeline_rf": pipeline_rf,
        "golden_rf":   golden_rf,
        "csr_table":   csr_table,
        "kbp":         kernel_base_ptrs,
        "fust":        fust,
        "prf":         prf,
    }


def tick_all(p: dict):
    """Tick every pipeline stage once (same order as sm-no-mem.py)."""
    p["wb"].tick()
    p["ex"].tick()
    p["ex"].compute()
    p["issue"].compute()
    p["decode"].compute()
    p["memc"].compute()
    p["icache"].compute()
    p["scheduler"].compute()


def initialize_regfile(pipeline_rf, golden_rf, warp_ids, threads_per_warp, default=True):

    if (default):
        # ── initialise register files ─────────────────────────────────────────────
        for warp_id in warp_ids:
            test_vals = get_test_values(warp_id, threads_per_warp)
            for reg_num, values in test_vals.items():
                if reg_num >= 10:
                    data = [Bits(float=v, length=32) for v in values]
                else:
                    data = [Bits(int=v,   length=32) for v in values]
                pipeline_rf.write_warp_gran(warp_id=warp_id,
                                            dest_operand=Bits(uint=reg_num, length=32),
                                            data=data)
                golden_rf.write_warp_gran(warp_id=warp_id,
                                        dest_operand=Bits(uint=reg_num, length=32),
                                        data=data)

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
    }

def run_test(
    # program_file: Path = FILE_ROOT / "test.bin",
    # program_file: Path = FILE_ROOT / "test_binaries/jump.bin",
    program_file: Path = FILE_ROOT / "test_binaries/predicated_halt.bin",
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
    p = build_pipeline(program_file, fmt=fmt)
    pipeline_rf  = p["pipeline_rf"]
    golden_rf    = p["golden_rf"]
    csr_table    = p["csr_table"]
    kbp          = p["kbp"]
    prf = p["prf"]

    threads = pipeline_rf.threads_per_warp

    # ── warp IDs under test ───────────────────────────────────────────────────
    warp_ids = list(range(WARP_COUNT + (1 if WARP_COUNT % 2 else 0)))

    # these must be initialized differenly based on the test case 
    initialize_regfile(pipeline_rf, golden_rf, warp_ids, threads, default=True)

    # ── sanity-check: initial RF matches ─────────────────────────────────────
    print("\nVerifying initial register file state against golden model...")
    for warp_id in warp_ids:
        test_vals = get_test_values(warp_id, threads)
        if not compare_register_files(
            pipeline_rf, golden_rf,
            warp_id=warp_id, reg_list=list(test_vals.keys()), verbose=True
        ):
            print(f"❌ Initial mismatch for warp {warp_id}. Aborting.")
            return 0, 1
    print("✅ Initial register file state matches golden model.")

    # ── pipeline simulation ───────────────────────────────────────────────────
    n_instr = len(decoded_instrs)
    print(f"\nRunning pipeline: {n_instr} issue cycles ...")
    for cycle in range(n_instr):
        tick_all(p)

    FLUSH_CYCLES = n_instr + 1100
    print(f"Flushing pipeline ({FLUSH_CYCLES} cycles)...")
    for _ in range(FLUSH_CYCLES):
        tick_all(p)
    print("Flush complete.")
    print(p["scheduler"].warp_table)
    # print(pipeline_rf.regs[0][0])
    # print(prf.reg_file[0][1])
    # print()
    # print(prf.reg_file[0][2])
    # print()
    
    # ── golden model: compute expected results from decoded instructions ───────
    print("\nComputing golden reference from decoded instruction stream...")
    for warp_id in warp_ids:
        if verbose:
            print(f"  warp {warp_id} ...")
        for dec in decoded_instrs:
            if not dec["opcode_enum"]:
                continue
            rd = dec["rd"]

            # Fetch source operands from golden RF
            bank  = warp_id % golden_rf.banks
            w_idx = warp_id // 2
            rs1_regs = golden_rf.regs[bank][w_idx][dec["rs1"]]

            if dec["is_R"] or dec["is_S"] or dec["is_B"]:
                rs2_regs = golden_rf.regs[bank][w_idx][dec["rs2"]]
            else:
                rs2_regs = None

            result = compute_golden_result(
                dec=dec,
                rs1_vals=rs1_regs,
                rs2_vals=rs2_regs,
                threads_per_warp=threads,
                csr_table=csr_table,
                kernel_base_ptrs=kbp,
                warp_id=warp_id,
            )

            if result is not None:
                golden_rf.write_warp_gran(
                    warp_id=warp_id,
                    dest_operand=Bits(uint=rd, length=32),
                    data=result,
                )

    # ── dump register files to disk ───────────────────────────────────────────
    _REGS = list(range(0, 63))

    pipeline_out = FILE_ROOT / "pipeline_regfile_dump.txt"
    golden_out   = FILE_ROOT / "golden_regfile_dump.txt"
    prf_out     = FILE_ROOT / "predicate_regfile_dump.txt"

    with open(pipeline_out, "w", encoding="utf-8") as f:
            pipeline_rf.dump(file=f)
    with open(golden_out, "w", encoding="utf-8") as f:
        golden_rf.dump(file=f)
    with open(prf_out, "w", encoding="utf-8") as f:
        prf.dump(file=f)

    print(f"\nRegister file dumps written:")
    print(f"  Pipeline -> {pipeline_out}")
    print(f"  Golden   -> {golden_out}")
    print(f"  Predicate RF -> {prf_out}")

    # ── result verification ───────────────────────────────────────────────────
    # Collect the set of destination registers written by the program
    written_rds = set()
    for dec in decoded_instrs:
        if dec["opcode_enum"] and not (dec["is_S"] or dec["is_B"] or dec["is_H"]):
            written_rds.add(dec["rd"])

    regs_to_check = sorted(written_rds)
    print(f"\nVerifying {len(regs_to_check)} destination registers across "
          f"{len(warp_ids)} warps...")

    all_passed = True
    for warp_id in warp_ids:
        passed = compare_register_files(
            pipeline_rf=pipeline_rf,
            golden_rf=golden_rf,
            warp_id=warp_id,
            reg_list=regs_to_check,
            verbose=True,
        )
        if passed:
            print(f"  ✅ Warp {warp_id} PASSED")
        else:
            all_passed = False
            print(f"  ❌ Warp {warp_id} FAILED")

    if all_passed:
        print(f"\n✅ SUCCESS: All {len(warp_ids)} warps passed.")
        return len(warp_ids), 0
    else:
        print("\n❌ FAILURE: Mismatches detected.")
        return 0, 1


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
        default=str(FILE_ROOT / "test_binaries/predicated_halt.bin"),
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
    passed, failed = run_test(
        program_file=Path(args.program),
        fmt=args.fmt,
        verbose=not args.quiet,
    )
    sys.exit(0 if failed == 0 else 1)
