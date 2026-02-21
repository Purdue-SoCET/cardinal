import math
import sys
import os
from bitstring import Bits

from simulator.issue.regfile import RegisterFile
from simulator.issue.stage import IssueStage
from simulator.execute.functional_unit import IntUnitConfig, FpUnitConfig, SpecialUnitConfig
from simulator.execute.stage import ExecuteStage, FunctionalUnitConfig
from simulator.mem.Memory import Mem
from simulator.mem.mem_controller import MemController
from simulator.mem.dcache import LockupFreeCacheStage
from simulator.mem.ld_st import Ldst_Fu
from simulator.writeback.stage import WritebackStage, WritebackBufferConfig, RegisterFileConfig
from simulator.latch_forward_stage import *
from gpu.common.custom_enums_multi import R_Op, I_Op, F_Op

# CREATING ALL LATCHES
# ---------------------------------------------------------
is_ex_latch = LatchIF(name="IS_EX_Latch")                              # Issue - Execute latch
lsu_dcache_latch = LatchIF(name="lsu_dcache_latch")                    # Ldst - dcache latch
dcache_lsu_forward = ForwardingIF(name="dcache_lsu_forward")           # Dcache - Ldst forwarding
lsu_dcache_latch.forward_if = dcache_lsu_forward
dcache_mem_latch = LatchIF(name="dcache_mem_latch")                    # Dcache - memory controller latch
mem_dcache_latch = LatchIF(name="mem_dcache_lstch")                    # Memory controller - dcache latch
ic_req = LatchIF("ICacheMemReqIF")                                     # Icache - memory controller latch
ic_resp = LatchIF("ICacheMemRespIF")                                   # Memory controller - icache latch

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


def write_val_to_mem(filename: str, address: int, value: int):
    '''
    Writes a specified data to a specified address in the test.bin text file
    '''
    line_idx = address // 4

    lines = []
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            # Strip newlines and empty lines
            lines = [line.strip() for line in f if line.strip()]
            
    # If the address is beyond the end of the file, pad it with zero-words
    while len(lines) <= line_idx:
        lines.append("00000000000000000000000000000000")
        
    binary_string = format(value & 0xFFFFFFFF, '032b')
    lines[line_idx] = binary_string
    
    # Write everything back to the file
    with open(filename, 'w') as f:
        for line in lines:
            f.write(line + '\n')


def print_latch_states(latches, forward_latches, cycle, before_after):
    """Prints the content of all latches with Hex formatting."""
    
    # --- Helper: Convert values to Hex Strings ---
    def to_hex(val):
        """Recursively converts integers to hex strings."""
        if isinstance(val, int):
            return f"0x{val:X}"
        elif isinstance(val, list):
            return [f"0x{v:X}" if isinstance(v, int) else v for v in val]
        return val

    def format_payload(payload):
        """Creates a readable Hex view of the payload."""
        if payload is None:
            return "None"

        # Case 1: Payload is a Dictionary (e.g., Input Requests)
        if isinstance(payload, dict):
            # Copy dict so we don't modify the actual simulation object
            p_view = payload.copy()
            # Convert specific keys to hex
            for key in ['addr_val', 'address', 'store_value', 'data', 'pc', 'addr']:
                if key in p_view and p_view[key] is not None:
                    p_view[key] = to_hex(p_view[key])
            return p_view

        # Case 2: Payload is an Object (e.g., dMemResponse)
        # We assume the object has a __repr__, but we can force it if needed
        return payload 
    # ---------------------------------------------

    if (before_after == "before"):
        print(f"=== Latch State Before Cycle {cycle} ===")
    else:
        print(f"=== Latch State at End of Cycle {cycle} ===")
    
    for name, latch in latches.items():
        payload = None

        # Extract payload based on latch type
        if hasattr(latch, 'valid') and latch.valid:
            payload = latch.payload
        elif hasattr(latch, 'payload') and latch.payload is not None:
            payload = latch.payload
            
        if payload is not None:
            # Print the formatted version
            print(f"  [{name}] VALID: {format_payload(payload)}")
        else:
            # Optional: Comment out to hide empty latches
            print(f"  [{name}] Empty")
    
    print(f"\nForward latches:")
    for name, forward_latch in forward_latches.items():
        payload = None

        if hasattr(forward_latch, 'valid') and latch.valid:
            payload = forward_latch.payload
        elif hasattr(forward_latch, 'payload') and latch.payload is not None:
            payload = forward_latch.payload
            
        if payload is not None:
            # Print the formatted version
            print(f"  [{name}] VALID: {format_payload(payload)}")
        else:
            # Optional: Comment out to hide empty latches
            print(f"  [{name}] Empty")
        
# Adding path to the current directory to import files from another directory
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
if project_root not in sys.path:
    sys.path.append(project_root)

def test_all_operations():
    # 1. Setup Pipeline Components
    # ---------------------------------------------------------
    pipeline_rf = RegisterFile()
    golden_rf = RegisterFile()
    functional_unit_config = FunctionalUnitConfig.get_default_config()
    fust = functional_unit_config.generate_fust_dict()
    
    # Issue stage
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

    # Execute stage
    ex_stage = ExecuteStage.create_pipeline_stage(
        functional_unit_config=functional_unit_config, 
        fust=fust
    )
    ex_stage.behind_latch = is_ex_latch

    # Writeback stage
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

    # Main memory
    mem_backend = Mem(start_pc = 0x0000_0000,
                      input_file = os.path.join(project_root, "gpu/tests/simulator/memory/dcache/test.bin"),
                      fmt = "bin")
    

    # DCache
    dCache = LockupFreeCacheStage(name = "dCache",
                                  behind_latch = lsu_dcache_latch,    # Change this to dummy
                                  forward_ifs_write = {"DCache_LSU_Resp": dcache_lsu_forward},   # Change this to dummy
                                  mem_req_if = dcache_mem_latch,
                                  mem_resp_if = mem_dcache_latch
                                  )
    
    # Memory controller
    memStage = MemController(name = "Memory",
                             ic_req_latch = ic_req,
                             dc_req_latch = dcache_mem_latch,
                             ic_serve_latch = ic_resp,
                             dc_serve_latch = mem_dcache_latch,
                             mem_backend = mem_backend,
                             latency = 5,
                             policy = "rr"
                            )
    
    # Load store Unit
    ldst = ex_stage.functional_units['MemBranchUnit_0'].subunits['Ldst_Fu_0']
    ldst.connect_interfaces(dcache_if = lsu_dcache_latch)

    all_latches = {
    "is_ex_latch": is_ex_latch,
    "lsu_dcache_latch": lsu_dcache_latch,
    "dcache_mem_latch": dcache_mem_latch,
    "mem_dcache_latch": mem_dcache_latch,
    "ic_req": ic_req,
    "ic_resp": ic_resp,
    "ldst_wb_latch": ldst.ex_wb_interface
    }
    all_forwarding = {
        "dcache_lsu_forward": dcache_lsu_forward
    }

    for latch_name, latch in all_latches.items():
        latch.clear_all()


    # 2. Initialize Register Data
    # ---------------------------------------------------------
    warp_id = 0
    test_addresses = {
        # Integer registers
        1: [i for i in range(0, 0x400, 32)],                                                                        # Reg 1: 0x0, 0x20, 0x40, ..., 0x3E0
        2: [i for i in range(0x400, 0x800, 32)]                                                                     # Reg 2: 0x400, 0x420, 0x440, ..., 0x7E0
    }

    imm_test_value = Bits(int=0, length=32)                                                                         # Immediate value for I-type instructions
    
    for reg_num, values in test_addresses.items():                                                                  # Converting the values from int to bits object
        if reg_num >= 10:
            data = [Bits(float=v, length=32) for v in values]
        else:
            data = [Bits(int=v, length=32) for v in values]
        
        pipeline_rf.write_warp_gran(warp_id=warp_id, dest_operand=Bits(uint=reg_num, length=32), data=data)         # Writes the initialized values the test rf
        golden_rf.write_warp_gran(warp_id=warp_id, dest_operand=Bits(uint=reg_num, length=32), data=data)           # Writes the initialized values to the golden rf


    # 3. Initialize Main Memory Data 
    # ---------------------------------------------------------
    mem_file = os.path.join(project_root, "gpu/tests/simulator/memory/dcache/test.bin")
    for address in test_addresses[1]:
        address_offset = address + imm_test_value.int
        write_val_to_mem(mem_file, address_offset, 1)                              # Initialize the addresses stored in register 1 + immediate to contain 1s (integer)
    
    for address in test_addresses[2]:
        address_offset = address + imm_test_value.int
        write_val_to_mem(mem_file, address_offset, 2)                              # Initialize the addresses stored in register 2 + immediate to contain 2s (integer)


    # 4. Define Test Cases
    # ---------------------------------------------------------
    # Format test: test_name, opcode, rs1_reg, rs2_reg, rd_reg, intended_fu, expected value
    test_cases = [
        ("LW_1", I_Op.LW, 1, 0, 20, "Ldst_Fu_0", 1),                            # Load from address in r1 to r20
        ("LW_2", I_Op.LW, 2, 0, 22, "Ldst_Fu_0", 2)                             # Load from address in r2 to r21
    ]

    instruction_list = []
    pc = 0x0
    for test_name, opcode, rs1_reg, rs2_reg, rd_reg, intended_fu, expected_value in test_cases:
        if intended_fu not in fust:
            print(f"  Warning: Skipping {test_name} (FU {intended_fu} not configured)")
            continue
        
        bank = warp_id % golden_rf.banks
        w_idx = warp_id // 2
        golden_data = [Bits(uint = expected_value, length = 32) for _ in range(32)]
        golden_rf.write_warp_gran(warp_id = rd_reg % 2, dest_operand = Bits(uint=rd_reg, length=32), data = golden_data)            # Update the golden rf to contain the expected loaded values

        instr = Instruction(
            pc=Bits(uint=pc, length=32),
            intended_FU=intended_fu,
            warp_id=rd_reg % 2,
            warp_group_id=0,
            num_operands=1 if isinstance(opcode, I_Op) else 2,
            rs1=Bits(uint=rs1_reg, length=32),
            rs2=Bits(uint=rs2_reg, length=32),
            rd=Bits(uint=rd_reg, length=32),
            wdat=[Bits(uint=0, length=32) for _ in range(pipeline_rf.threads_per_warp)],
            opcode=opcode,
            predicate=[Bits(uint=1, length=1) for _ in range(pipeline_rf.threads_per_warp)],
            target_bank=rd_reg % 2,
            imm=imm_test_value if isinstance(opcode, I_Op) else None
        )
        pc += 4

        instruction_list.append(instr)


    # 5. Run Simulation
    # ---------------------------------------------------------
    def run_sim(start, cycles, instr: None):
        for cycle in range(start, start + cycles):
            print(f"\n=== Cycle {cycle} ===")

            wb_stage.tick()
            memStage.compute()
            dCache.compute()
            ex_stage.tick()
            ex_stage.compute()
            issue_stage.compute(instr)

            print_latch_states(all_latches, all_forwarding, cycle, "after")
    
    start_cycle = 0
    original_stdout = sys.stdout
    with open("seqTest_dcache_is_ex_wb_rf", "w") as f:
        sys.stdout = f
        # Feed instructions
        for idx, instr in enumerate(instruction_list):
            run_sim(start_cycle, 1, instr)
            start_cycle += 1

        while (not ldst.ex_wb_interface.valid):
            run_sim(start_cycle, 1, None)
            start_cycle += 1

        run_sim(start_cycle, 1, None)
        start_cycle += 1

        while (not ldst.ex_wb_interface.valid):
            run_sim(start_cycle, 1, None)
            start_cycle += 1

        run_sim(start_cycle, 3, None)                                       # Flushing the wb buffer for # cycles to ensure that the data is written back to the rf

    # 6. Verify Results
    # ---------------------------------------------------------
    sys.stdout = original_stdout
    regs_to_check = [20, 22]
    passed = compare_register_files(
        pipeline_rf=pipeline_rf,
        golden_rf=golden_rf,
        warp_id=warp_id,
        reg_list=regs_to_check,
        verbose=True
    )

    with open("rf_dump", "w") as f:
        sys.stdout = f
        print("\nVerifying Register File State...")
        pipeline_rf.dump()
        golden_rf.dump()

    sys.stdout = original_stdout
    if passed:
        print("\n✅ SUCCESS: All register values match golden model.")
        return len(instruction_list), 0
    else:
        print("\n❌ FAILURE: Mismatches detected in register file.")
        return 0, 1


if __name__ == "__main__":
    passed, failed = test_all_operations()
    exit(0 if failed == 0 else 1)