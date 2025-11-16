#!/usr/bin/env python3
"""Debug the test harness with a single instruction"""

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

# Import the test harness
sys.path.insert(0, str(Path(__file__).parent))
from ex_stage_test import PipelineTestHarness, create_instruction

def main():
    print("Creating ExecuteStage...")
    config = FunctionalUnitConfig.get_default_config()
    ex_stage = ExecuteStage(config=config)
    harness = PipelineTestHarness(ex_stage)
    
    print("\nCreating simple ADD instruction...")
    instr = create_instruction(
        opcode=R_Op.ADD,
        intended_fsu="Alu_int_0",
        rdat1_vals=10,
        rdat2_vals=20,
        is_float=False,
        pc_value=0
    )
    
    print(f"\nIssuing instruction at cycle {harness.current_cycle}")
    tracker = harness.issue_instruction(instr, test_name="Simple ADD")
    
    if tracker:
        print(f"Instruction issued successfully")
        print(f"  Expected latency: {tracker.expected_latency}")
        print(f"  Target FSU: {tracker.instr.intended_FSU}")
    
    # Run for a few cycles with debug output
    for i in range(10):
        print(f"\n--- Cycle {harness.current_cycle} ---")
        print(f"Trackers in flight: {len(harness.trackers)}")
        print(f"Completed trackers: {len(harness.completed_trackers)}")
        
        # Check latch status before tick
        latch_name = "Alu_int_0_EX_WB_Interface"
        if latch_name in ex_stage.ahead_latches:
            latch = ex_stage.ahead_latches[latch_name]
            snooped = latch.snoop()
            print(f"Latch {latch_name}: valid={latch.valid}, has_data={snooped is not None}")
            if snooped and isinstance(snooped, Instruction):
                print(f"  Instruction PC: {snooped.pc.int}, wdat[0]={snooped.wdat[0].int}")
        
        harness.tick()
        
        if len(harness.completed_trackers) > 0:
            print(f"\n✓ Instruction completed!")
            tracker = harness.completed_trackers[0]
            print(f"  Issue cycle: {tracker.issue_cycle}")
            print(f"  Completion cycle: {tracker.actual_completion_cycle}")
            print(f"  Actual latency: {tracker.actual_completion_cycle - tracker.issue_cycle}")
            print(f"  Result wdat[0]: {tracker.result_instr.wdat[0].int}")
            break

if __name__ == "__main__":
    main()
