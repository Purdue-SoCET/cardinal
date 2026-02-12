from simulator.execute.functional_unit import IntUnitConfig, FpUnitConfig, SpecialUnitConfig
from simulator.execute.stage import ExecuteStage, FunctionalUnitConfig
from simulator.writeback.stage import WritebackStage, WritebackBufferConfig, RegisterFileConfig
from simulator.issue.regfile import RegisterFile
from simulator.latch_forward_stage import Instruction, LatchIF
from simulator.issue.stage import IssueStage
from bitstring import Bits
from gpu.common.custom_enums_multi import R_Op, I_Op, F_Op
import math

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
    pipeline_rf = RegisterFile()
    golden_rf = RegisterFile()
    
    functional_unit_config = FunctionalUnitConfig.get_default_config()
    fust = functional_unit_config.generate_fust_dict()
    
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
        behind_latch=None,
        ahead_latch=is_ex_latch,
        forward_ifs_read=None,
        forward_ifs_write=None
    )
    
    # 2. Initialize Register Data
    # ---------------------------------------------------------
    warp_id = 0
    test_values = {
        # Integer registers
        1: [10 + i for i in range(pipeline_rf.threads_per_warp)],
        2: [5 + i for i in range(pipeline_rf.threads_per_warp)],
        3: [3 for _ in range(pipeline_rf.threads_per_warp)],
        4: [2 for _ in range(pipeline_rf.threads_per_warp)],
        5: [-5 - i for i in range(pipeline_rf.threads_per_warp)],
        # Floating point registers
        10: [10.5 + i*0.5 for i in range(pipeline_rf.threads_per_warp)],
        11: [2.5 + i*0.25 for i in range(pipeline_rf.threads_per_warp)],
        12: [1.57 for _ in range(pipeline_rf.threads_per_warp)],
        13: [4.0 for _ in range(pipeline_rf.threads_per_warp)],
    }
    
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
        ("ADD", R_Op.ADD, 1, 2, 20, "Alu_int_0", lambda a, b: (a + b) & 0xFFFFFFFF),
        ("SUB", R_Op.SUB, 1, 2, 21, "Alu_int_0", lambda a, b: (a - b) & 0xFFFFFFFF),
        ("MUL", R_Op.MUL, 1, 2, 22, "Mul_int_0", lambda a, b: (a * b) & 0xFFFFFFFF),
        ("DIV", R_Op.DIV, 1, 2, 23, "Div_int_0", lambda a, b: (a // b) if b != 0 else 0),
        ("AND", R_Op.AND, 1, 2, 24, "Alu_int_0", lambda a, b: a & b),
        ("OR", R_Op.OR, 1, 2, 25, "Alu_int_0", lambda a, b: a | b),
        ("XOR", R_Op.XOR, 1, 2, 26, "Alu_int_0", lambda a, b: a ^ b),
        ("SLT", R_Op.SLT, 1, 5, 27, "Alu_int_0", lambda a, b: 1 if a < b else 0),
        ("SLTU", R_Op.SLTU, 1, 2, 28, "Alu_int_0", lambda a, b: 1 if (a & 0xFFFFFFFF) < (b & 0xFFFFFFFF) else 0),
        ("SLL", R_Op.SLL, 1, 3, 29, "Alu_int_0", lambda a, b: (a << b) & 0xFFFFFFFF if b < 32 else 0),
        ("SRL", R_Op.SRL, 1, 3, 30, "Alu_int_0", lambda a, b: ((a & 0xFFFFFFFF) >> b) if b < 32 else 0),
        ("SRA", R_Op.SRA, 5, 3, 31, "Alu_int_0", lambda a, b: (a >> b) if b < 32 else 0),
        
        # Integer Immediate (32-40)
        ("ADDI", I_Op.ADDI, 1, 4, 32, "Alu_int_0", lambda a, b: (a + b) & 0xFFFFFFFF),
        ("SUBI", I_Op.SUBI, 1, 4, 33, "Alu_int_0", lambda a, b: (a - b) & 0xFFFFFFFF),
        ("ORI", I_Op.ORI, 1, 3, 34, "Alu_int_0", lambda a, b: a | b),
        ("XORI", I_Op.XORI, 1, 3, 35, "Alu_int_0", lambda a, b: a ^ b),
        ("SLTI", I_Op.SLTI, 1, 4, 36, "Alu_int_0", lambda a, b: 1 if a < b else 0),
        ("SLTIU", I_Op.SLTIU, 1, 4, 37, "Alu_int_0", lambda a, b: 1 if (a & 0xFFFFFFFF) < (b & 0xFFFFFFFF) else 0),
        ("SLLI", I_Op.SLLI, 1, 3, 38, "Alu_int_0", lambda a, b: (a << b) & 0xFFFFFFFF if b < 32 else 0),
        ("SRLI", I_Op.SRLI, 1, 3, 39, "Alu_int_0", lambda a, b: ((a & 0xFFFFFFFF) >> b) if b < 32 else 0),
        ("SRAI", I_Op.SRAI, 5, 3, 40, "Alu_int_0", lambda a, b: (a >> b) if b < 32 else 0),
        
        # Floating Point (50-53)
        ("ADDF", R_Op.ADDF, 10, 11, 50, "AddSub_float_0", lambda a, b: a + b),
        ("SUBF", R_Op.SUBF, 10, 11, 51, "AddSub_float_0", lambda a, b: a - b),
        ("MULF", R_Op.MULF, 10, 11, 52, "Mul_float_0", lambda a, b: a * b),
        ("DIVF", R_Op.DIVF, 10, 11, 53, "Div_float_0", lambda a, b: a / b if b != 0.0 else 0.0),
        
        # Special Functions (54-56)
        ("SIN", F_Op.SIN, 12, 12, 54, "Trig_float_0", None),
        ("COS", F_Op.COS, 12, 12, 55, "Trig_float_0", None),
        ("ISQRT", F_Op.ISQRT, 13, 13, 56, "InvSqrt_float_0", None),
    ]

    # 4. Generate Instructions and Update Golden Model
    # ---------------------------------------------------------
    instruction_list = []
    
    print("Generating instruction stream and computing golden reference...")
    
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
            # 3. Int Ops
            else:
                res = python_op(rs1_vals[i].int, rs2_vals[i].int)
                if res < 0:
                    golden_res.append(Bits(int=res, length=32))
                else:
                    golden_res.append(Bits(uint=res & 0xFFFFFFFF, length=32))

        golden_rf.write_warp_gran(
            warp_id=warp_id,
            dest_operand=Bits(uint=rd_reg, length=32),
            data=golden_res
        )

        # --- B. Create Pipeline Instruction ---
        instr = Instruction(
            pc=Bits(uint=0x0, length=32),
            intended_FU=intended_fu,
            warp_id=warp_id,
            warp_group_id=0,
            num_operands=2,
            rs1=Bits(uint=rs1_reg, length=32),
            rs2=Bits(uint=rs2_reg, length=32),
            rd=Bits(uint=rd_reg, length=32),
            wdat=[Bits(uint=0, length=32) for _ in range(pipeline_rf.threads_per_warp)],
            opcode=opcode,
            predicate=[Bits(uint=1, length=1) for _ in range(pipeline_rf.threads_per_warp)],
            target_bank=0,
        )
        instruction_list.append(instr)

    print(f"Generated {len(instruction_list)} instructions.")

    # 5. Run Pipeline Simulation
    # ---------------------------------------------------------
    print("\nStarting pipeline simulation...")
    
    # Cycle 1: Feed instructions
    for idx, instr in enumerate(instruction_list):
        # Issue Stage: Send new instruction
        issue_stage.compute(instr)
        
        # Advance Pipeline: Tick logic
        wb_stage.tick()
        ex_stage.tick()
        
        # Advance Pipeline: Compute logic
        ex_stage.compute()
    
    print("All instructions issued. Flushing pipeline...")

    # Cycle 2: Flush pipeline (allow remaining instructions to complete)
    # We loop enough times to cover the latency of the slowest unit
    FLUSH_CYCLES = 50
    for _ in range(FLUSH_CYCLES):
        issue_stage.compute(None) # No new instruction
        wb_stage.tick()
        ex_stage.tick()
        ex_stage.compute()

    print("Pipeline flush complete.")

    # 6. Verify Results
    # ---------------------------------------------------------
    print("\nVerifying Register File State...")
    
    # We check all destination registers that were written to
    # Int Ops: 20-40, Float Ops: 50-56
    regs_to_check = list(range(20, 41)) + list(range(50, 57))
    
    passed = compare_register_files(
        pipeline_rf=pipeline_rf,
        golden_rf=golden_rf,
        warp_id=warp_id,
        reg_list=regs_to_check,
        verbose=True
    )

    if passed:
        print("\n✅ SUCCESS: All register values match golden model.")
        return len(instruction_list), 0
    else:
        print("\n❌ FAILURE: Mismatches detected in register file.")
        return 0, 1

if __name__ == "__main__":
    passed, failed = test_all_operations()
    exit(0 if failed == 0 else 1)