import math
import sys
import os
from bitstring import Bits

# Adding path to the current directory to import files from another directory
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
if project_root not in sys.path:
    sys.path.append(project_root)
print(project_root)

from gpu.simulator.src.issue.regfile import RegisterFile
from gpu.simulator.src.issue.stage import IssueStage
from gpu.simulator.src.execute.functional_unit import IntUnitConfig, FpUnitConfig, SpecialUnitConfig
from gpu.simulator.src.execute.stage import ExecuteStage, FunctionalUnitConfig
from gpu.simulator.src.mem.Memory import Mem
from gpu.simulator.src.mem.mem_controller import MemController
from gpu.simulator.src.mem.dcache import LockupFreeCacheStage
from gpu.simulator.src.mem.ld_st import Ldst_Fu
from gpu.simulator.src.writeback.stage import WritebackStage, WritebackBufferConfig, RegisterFileConfig
from gpu.simulator.src.latch_forward_stage import Instruction, LatchIF
from gpu.common.custom_enums_multi import R_Op, I_Op, F_Op
from gpu.simulator.src.base_class import *

# CREATING ALL LATCHES
# ---------------------------------------------------------
is_ex_latch = LatchIF(name="IS_EX_Latch")                              # Issue - Execute latch
lsu_dcache_latch = LatchIF(name="lsu_dcache_latch")                    # Ldst - dcache latch
dcache_lsu_forward = ForwardingIF(name="dcache_lsu_forward")           # Dcache - Ldst forwarding
lsu_dcache_latch.forward_if = dcache_lsu_forward
dcache_mem_latch = LatchIF(name="dcache_mem_latch")                    # Dcache - memory controller latch
mem_dcache_latch = LatchIF(name="mem_dcache_lstch")                    # Demory controller - dcache latch

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


    # 2. Initialize Register Data
    # ---------------------------------------------------------
    warp_id = 0
    test_values = {
        # Integer registers
        1: [10 + i for i in range(pipeline_rf.threads_per_warp)],                               # Reg 1: [10, 11, 12, 13, ..., 41]
        2: [5 + i for i in range(pipeline_rf.threads_per_warp)],                                # Reg 2: [5, 6, 7, 8, ..., 36]
        3: [3 for _ in range(pipeline_rf.threads_per_warp)],                                    # Reg 3: [3, 3, 3, 3, ..., 3]
        4: [2 for _ in range(pipeline_rf.threads_per_warp)],                                    # Reg 4: [2, 2, 2, 2, ..., 2]
        5: [-5 - i for i in range(pipeline_rf.threads_per_warp)],                               # Reg 5: [-5, -4, -3, -2, ..., -36]
        # Floating point registers          
        10: [10.5 + i*0.5 for i in range(pipeline_rf.threads_per_warp)],                        # Reg 10: [10.5, 11.0, 11.5, ..., 26.0]
        11: [2.5 + i*0.25 for i in range(pipeline_rf.threads_per_warp)],                        # Reg 11: [2.5, 2.75, 3.0, ..., 10.5]
        12: [1.57 for _ in range(pipeline_rf.threads_per_warp)],                                # Reg 12: [1.57, 1.57, ...., 1.57]
        13: [4.0 for _ in range(pipeline_rf.threads_per_warp)],                                 # Reg 13: [4, 4, 4, ..., 4]
    }

    imm_test_value = Bits(int=5, length=32)                                                     # Immediate value for I-type instructions
    
    for reg_num, values in test_values.items():                                                 # Converting the values from int to bits object
        if reg_num >= 10:
            data = [Bits(float=v, length=32) for v in values]
        else:
            data = [Bits(int=v, length=32) for v in values]
        
        pipeline_rf.write_warp_gran(warp_id=warp_id, dest_operand=Bits(uint=reg_num, length=32), data=data)         # Writes the initialized values the test rf
        golden_rf.write_warp_gran(warp_id=warp_id, dest_operand=Bits(uint=reg_num, length=32), data=data)           # Writes the initialized values to the golden rf
    

    # 3. Define Test Cases
    # ---------------------------------------------------------
    


if __name__ == "__main__":
    test_all_operations()