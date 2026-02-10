from simulator.execute.functional_unit import MemBranchUnitConfig
from simulator.execute.functional_unit import IntUnitConfig, FpUnitConfig, SpecialUnitConfig
from simulator.execute.stage import ExecuteStage
from simulator.writeback.stage import WritebackStage, WritebackBufferConfig, RegisterFileConfig
from simulator.execute.stage import FunctionalUnitConfig
from simulator.issue.regfile import RegisterFile

# Issue Stage stuff
from simulator.latch_forward_stage import ForwardingIF, Instruction, LatchIF
from simulator.issue.stage import IssueStage
from pathlib import Path
from bitstring import Bits
from gpu.common.custom_enums_multi import *

"""
Create Execute and Writeback Stages
"""
# Step 0: Create desired configuration classmethods in the respective files:
    # IntUnitConfig -> /execute/arithmetic_functional_unit.py
    # FpUnitConfig -> /execute/arithmetic_functional_unit.py
    # SpecialUnitConfig -> /execute/arithmetic_functional_unit.py
    # FunctionalUnitConfig -> /execute/stage.py
    # WritebackBufferConfig -> /writeback/stage.py
    # RegisterFileConfig -> /writeback/stage.py

    # Only default configurations are provided in this example. You can follow the pattern to create custom configurations as needed.
    # Please do not use the constructors directly; always use the classmethods to ensure maintainability and consistency.

# Step 1: Create Configurations using classmethods
    # I am using default configurations here, but custom configurations can be created as neede by following Step 0.

reg_file = RegisterFile()

# for the functional unit config, you can do this:
functional_unit_config = FunctionalUnitConfig.get_default_config()
fust = functional_unit_config.generate_fust_dict()

# OR, you can do this (same outcome):
int_config = IntUnitConfig.get_default_config()
fp_config = FpUnitConfig.get_default_config()
special_config = SpecialUnitConfig.get_default_config()
membranch_config = MemBranchUnitConfig.get_default_config()
functional_unit_config = FunctionalUnitConfig.get_config(
    int_config=int_config, fp_config=fp_config, special_config=special_config, membranch_config=membranch_config,
    int_unit_count=1, fp_unit_count=1, special_unit_count=1, membranch_unit_count=1
)
fust = functional_unit_config.generate_fust_dict()

# Step 2: Create Execute Stage (With Latch and Forwarding Interfaces)
is_ex_latch = LatchIF(name="IS_EX_Latch")
ex_stage = ExecuteStage.create_pipeline_stage(functional_unit_config=functional_unit_config, fust=fust)
ex_stage.behind_latch = is_ex_latch

# Step 3: Create buffer sizes and priorities for Writeback Buffer Config
wb_buffer_config = WritebackBufferConfig.get_default_config()
wb_buffer_config.validate_config(fsu_names=list(fust.keys()))
reg_file_config = RegisterFileConfig.get_config_from_reg_File(reg_file=reg_file)

# Make sure ExecuteStage is created first before WritebackStage since it needs the ahead_latches from ExecuteStage
# wb_stage = WritebackStage.create_pipeline_stage(wb_buffer_config=wb_buffer_config, rf_config=reg_file_config, ex_stage_ahead_latches=ex_stage.ahead_latches)
# wb_stage = WritebackStage.create_pipeline_stage(wb_config=wb_buffer_config, rf_config=reg_file_config, ex_stage_ahead_latches=ex_stage.ahead_latches, reg_file=reg_file, fsu_names=list(fust.keys()))
wb_stage = WritebackStage.create_pipeline_stage(
    wb_config=wb_buffer_config,
    rf_config=reg_file_config,
    ex_stage_ahead_latches=ex_stage.ahead_latches,
    reg_file=reg_file,
    fsu_names=list(fust.keys())
)
"""
Create Issue Stage and Register File
    We need to create the RF, the FUST will be definied by execute as it knows which FUs it wants. 
"""

issue_stage = IssueStage(
    fust_latency_cycles = 1,
    regfile = reg_file,
    fust = fust,
    name = "IssueStage",
    behind_latch = None,
    ahead_latch = is_ex_latch,
    forward_ifs_read = None,
    forward_ifs_write = None
)


if __name__ == "__main__":
    print("Execute Stage and Writeback Stage created successfully with the specified configurations.")

    # 1) Fill regfile with a known value in register 1, all threads
    reg_file.write_warp_gran(
        warp_id=0,
        dest_operand=Bits(uint=1, length=32),
        data=[Bits(uint=10, length=32) for _ in range(reg_file.threads_per_warp)]
    )
    reg_file.write_warp_gran(
        warp_id=0,
        dest_operand=Bits(uint=2, length=32),
        data=[Bits(uint=0, length=32) for _ in range(reg_file.threads_per_warp)]
    )
    # Confirm initial value
    print("Initial reg[0][0][1]:", [x.int for x in reg_file.regs[0][0][1]])

    # 2) Create an ADD instruction: reg2 = reg1 + reg1 (should be 20)
    instr = Instruction(
        pc=Bits(uint=0x0, length=32),
        intended_FU=list(fust.keys())[0],  # Use a valid FSU name from fust.keys() (should be Alu_int_0)
        warp_id=0,
        warp_group_id=0,
        num_operands = 2,
        rs1=Bits(uint=1, length=32),
        rs2=Bits(uint=1, length=32),
        rd=Bits(uint=2, length=32),
        wdat=[Bits(uint=0, length=32) for _ in range(reg_file.threads_per_warp)],
        opcode=R_Op.ADD,  # Use enum for opcode, make sure it is supported by the intended_FU
        predicate=[Bits(uint=1, length=1) for _ in range(reg_file.threads_per_warp)],
        target_bank=0,
    )

    # 3) Send into pipe
    issue_stage.compute(instr)

    # 4) Run for enough cycles to propagate through pipeline
    for _ in range(1000):
        wb_stage.tick()
        ex_stage.tick()
        ex_stage.compute()
        issue_stage.compute(None)
    
    print(instr)

    # 5) Check result in reg2 (should be 20 for all threads)
    print("Result reg[0][0][2]:", [x.int for x in reg_file.regs[0][0][2]])