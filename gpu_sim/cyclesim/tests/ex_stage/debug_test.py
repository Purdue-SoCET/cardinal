#!/usr/bin/env python3
"""Minimal debug test for pipeline progression"""

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent.parent / "src"
common_path = Path(__file__).parent.parent.parent.parent / "common"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(src_path / "ex_stage"))
sys.path.insert(0, str(common_path))

from bitstring import Bits
from custom_enums_multi import R_Op
from latch_forward_stage import Instruction
from execute_stage import ExecuteStage, FunctionalUnitConfig

def create_simple_instruction():
    """Create a simple ADD instruction"""
    return Instruction(
        pc=Bits(length=32, int=0),
        intended_FSU="Alu_int_0",
        warp_id=0,
        warp_group_id=0,
        rs1=Bits(length=5, int=1),
        rs2=Bits(length=5, int=2),
        rd=Bits(length=5, int=3),
        opcode=R_Op.ADD,
        rdat1=[Bits(length=32, int=10) for _ in range(32)],
        rdat2=[Bits(length=32, int=20) for _ in range(32)],
        wdat=[Bits(length=32, int=0) for _ in range(32)],
        predicate=[Bits(length=1, bin='1') for _ in range(32)]
    )

def main():
    print("Creating ExecuteStage...")
    config = FunctionalUnitConfig.get_default_config()
    ex_stage = ExecuteStage(config=config)
    
    print("\nCreating instruction...")
    instr = create_simple_instruction()
    
    print(f"\nCycle 0: Pushing instruction to behind_latch")
    success = ex_stage.behind_latch.push(instr)
    print(f"  Push success: {success}")
    
    for cycle in range(1, 10):
        print(f"\nCycle {cycle}:")
        
        # Check output latch status BEFORE popping
        alu_latch = ex_stage.ahead_latches["Alu_int_0_EX_WB_Interface"]
        print(f"  Before pop - ALU output latch valid: {alu_latch.valid}")
        if alu_latch.valid:
            print(f"    Output available!")
        
        # Pop output latch
        out_data = alu_latch.pop()
        if isinstance(out_data, Instruction):
            print(f"    Popped instruction, wdat[0] = {out_data.wdat[0].int}")
        
        # Compute and tick
        print(f"  Calling compute()...")
        ex_stage.compute()
        
        print(f"  Calling tick()...")
        ex_stage.tick()
        
        # Check if output is ready after tick
        print(f"  After tick - ALU output latch valid: {alu_latch.valid}")

if __name__ == "__main__":
    main()
