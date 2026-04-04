"""
Comprehensive Pipeline Test Suite
Tests all supported operations with golden model validation.

This test creates two register files:
1. Pipeline register file - integrated into the pipeline stages
2. Golden register file - used for Python-based golden model validation

All supported operations are tested by:
- Initializing both register files with identical test values
- Sending instructions through the pipeline
- Computing golden results using Python operations
- Comparing pipeline results against golden model
"""

from simulator.execute.functional_unit import IntUnitConfig, FpUnitConfig, SpecialUnitConfig
from simulator.execute.stage import ExecuteStage, FunctionalUnitConfig
from simulator.writeback.stage import WritebackStage, WritebackBufferConfig, RegisterFileConfig
from simulator.issue.regfile import RegisterFile
from simulator.latch_forward_stage import Instruction, LatchIF
from simulator.issue.stage import IssueStage
from bitstring import Bits
from common.custom_enums_multi import R_Op, I_Op, F_Op
import math


def compare_register_files(pipeline_rf, golden_rf, warp_id=0, reg_list=None, verbose=False):
    """
    Compare two register files and return True if they match, False otherwise.
    
    Args:
        pipeline_rf: Register file from the pipeline
        golden_rf: Golden model register file
        warp_id: Warp ID to compare (default: 0)
        reg_list: List of register numbers to compare (None = all registers)
        verbose: Print detailed mismatch information (default: False)
    
    Returns:
        bool: True if register files match, False otherwise
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
            if is_float_reg:
                # Allow 5% tolerance for float comparisons
                if abs(pipeline_val.float - golden_val.float) > abs(golden_val.float * 0.05 + 1e-6):
                    mismatches.append({
                        'reg': reg_num,
                        'thread': thread_id,
                        'pipeline': pipeline_val,
                        'golden': golden_val
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
        for m in mismatches[:10]:  # Show first 10 mismatches
            if is_float_reg:
                print(f"  Reg[{m['reg']}][{m['thread']}]: "
                      f"pipeline={m['pipeline'].float:.6f}, "
                      f"golden={m['golden'].float:.6f}")
            else:
                print(f"  Reg[{m['reg']}][{m['thread']}]: "
                      f"pipeline={m['pipeline'].int} (0x{m['pipeline'].hex}), "
                      f"golden={m['golden'].int} (0x{m['golden'].hex})")
        if len(mismatches) > 10:
            print(f"  ... and {len(mismatches) - 10} more")
    
    return len(mismatches) == 0


def test_all_operations():
    """
    Comprehensive test of all supported operations.
    
    Creates two register files: one for the pipeline and one as a golden model.
    Tests all supported operations and compares results.
    
    Supported Operations Tested:
    - Integer ALU: ADD, SUB, MUL, DIV, AND, OR, XOR, SLT, SLTU, SLL, SRL, SRA
    - Integer Immediate: ADDI, SUBI, ORI, XORI, SLTI, SLTIU, SLLI, SRLI, SRAI
    - Floating Point: ADDF, SUBF, MULF, DIVF
    - Special Functions: SIN, COS, ISQRT (Inverse Square Root)
    
    Returns:
        tuple: (passed_tests, failed_tests)
    """
    print("\nComprehensive Pipeline Test - All Supported Operations")
    print("-" * 60)
    
    # Create pipeline register file and stages
    pipeline_rf = RegisterFile()
    
    # Create golden model register file (separate copy)
    golden_rf = RegisterFile()
    
    # Create functional unit configuration
    functional_unit_config = FunctionalUnitConfig.get_default_config()
    fust = functional_unit_config.generate_fust_dict()
    
    print(f"Functional Units: {', '.join(sorted(fust.keys()))}")
    
    # Create pipeline stages
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
    
    # Initialize test values in both register files
    warp_id = 0
    
    # Register assignments for test operands
    test_values = {
        # Integer registers
        1: [10 + i for i in range(pipeline_rf.threads_per_warp)],      # r1: 10, 11, 12, ...
        2: [5 + i for i in range(pipeline_rf.threads_per_warp)],       # r2: 5, 6, 7, ...
        3: [3 for _ in range(pipeline_rf.threads_per_warp)],           # r3: 3 (for shift amounts)
        4: [2 for _ in range(pipeline_rf.threads_per_warp)],           # r4: 2
        5: [-5 - i for i in range(pipeline_rf.threads_per_warp)],      # r5: -5, -6, -7, ...
        # Floating point registers
        10: [10.5 + i*0.5 for i in range(pipeline_rf.threads_per_warp)],  # r10: 10.5, 11.0, 11.5, ...
        11: [2.5 + i*0.25 for i in range(pipeline_rf.threads_per_warp)],  # r11: 2.5, 2.75, 3.0, ...
        12: [1.57 for _ in range(pipeline_rf.threads_per_warp)],          # r12: ~π/2 (for trig)
        13: [4.0 for _ in range(pipeline_rf.threads_per_warp)],           # r13: 4.0 (float)
    }
    
    for reg_num, values in test_values.items():
        if reg_num >= 10:  # Floating point registers
            pipeline_data = [Bits(float=v, length=32) for v in values]
            golden_data = [Bits(float=v, length=32) for v in values]
        else:  # Integer registers
            pipeline_data = [Bits(int=v, length=32) for v in values]
            golden_data = [Bits(int=v, length=32) for v in values]
        
        pipeline_rf.write_warp_gran(
            warp_id=warp_id, 
            dest_operand=Bits(uint=reg_num, length=32), 
            data=pipeline_data
        )
        golden_rf.write_warp_gran(
            warp_id=warp_id, 
            dest_operand=Bits(uint=reg_num, length=32), 
            data=golden_data
        )
    
    # Define all test cases
    # Format: (op_name, opcode, rs1, rs2, rd, intended_FU, python_operation)
    # 
    # NOTE: Functional unit assignments are based on functional_sub_unit.py SUPPORTED_OPS:
    #   - Alu_int_0: Integer ALU operations
    #       * R-type: ADD, SUB, AND, OR, XOR, SLT, SLTU, SLL, SRL, SRA
    #       * I-type: ADDI, SUBI, ORI, XORI, SLTI, SLTIU, SLLI, SRLI, SRAI
    #   - Mul_int_0: Integer multiply
    #       * R-type: MUL
    #   - Div_int_0: Integer divide
    #       * R-type: DIV
    #   - AddSub_float_0: Floating point add/subtract
    #       * R-type: ADDF, SUBF
    #   - Mul_float_0: Floating point multiply
    #       * R-type: MULF
    #   - Div_float_0: Floating point divide
    #       * R-type: DIVF
    #   - Trig_float_0: Trigonometric functions (CORDIC algorithm)
    #       * F-type: SIN, COS
    #   - InvSqrt_float_0: Inverse square root (Fast InvSqrt algorithm)
    #       * F-type: ISQRT
    #   - Sqrt_float_0: Square root (exists but no opcode defined yet)
    
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
    ]
    
    print(f"\nRunning {len(test_cases)} test cases...\n")
    passed_tests = 0
    failed_tests = 0
    
    for test_name, opcode, rs1_reg, rs2_reg, rd_reg, intended_fu, python_op in test_cases:
        # Check if the intended FU exists in fust
        if intended_fu not in fust:
            print(f"  {test_name:6s} SKIPPED (FU not found)")
            continue
        
        # Read source operands from golden RF
        bank = warp_id % golden_rf.banks
        warp_idx = warp_id // 2
        rs1_data = golden_rf.regs[bank][warp_idx][rs1_reg]
        rs2_data = golden_rf.regs[bank][warp_idx][rs2_reg]
        
        # Compute golden result using Python
        if test_name in ["SIN", "COS"]:
            # Special handling for trig functions
            golden_result = []
            for i in range(golden_rf.threads_per_warp):
                a = rs1_data[i].float
                if test_name == "SIN":
                    result = math.sin(a)
                else:  # COS
                    result = math.cos(a)
                golden_result.append(Bits(float=result, length=32))
        elif test_name == "ISQRT":
            # Special handling for inverse square root
            golden_result = []
            for i in range(golden_rf.threads_per_warp):
                a = rs1_data[i].float
                if a <= 0.0:
                    result = 0.0
                else:
                    result = 1.0 / (a ** 0.5)
                golden_result.append(Bits(float=result, length=32))
        elif rd_reg >= 50:  # Float operations
            golden_result = []
            for i in range(golden_rf.threads_per_warp):
                a = rs1_data[i].float
                b = rs2_data[i].float
                result = python_op(a, b)
                golden_result.append(Bits(float=result, length=32))
        else:  # Integer operations
            golden_result = []
            for i in range(golden_rf.threads_per_warp):
                a = rs1_data[i].int
                b = rs2_data[i].int
                result = python_op(a, b)
                # Ensure result is properly masked to 32 bits
                if result < 0:
                    golden_result.append(Bits(int=result, length=32))
                else:
                    golden_result.append(Bits(uint=result & 0xFFFFFFFF, length=32))
        
        # Write golden result to golden RF
        golden_rf.write_warp_gran(
            warp_id=warp_id, 
            dest_operand=Bits(uint=rd_reg, length=32), 
            data=golden_result
        )
        
        # Create instruction for pipeline
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
        
        # Send instruction through pipeline
        issue_stage.compute(instr)
        
        # Run pipeline for enough cycles (account for max latency)
        for _ in range(100):
            wb_stage.tick()
            ex_stage.tick()
            ex_stage.compute()
            issue_stage.compute(None)
        
        # Compare results for the destination register
        pipeline_result = pipeline_rf.regs[bank][warp_idx][rd_reg]
        golden_result_check = golden_rf.regs[bank][warp_idx][rd_reg]
        
        # Check if results match
        match = True
        max_error = 0.0
        for i in range(pipeline_rf.threads_per_warp):
            # For float comparisons, allow small tolerance
            if rd_reg >= 50 or test_name in ["SIN", "COS", "ISQRT"]:
                pipeline_val = pipeline_result[i].float
                golden_val = golden_result_check[i].float
                
                # Different tolerances for different operations
                if test_name in ["SIN", "COS"]:
                    # CORDIC algorithm has higher error - allow 5% relative error
                    tolerance = 0.05
                elif test_name == "ISQRT":
                    # Fast inverse square root has moderate error - allow 1% 
                    tolerance = 0.01
                else:
                    # Standard float ops - allow 0.1% relative error
                    tolerance = 0.001
                
                if abs(golden_val) > 1e-6:
                    rel_error = abs(pipeline_val - golden_val) / abs(golden_val)
                    max_error = max(max_error, rel_error)
                    if rel_error > tolerance:
                        match = False
                        break
                else:
                    abs_error = abs(pipeline_val - golden_val)
                    max_error = max(max_error, abs_error)
                    if abs_error > tolerance:
                        match = False
                        break
            else:
                if pipeline_result[i] != golden_result_check[i]:
                    match = False
                    break
        
        if match:
            if rd_reg >= 50 or test_name in ["SIN", "COS", "ISQRT"]:
                print(f"  {test_name:6s} [{intended_fu:16s}] PASS (err: {max_error:.2e})")
            else:
                print(f"  {test_name:6s} [{intended_fu:16s}] PASS")
            passed_tests += 1
        else:
            print(f"  {test_name:6s} [{intended_fu:16s}] FAIL", end="")
            # Show first mismatch inline
            if rd_reg >= 50 or test_name in ["SIN", "COS", "ISQRT"]:
                p_val = pipeline_result[0].float
                g_val = golden_result_check[0].float
                error = abs(p_val - g_val) / abs(g_val) if abs(g_val) > 1e-6 else abs(p_val - g_val)
                print(f" - thread[0]: pipe={p_val:.4f} gold={g_val:.4f} err={error:.2e}")
            else:
                print(f" - thread[0]: pipe={pipeline_result[0].int} gold={golden_result_check[0].int}")
            failed_tests += 1
    
    # Final summary
    print(f"\n{'-'*60}")
    print(f"Summary: {passed_tests}/{len(test_cases)} passed, {failed_tests}/{len(test_cases)} failed")
    
    # Perform register file integrity check
    dest_regs = list(range(20, 41)) + list(range(50, 57))
    integrity_ok = compare_register_files(
        pipeline_rf=pipeline_rf,
        golden_rf=golden_rf,
        warp_id=warp_id,
        reg_list=dest_regs,
        verbose=False
    )
    
    if integrity_ok:
        print(f"Register file integrity: PASS")
    else:
        print(f"Register file integrity: FAIL (run with verbose=True for details)")
    
    if failed_tests == 0:
        print(f"\nResult: ALL TESTS PASSED\n")
    else:
        print(f"\nResult: {failed_tests} TEST(S) FAILED\n")

    pipeline_rf.dump()
    golden_rf.dump()
    
    return passed_tests, failed_tests


if __name__ == "__main__":
    passed, failed = test_all_operations()
    exit(0 if failed == 0 else 1)