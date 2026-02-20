from __future__ import annotations

from simulator.execute.functional_unit import IntUnitConfig, FpUnitConfig, SpecialUnitConfig
from simulator.execute.stage import ExecuteStage, FunctionalUnitConfig
from simulator.writeback.stage import WritebackStage, WritebackBufferConfig, RegisterFileConfig
from simulator.issue.regfile import RegisterFile
from simulator.latch_forward_stage import Instruction, LatchIF
from simulator.issue.stage import IssueStage
from bitstring import Bits
from gpu.common.custom_enums_multi import R_Op, I_Op, F_Op
import math

#Yash and Dan
import sys
from pathlib import Path
FILE_ROOT = Path(__file__).resolve().parent
gpu_sim_root = Path(__file__).resolve().parents[3]
sys.path.append(str(gpu_sim_root))
from simulator.latch_forward_stage import LatchIF, Instruction, ForwardingIF, Stage, DecodeType
from gpu.common.custom_enums_multi import Instr_Type, R_Op, I_Op, F_Op, S_Op, B_Op, U_Op, J_Op, P_Op, H_Op
from common.custom_enums import Op
from simulator.scheduler.scheduler import SchedulerStage
from simulator.mem.icache_stage import ICacheStage
from simulator.mem.mem_controller import MemController
from simulator.mem.Memory import Mem
from simulator.decode.decode_class import DecodeStage
from simulator.decode.predicate_reg_file import PredicateRegFile
from simulator.latch_forward_stage import *
from datetime import datetime
from typing import Iterable, Any

START_PC = 0x1000
LAT = 2
WARP_COUNT = 6

def compare_register_files(pipeline_rf, golden_rf, warp_id=0, reg_list=None, verbose=False):
    """
    Compare two register files and return True if they match, False otherwise.
    """
    mismatches = []
    bank = warp_id % pipeline_rf.banks
    warp_idx = warp_id // 2
    
    # Determine which registers to check
    if reg_list is None:
        reg_range = range(pipeline_rf.regs_per_warp)
    else:
        reg_range = reg_list
    
    for reg_num in reg_range:
        for thread_id in range(pipeline_rf.threads_per_warp):
            pipeline_val = pipeline_rf.regs[bank][warp_idx][reg_num][thread_id]
            golden_val = golden_rf.regs[bank][warp_idx][reg_num][thread_id]
            
            # For float registers (typically >= 10 in our test), allow small tolerance
            is_float_reg = reg_num >= 50 or (reg_num >= 10 and reg_num < 20)
            
            # Special handling for trig/isqrt results which have higher error margins in CORDIC/FastApprox
            is_approx_reg = reg_num in [54, 55, 56] # SIN, COS, ISQRT

            if is_float_reg:
                p_float = pipeline_val.float
                g_float = golden_val.float
                
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
            if m['reg'] >= 50 or (m['reg'] >= 10 and m['reg'] < 20):
                print(f"  Reg[{m['reg']}][{m['thread']}]: "
                      f"Pipe={m['pipeline'].float:.6f} "
                      f"Gold={m['golden'].float:.6f} "
                      f"Diff={m.get('diff', 0):.6f}")
            else:
                print(f"  Reg[{m['reg']}][{m['thread']}]: "
                      f"Pipe={m['pipeline'].int} "
                      f"Gold={m['golden'].int}")

    return len(mismatches) == 0

def test_all_operations():
    """
    Comprehensive test of all supported operations using a continuous instruction stream.
    """
    print("\nComprehensive Pipeline Test - Continuous Stream Mode")
    print("-" * 60)
    
    # 1. Setup Pipeline Components
    # ---------------------------------------------------------
    tbs_ws_if = LatchIF("Thread Block Scheduler - Warp Scheduler Latch")
    sched_icache_if = LatchIF("Sched-ICache Latch")
    icache_mem_req_if = LatchIF("ICache-Mem Latch")
    dummy_dcache_mem_req_if = LatchIF("Dummy DCache-Mem Latch")
    mem_icache_resp_if = LatchIF("Mem-ICache Latch")
    dummy_dcache_mem_resp_if = LatchIF("Mem-Dummy DCache Latch")
    icache_decode_if = LatchIF("ICache-Decode Latch")
    decode_issue_if = LatchIF("Decode-Issue Latch")
    icache_scheduler_fwif = ForwardingIF(name = "icache_forward_if")
    decode_scheduler_fwif = ForwardingIF(name = "decode_forward_if")
    issue_scheduler_fwif = ForwardingIF(name = "issue_forward_if")
    branch_scheduler_fwif = ForwardingIF(name = "branch_forward_if")
    writeback_scheduler_fwif = ForwardingIF(name = "Writeback_forward_if")

    mem = Mem(
        start_pc=0x1000,
        input_file = FILE_ROOT / "no_eop.bin",
        fmt="bin",
    )

    memc = MemController(
        name="Mem_Controller",
        ic_req_latch=icache_mem_req_if,
        dc_req_latch=dummy_dcache_mem_req_if,
        ic_serve_latch=mem_icache_resp_if,
        dc_serve_latch=dummy_dcache_mem_resp_if,
        mem_backend=mem, 
        latency=LAT,
        policy="rr"
    )

    functional_unit_config = FunctionalUnitConfig.get_default_config()
    fust = functional_unit_config.generate_fust_dict()

    scheduler_stage = SchedulerStage(
        name="Scheduler_Stage",
        behind_latch=tbs_ws_if,
        ahead_latch=sched_icache_if,
        forward_ifs_read= {"ICache_Scheduler" : icache_scheduler_fwif, "Decode_Scheduler": decode_scheduler_fwif, "Issue_Scheduler": issue_scheduler_fwif, "Branch_Scheduler": branch_scheduler_fwif, "Writeback_Scheduler": writeback_scheduler_fwif},
        forward_ifs_write=None,
        start_pc=START_PC, 
        warp_count=WARP_COUNT
    )

    icache_stage = ICacheStage(
        name="ICache_Stage",
        behind_latch=sched_icache_if,
        ahead_latch=icache_decode_if,
        mem_req_if=icache_mem_req_if,
        mem_resp_if=mem_icache_resp_if,
        cache_config={"cache_size": 32 * 1024, 
                        "block_size": 4, 
                        "associativity": 1},
        forward_ifs_write= {"ICache_Scheduler": icache_scheduler_fwif},
    )

    prf = PredicateRegFile(
        num_preds_per_warp=16,
        num_warps=16
    )

    decode_stage = DecodeStage(
        name="Decode Stage",
        behind_latch=icache_decode_if,
        ahead_latch=decode_issue_if,
        prf=prf,
        fust=fust,
        forward_ifs_read={"ICache_Decode_Ihit": icache_scheduler_fwif},
        forward_ifs_write={"Decode_Scheduler_Pckt": decode_scheduler_fwif}
    )
    
    pipeline_rf = RegisterFile()
    golden_rf = RegisterFile()
    
    is_ex_latch = LatchIF(name="IS_EX_Latch")
    
    ex_stage = ExecuteStage.create_pipeline_stage(
        functional_unit_config=functional_unit_config, 
        fust=fust
    )
    ex_stage.behind_latch = is_ex_latch
    
    wb_buffer_config = WritebackBufferConfig.get_default_config()
    wb_buffer_config.validate_config(fsu_names=list(fust.keys()))
    reg_file_config = RegisterFileConfig.get_config_from_reg_File(reg_file=pipeline_rf)
    
    wb_stage = WritebackStage.create_pipeline_stage(
        wb_config=wb_buffer_config,
        rf_config=reg_file_config,
        ex_stage_ahead_latches=ex_stage.ahead_latches,
        reg_file=pipeline_rf,
        fsu_names=list(fust.keys())
    )
    
    issue_stage = IssueStage(
        fust_latency_cycles=1,
        regfile=pipeline_rf,
        fust=fust,
        name="IssueStage",
        behind_latch=decode_issue_if,
        ahead_latch=is_ex_latch,
        forward_ifs_read=None,
        forward_ifs_write=None
    )
    
    # 2. Initialize Register Data
    # ---------------------------------------------------------
    warp_id = 0
    test_values = {
        # Integer registers
        # 1: [0 + i for i in range(pipeline_rf.threads_per_warp)],
        # 2: [5 + i for i in range(pipeline_rf.threads_per_warp)],
        # 3: [3 for _ in range(pipeline_rf.threads_per_warp)],
        # 4: [2 for _ in range(pipeline_rf.threads_per_warp)],
        # 5: [-5 - i for i in range(pipeline_rf.threads_per_warp)],
        # # Floating point registers
        # 10: [10.5 + i*0.5 for i in range(pipeline_rf.threads_per_warp)],
        # 11: [2.5 + i*0.25 for i in range(pipeline_rf.threads_per_warp)],
        # 12: [1.57 for _ in range(pipeline_rf.threads_per_warp)],
        # 13: [4.0 for _ in range(pipeline_rf.threads_per_warp)],

        # integration2 test
        2: [5 for i in range(pipeline_rf.threads_per_warp)],
        3: [5 for i in range(pipeline_rf.threads_per_warp)]
    }

    imm_test_value = Bits(int=5, length=32)  # Immediate value for I-type instructions
    
    for reg_num, values in test_values.items():
        if reg_num >= 10:
            data = [Bits(float=v, length=32) for v in values]
        else:
            data = [Bits(int=v, length=32) for v in values]
        
        pipeline_rf.write_warp_gran(warp_id=warp_id, dest_operand=Bits(uint=reg_num, length=32), data=data)
        golden_rf.write_warp_gran(warp_id=warp_id, dest_operand=Bits(uint=reg_num, length=32), data=data)

    # 3. Define Test Cases
    # ---------------------------------------------------------
    test_cases = [
        # Integer ALU (20-31)
        ("ADD", R_Op.ADD, 2, 3, 1, "Alu_int_0", lambda a, b: (a + b) & 0xFFFFFFFF)
        # ("MUL", R_Op.MUL, 1, 2, 22, "Mul_int_0", lambda a, b: (a * b) & 0xFFFFFFFF),
        # ("DIV", R_Op.DIV, 1, 2, 23, "Div_int_0", lambda a, b: (a // b) if b != 0 else 0),
        # ("AND", R_Op.AND, 1, 2, 24, "Alu_int_0", lambda a, b: a & b),
        # ("OR", R_Op.OR, 1, 2, 25, "Alu_int_0", lambda a, b: a | b),
        # ("XOR", R_Op.XOR, 1, 2, 26, "Alu_int_0", lambda a, b: a ^ b),
        # ("SLT", R_Op.SLT, 1, 5, 27, "Alu_int_0", lambda a, b: 1 if a < b else 0),
        # ("SLTU", R_Op.SLTU, 1, 2, 28, "Alu_int_0", lambda a, b: 1 if (a & 0xFFFFFFFF) < (b & 0xFFFFFFFF) else 0),
        # ("SLL", R_Op.SLL, 1, 3, 29, "Alu_int_0", lambda a, b: (a << b) & 0xFFFFFFFF if b < 32 else 0),
        # ("SRL", R_Op.SRL, 1, 3, 30, "Alu_int_0", lambda a, b: ((a & 0xFFFFFFFF) >> b) if b < 32 else 0),
        # ("SRA", R_Op.SRA, 5, 3, 31, "Alu_int_0", lambda a, b: (a >> b) if b < 32 else 0),
        
        # # Integer Immediate (32-40)
        # ("ADDI", I_Op.ADDI, 1, 4, 32, "Alu_int_0", lambda a, b: (a + b) & 0xFFFFFFFF),
        # ("SUBI", I_Op.SUBI, 1, 4, 33, "Alu_int_0", lambda a, b: (a - b) & 0xFFFFFFFF),
        # ("ORI", I_Op.ORI, 1, 3, 34, "Alu_int_0", lambda a, b: a | b),
        # ("XORI", I_Op.XORI, 1, 3, 35, "Alu_int_0", lambda a, b: a ^ b),
        # ("SLTI", I_Op.SLTI, 1, 4, 36, "Alu_int_0", lambda a, b: 1 if a < b else 0),
        # ("SLTIU", I_Op.SLTIU, 1, 4, 37, "Alu_int_0", lambda a, b: 1 if (a & 0xFFFFFFFF) < (b & 0xFFFFFFFF) else 0),
        # ("SLLI", I_Op.SLLI, 1, 3, 38, "Alu_int_0", lambda a, b: (a << b) & 0xFFFFFFFF if b < 32 else 0),
        # ("SRLI", I_Op.SRLI, 1, 3, 39, "Alu_int_0", lambda a, b: ((a & 0xFFFFFFFF) >> b) if b < 32 else 0),
        # ("SRAI", I_Op.SRAI, 5, 3, 40, "Alu_int_0", lambda a, b: (a >> b) if b < 32 else 0),
        
        # # Floating Point (50-53)
        # ("ADDF", R_Op.ADDF, 10, 11, 50, "AddSub_float_0", lambda a, b: a + b),
        # ("SUBF", R_Op.SUBF, 10, 11, 51, "AddSub_float_0", lambda a, b: a - b),
        # ("MULF", R_Op.MULF, 10, 11, 52, "Mul_float_0", lambda a, b: a * b),
        # ("DIVF", R_Op.DIVF, 10, 11, 53, "Div_float_0", lambda a, b: a / b if b != 0.0 else 0.0),
        
        # # Special Functions (54-56)
        # ("SIN", F_Op.SIN, 12, 12, 54, "Trig_float_0", None),
        # ("COS", F_Op.COS, 12, 12, 55, "Trig_float_0", None),
        # ("ISQRT", F_Op.ISQRT, 13, 13, 56, "InvSqrt_float_0", None),
    ]

    # 4. Update Golden Model
    # ---------------------------------------------------------
    instruction_list = []
    
    print("Computing golden reference...")
    
    for test_name, opcode, rs1_reg, rs2_reg, rd_reg, intended_fu, python_op in test_cases:
        if intended_fu not in fust:
            print(f"  Warning: Skipping {test_name} (FU {intended_fu} not configured)")
            continue
        
        # --- A. Update Golden Model ---
        bank = warp_id % golden_rf.banks
        w_idx = warp_id // 2
        rs1_vals = golden_rf.regs[bank][w_idx][rs1_reg]
        rs2_vals = golden_rf.regs[bank][w_idx][rs2_reg]
        golden_res = []

        if isinstance(opcode, I_Op): # if opcode is for an immediate type
            imm_val = imm_test_value
            rs2_vals = None

        for i in range(golden_rf.threads_per_warp):
            # 1. Special Functions
            if test_name == "SIN":
                res = math.sin(rs1_vals[i].float)
                golden_res.append(Bits(float=res, length=32))
            elif test_name == "COS":
                res = math.cos(rs1_vals[i].float)
                golden_res.append(Bits(float=res, length=32))
            elif test_name == "ISQRT":
                val = rs1_vals[i].float
                res = 0.0 if val <= 0 else 1.0 / math.sqrt(val)
                golden_res.append(Bits(float=res, length=32))
            # 2. Float Ops
            elif rd_reg >= 50: 
                res = python_op(rs1_vals[i].float, rs2_vals[i].float)
                golden_res.append(Bits(float=res, length=32))
            elif isinstance(opcode, I_Op): # Immediate ops
                res = python_op(rs1_vals[i].int, imm_val.int)
                if res < 0:
                    golden_res.append(Bits(int=res, length=32))
                else:
                    golden_res.append(Bits(uint=res & 0xFFFFFFFF, length=32))
            # 3. Int Ops
            else:
                res = python_op(rs1_vals[i].int, rs2_vals[i].int)
                if res < 0:
                    golden_res.append(Bits(int=res, length=32))
                else:
                    golden_res.append(Bits(uint=res & 0xFFFFFFFF, length=32))

        golden_rf.write_warp_gran(
            # warp_id=rd_reg % 2,
            warp_id=warp_id,
            dest_operand=Bits(uint=rd_reg, length=32),
            data=golden_res
        )

        # # --- B. Create Pipeline Instruction ---
        # instr = Instruction(
        #     pc=Bits(uint=0x0, length=32),
        #     intended_FU=intended_fu,
        #     warp_id=rd_reg % 2,
        #     warp_group_id=0,
        #     num_operands=1 if isinstance(opcode, I_Op) else 2,
        #     rs1=Bits(uint=rs1_reg, length=32),
        #     rs2=Bits(uint=rs2_reg, length=32),
        #     rd=Bits(uint=rd_reg, length=32),
        #     wdat=[Bits(uint=0, length=32) for _ in range(pipeline_rf.threads_per_warp)],
        #     opcode=opcode,
        #     predicate=[Bits(uint=1, length=1) for _ in range(pipeline_rf.threads_per_warp)],
        #     target_bank=rd_reg % 2,
        #     imm=imm_val if isinstance(opcode, I_Op) else None
        # )

        # instruction_list.append(instr)
        # print(instr.target_bank)

    # print(f"Generated {len(instruction_list)} instructions.")


    # (TALK TO DAN AND YASH abt this)
    # 4.5 Initialize Forward IFs with Filler Payloads
    # ---------------------------------------------------------
    # Bootstrap the scheduler by providing neutral control packets
    # so collision() never sees None on the first cycle
    filler_decode_scheduler = {"type": DecodeType.MOP, "warp_id": 0, "pc": 0}
    filler_issue_scheduler = [0] * scheduler_stage.num_groups
    # Initialize all forward interfaces
    icache_scheduler_fwif.payload = None
    decode_scheduler_fwif.push(filler_decode_scheduler)
    issue_scheduler_fwif.push(filler_issue_scheduler)
    branch_scheduler_fwif.payload = None
    writeback_scheduler_fwif.payload = None

    # 5. Run Pipeline Simulation
    # ---------------------------------------------------------
    print("\nStarting pipeline simulation...")
    
    # Cycle 1: Feed instructions
    for idx, instr in enumerate(instruction_list):
        if instr.rd.uint == 1:
            abcHI = 1
        
        wb_stage.tick()
        ex_stage.tick()
        ex_stage.compute()
        issue_stage.compute()
        decode_stage.compute()
        memc.compute()
        icache_stage.compute()
        scheduler_stage.compute()

    print("All instructions issued. Flushing pipeline...")

    FLUSH_CYCLES = 100
    for _ in range(FLUSH_CYCLES):
        # Refill forward IFs if they get drained
        if issue_scheduler_fwif.payload is None:
            issue_scheduler_fwif.push(filler_issue_scheduler)
        if decode_scheduler_fwif.payload is None:
            decode_scheduler_fwif.push(filler_decode_scheduler)
        
        wb_stage.tick()
        ex_stage.tick()
        ex_stage.compute()
        issue_stage.compute()
        decode_stage.compute()
        memc.compute()
        icache_stage.compute()
        scheduler_stage.compute()

    print("Pipeline flush complete.")

    # 6. Verify Results
    # ---------------------------------------------------------
    print("\nVerifying Register File State...")
    
    # We check all destination registers that were written to
    # Int Ops: 20-40, Float Ops: 50-56
    # regs_to_check = list(range(20, 41)) + list(range(50, 57))
    regs_to_check = list(range(0, 63))
    
    passed = compare_register_files(
        pipeline_rf=pipeline_rf,
        golden_rf=golden_rf,
        warp_id=warp_id,
        reg_list=regs_to_check,
        verbose=True
    )

    pipeline_rf.dump()
    golden_rf.dump()

    if passed:
        print("\n✅ SUCCESS: All register values match golden model.")
        return len(instruction_list), 0
    else:
        print("\n❌ FAILURE: Mismatches detected in register file.")
        return 0, 1


if __name__ == "__main__":
    passed, failed = test_all_operations()
    exit(0 if failed == 0 else 1)