from __future__ import annotations

from simulator.execute.functional_unit import IntUnitConfig, FpUnitConfig, SpecialUnitConfig
from simulator.execute.stage import ExecuteStage, FunctionalUnitConfig
from simulator.writeback.stage import WritebackStage, WritebackBufferConfig, RegisterFileConfig
from simulator.issue.regfile import RegisterFile
from simulator.latch_forward_stage import Instruction, LatchIF
from simulator.issue.stage import IssueStage
from simulator.csr_table import CsrTable
from simulator.kernel_base_pointers import KernelBasePointers
from bitstring import Bits
import math

#Yash and Dan
import sys
from pathlib import Path
FILE_ROOT = Path(__file__).resolve().parent
gpu_sim_root = Path(__file__).resolve().parents[3]
sys.path.append(str(gpu_sim_root))
from simulator.latch_forward_stage import LatchIF, Instruction, ForwardingIF, Stage, DecodeType
from gpu.common.custom_enums_multi import Instr_Type, R_Op, I_Op, F_Op, S_Op, B_Op, U_Op, J_Op, P_Op, H_Op, C_Op
from gpu.common.custom_enums import Op
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
WARP_COUNT = 32

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
                p_float = pipeline_val.float
                g_float = golden_val.float

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
        start_pc=START_PC,
        input_file = FILE_ROOT / "test.bin",
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

    csr_table = CsrTable()

    scheduler_stage = SchedulerStage(
        name="Scheduler_Stage",
        behind_latch=tbs_ws_if,
        ahead_latch=sched_icache_if,
        forward_ifs_read= {"ICache_Scheduler" : icache_scheduler_fwif, "Decode_Scheduler": decode_scheduler_fwif, 
                           "Issue_Scheduler": issue_scheduler_fwif, "Branch_Scheduler": branch_scheduler_fwif, 
                           "Writeback_Scheduler": writeback_scheduler_fwif},
        forward_ifs_write=None,
        csrtable = csr_table,
        warp_count=WARP_COUNT
    )

    tbs_ws_if.push([0, 1024, START_PC])

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
        num_warps=WARP_COUNT
    )

    kernel_base_ptrs = KernelBasePointers(max_kernels_per_SM=1)
    kernel_base_ptrs.write(0, Bits(uint=9203930, length=32)) # random address for testing
    
    # Initialize all predicate registers to 1 (all threads active)
    for warp in range(WARP_COUNT):
        for pred in range(16 * 2):  # num_preds_per_warp * 2
            for neg in range(2):  # both positive and negative versions
                prf.reg_file[warp][pred][neg] = [True] * 32  # all 32 threads active

    decode_stage = DecodeStage(
        name="Decode Stage",
        behind_latch=icache_decode_if,
        ahead_latch=decode_issue_if,
        prf=prf,
        fust=fust,
        csr_table=csr_table,
        kernel_base_ptrs=kernel_base_ptrs,
        forward_ifs_read=None,
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
    ex_stage.functional_units['MemBranchJumpUnit_0'].subunits['Jump_0'].schedule_if = branch_scheduler_fwif
    
    wb_buffer_config = WritebackBufferConfig.get_default_config()
    wb_buffer_config.validate_config(fsu_names=list(fust.keys()))
    reg_file_config = RegisterFileConfig.get_config_from_reg_File(reg_file=pipeline_rf)
    
    wb_stage = WritebackStage.create_pipeline_stage(
        wb_config=wb_buffer_config,
        rf_config=reg_file_config,
        ex_stage_ahead_latches=ex_stage.ahead_latches,
        reg_file=pipeline_rf,
        fsu_names=list(fust.keys()),
    )

    decode_issue_fwif = ForwardingIF(name="Decode_issue_fwif")

    issue_stage = IssueStage(
        fust_latency_cycles=1,
        regfile=pipeline_rf,
        fust=fust,
        name="IssueStage",
        behind_latch=decode_issue_if,
        ahead_latch=is_ex_latch,
        forward_ifs_read=None,
        # missing the forward IF connection, adding it in.
        forward_ifs_write= {"issue_scheduler_fwif" : issue_scheduler_fwif, 
                            "decode_issue_fwif" : decode_issue_fwif},
    )
    
    # 2. Initialize Register Data
    # ---------------------------------------------------------
    # Define list of warp IDs to test
    # warp_ids = [0, 1, 2, 3]  # Test multiple warps
    warp_ids = []
    for i in range(WARP_COUNT + 1 if(WARP_COUNT % 2 == 1) else WARP_COUNT):
        warp_ids.append(i)

    def get_test_values(warp_id, threads_per_warp):
        """Generate test values that are unique per warp_id"""
        return {
            # Integer registers
            1: [0 + i + warp_id for i in range(threads_per_warp)],
            2: [5 + i + warp_id for i in range(threads_per_warp)],
            3: [3 for _ in range(threads_per_warp)],
            4: [2 for _ in range(threads_per_warp)],
            5: [-5 - i + warp_id for i in range(threads_per_warp)],
            # Floating point registers
            10: [10.5 + i*0.5 + warp_id for i in range(threads_per_warp)],
            11: [2.5 + i*0.25 + warp_id for i in range(threads_per_warp)],
            12: [1.57 for _ in range(threads_per_warp)],
            13: [4.0 for _ in range(threads_per_warp)],
        }

    imm_test_value = Bits(int=5, length=32)  # Immediate value for I-type instructions
    
    # Initialize register values for all warps
    for warp_id in warp_ids:
        test_values = get_test_values(warp_id, pipeline_rf.threads_per_warp)
        
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
        # Integer ALU operations (Alu_int_0)
        ("ADD", R_Op.ADD, 1, 2, 20, "Alu_int_0", lambda a, b: (a + b) & 0xFFFFFFFF),
        ("SUB", R_Op.SUB, 1, 2, 21, "Alu_int_0", lambda a, b: (a - b) & 0xFFFFFFFF),
        ("AND", R_Op.AND, 1, 2, 24, "Alu_int_0", lambda a, b: a & b),
        ("OR", R_Op.OR, 1, 2, 25, "Alu_int_0", lambda a, b: a | b),
        ("XOR", R_Op.XOR, 1, 2, 26, "Alu_int_0", lambda a, b: a ^ b),
        ("SLT", R_Op.SLT, 1, 5, 27, "Alu_int_0", lambda a, b: 1 if a < b else 0),
        ("SLTU", R_Op.SLTU, 1, 2, 28, "Alu_int_0", lambda a, b: 1 if (a & 0xFFFFFFFF) < (b & 0xFFFFFFFF) else 0),
        ("SLL", R_Op.SLL, 1, 3, 29, "Alu_int_0", lambda a, b: (a << b) & 0xFFFFFFFF if b < 32 else 0),
        ("SRL", R_Op.SRL, 1, 3, 30, "Alu_int_0", lambda a, b: ((a & 0xFFFFFFFF) >> b) if b < 32 else 0),
        ("SRA", R_Op.SRA, 5, 3, 31, "Alu_int_0", lambda a, b: (a >> b) if b < 32 else 0),
        
        # Integer immediate operations (Alu_int_0)
        ("ADDI", I_Op.ADDI, 1, 4, 32, "Alu_int_0", lambda a, b: (a + b) & 0xFFFFFFFF),
        ("SUBI", I_Op.SUBI, 1, 4, 33, "Alu_int_0", lambda a, b: (a - b) & 0xFFFFFFFF),
        ("ORI", I_Op.ORI, 1, 3, 34, "Alu_int_0", lambda a, b: a | b),
        ("XORI", I_Op.XORI, 1, 3, 35, "Alu_int_0", lambda a, b: a ^ b),
        ("SLTI", I_Op.SLTI, 1, 4, 36, "Alu_int_0", lambda a, b: 1 if a < b else 0),
        ("SLTIU", I_Op.SLTIU, 1, 4, 37, "Alu_int_0", lambda a, b: 1 if (a & 0xFFFFFFFF) < (b & 0xFFFFFFFF) else 0),
        ("SLLI", I_Op.SLLI, 1, 3, 38, "Alu_int_0", lambda a, b: (a << b) & 0xFFFFFFFF if b < 32 else 0),
        ("SRLI", I_Op.SRLI, 1, 3, 39, "Alu_int_0", lambda a, b: ((a & 0xFFFFFFFF) >> b) if b < 32 else 0),
        ("SRAI", I_Op.SRAI, 5, 3, 40, "Alu_int_0", lambda a, b: (a >> b) if b < 32 else 0),
        
        # Integer multiply/divide operations (Mul_int_0, Div_int_0)
        ("MUL", R_Op.MUL, 1, 2, 22, "Mul_int_0", lambda a, b: (a * b) & 0xFFFFFFFF),
        ("DIV", R_Op.DIV, 1, 2, 23, "Div_int_0", lambda a, b: (a // b) if b != 0 else 0),
        
        # Floating point operations (AddSub_float_0, Mul_float_0, Div_float_0)
        ("ADDF", R_Op.ADDF, 10, 11, 50, "AddSub_float_0", lambda a, b: a + b),
        ("SUBF", R_Op.SUBF, 10, 11, 51, "AddSub_float_0", lambda a, b: a - b),
        ("MULF", R_Op.MULF, 10, 11, 52, "Mul_float_0", lambda a, b: a * b),
        ("DIVF", R_Op.DIVF, 10, 11, 53, "Div_float_0", lambda a, b: a / b if b != 0.0 else 0.0),
        
        # Special function operations (Trig_float_0, InvSqrt_float_0)
        ("SIN", F_Op.SIN, 12, 12, 54, "Trig_float_0", lambda a, b: None),  # Special handling
        ("COS", F_Op.COS, 12, 12, 55, "Trig_float_0", lambda a, b: None),  # Special handling
        ("ISQRT", F_Op.ISQRT, 13, 13, 56, "InvSqrt_float_0", lambda a, b: None),  # Special handling

        # CSRR instructions: rs1_reg field holds the csr_param (0=base_id, 1=tb_id, 2=tb_size, 3=kernel_base_ptr)
        ("CSRR", C_Op.CSRR, 0, 0, 57, "Alu_int_0", lambda a, b: None),  # rd=57, csr_param=0 -> base_id
        ("CSRR", C_Op.CSRR, 1, 0, 58, "Alu_int_0", lambda a, b: None),  # rd=58, csr_param=1 -> tb_id
        ("CSRR", C_Op.CSRR, 2, 0, 59, "Alu_int_0", lambda a, b: None),  # rd=59, csr_param=2 -> tb_size
        ("CSRR", C_Op.CSRR, 3, 0, 60, "Alu_int_0", lambda a, b: None),  # rd=60, csr_param=3 -> kernel_base_ptr

    ]

    # print(f"Generated {len(instruction_list)} instructions.")

    # 4. Run Pipeline Simulation
    # ---------------------------------------------------------
    print("\nStarting pipeline simulation...")
    
    print("Verifying initial state of register file matches golden model...")
    all_warps_match = True
    for warp_id in warp_ids:
        test_values = get_test_values(warp_id, pipeline_rf.threads_per_warp)
        if not compare_register_files(pipeline_rf, golden_rf, warp_id=warp_id, reg_list=list(test_values.keys()), verbose=True):
            all_warps_match = False
            print(f"❌ Initial register file state for warp {warp_id} does NOT match.")
    
    if all_warps_match:
        print("✅ Initial register file state matches golden model for all warps.")
    else:
        print("❌ Initial register file state does NOT match golden model. Aborting test.")
        return 0, 1
    
    # Cycle 1: Feed instructions
    # for idx, instr in enumerate(instruction_list):
    n_cycle = 0
    for cycle in range(len(test_cases)):
        # if instr.rd.uint == 1:
        #     abcHI = 1
        # print(f"\nCycle #{cycle}\n")
        wb_stage.tick()
        ex_stage.tick()
        ex_stage.compute()
        issue_stage.compute()
        decode_stage.compute()
        memc.compute()
        icache_stage.compute()
        scheduler_stage.compute()

        if (cycle == (len(test_cases) - 1)):
            n_cycle = cycle


    print("All instructions issued. Flushing pipeline...")

    FLUSH_CYCLES = len(test_cases) + 1100  # Run enough cycles to flush the pipeline after last instruction is issued
    for _ in range(FLUSH_CYCLES):
        # Refill forward IFs if they get drained
        # print(f"\nCycle #{_ + n_cycle}\n")
        # if issue_scheduler_fwif.payload is None:
        #     issue_scheduler_fwif.push(filler_issue_scheduler)
        # if decode_scheduler_fwif.payload is None:
        #     decode_scheduler_fwif.push(filler_decode_scheduler)
        
        wb_stage.tick()
        ex_stage.tick()
        ex_stage.compute()
        issue_stage.compute()
        decode_stage.compute()
        memc.compute()
        icache_stage.compute()
        scheduler_stage.compute()
        # reg_is_same = compare_register_files(pipeline_rf, golden_rf, warp_id=warp_id, reg_list=list(test_values.keys()), verbose=False)
        # if reg_is_same >:
        #     print("Register file state has diverged from golden model during flush. Aborting test.")
        #     return 0, 1
        
    print("Pipeline flush complete.")

    # 5. Update Golden Model
    # ---------------------------------------------------------
    instruction_list = []
    
    print("Computing golden reference...")
    
    # Iterate over all warps for golden model computation
    for warp_id in warp_ids:
        print(f"  Computing golden model for warp {warp_id}...")
        
        for test_name, opcode, rs1_reg, rs2_reg, rd_reg, intended_fu, python_op in test_cases:
            if intended_fu not in fust:
                print(f"    Warning: Skipping {test_name} (FU {intended_fu} not configured)")
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
                elif test_name == "CSRR":
                    # base_id (param=0): each thread gets base_id + thread_index
                    # all others are scalar, broadcast to all threads
                    if rs1_reg == 0:
                        csr_val = int(csr_table.read_base_id(warp_id)) + i
                    elif rs1_reg == 1:
                        csr_val = int(csr_table.read_tb_id(warp_id))
                    elif rs1_reg == 2:
                        csr_val = int(csr_table.read_tb_size(warp_id))
                    elif rs1_reg == 3:
                        csr_val = kernel_base_ptrs.read(0).uint
                    else:
                        csr_val = 0
                    golden_res.append(Bits(uint=csr_val, length=32))
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

    # 6. Verify Results
    # ---------------------------------------------------------
    print("\nVerifying Register File State...")
    
    # We check all destination registers that were written to
    # Int Ops: 20-40, Float Ops: 50-56
    regs_to_check = list(range(pipeline_rf.regs_per_warp))
    
    all_warps_passed = True
    for warp_id in warp_ids:
        print(f"\n  Checking warp {warp_id}...")
        passed = compare_register_files(
            pipeline_rf=pipeline_rf,
            golden_rf=golden_rf,
            warp_id=warp_id,
            reg_list=regs_to_check,
            verbose=True
        )
        if not passed:
            all_warps_passed = False
            print(f"  ❌ Warp {warp_id} FAILED")
        else:
            print(f"  ✅ Warp {warp_id} PASSED")

    print("\nFinal Pipeline Register File State:")
    pipeline_rf.dump()
    print("\nFinal Golden Model Register File State:")
    golden_rf.dump()

    if all_warps_passed:
        print(f"\n✅ SUCCESS: All register values match golden model for all {len(warp_ids)} warps.")
        return len(instruction_list), 0
    else:
        print("\n❌ FAILURE: Mismatches detected in register file.")
        return 0, 1


if __name__ == "__main__":
    passed, failed = test_all_operations()
    exit(0 if failed == 0 else 1)