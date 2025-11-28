#!/usr/bin/env python3
"""Debug multiple instructions in the test harness"""

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
    
    print("\nIssuing 3 ADD instructions...")
    for i in range(3):
        instr = create_instruction(
            opcode=R_Op.ADD,
            intended_fsu="Alu_int_0",
            rdat1_vals=10 + i,
            rdat2_vals=20 + i,
            is_float=False,
            pc_value=i * 4  # Different PC for each
        )
        tracker = harness.issue_instruction(instr, test_name=f"ADD #{i}")
        if tracker:
            print(f"  Instruction {i} issued at cycle {tracker.issue_cycle}")
        else:
            print(f"  Instruction {i} FAILED to issue")
    
    print(f"\nTotal trackers: {len(harness.trackers)}")
    print(f"Pending issue: {len(harness.pending_issue)}")
    
    # Run for cycles
    for cycle_num in range(20):
        print(f"\n--- Cycle {harness.current_cycle} ---")
        print(f"Trackers in flight: {len(harness.trackers)}")
        print(f"Pending issue: {len(harness.pending_issue)}")
        print(f"Completed: {len(harness.completed_trackers)}")
        
        # Check latch status
        latch_name = "Alu_int_0_EX_WB_Interface"
        if latch_name in ex_stage.ahead_latches:
            latch = ex_stage.ahead_latches[latch_name]
            snooped = latch.snoop()
            print(f"Latch valid={latch.valid}")
            if snooped and isinstance(snooped, Instruction):
                print(f"  PC={snooped.pc.int}, wdat[0]={snooped.wdat[0].int}")
        
        harness.tick()
        
        if len(harness.completed_trackers) >= 3:
            print(f"\n✓ All 3 instructions completed!")
            break
    
    print(f"\n\nFinal summary:")
    print(f"Completed: {len(harness.completed_trackers)}")
    print(f"Still in flight: {len(harness.trackers)}")
    print(f"Pending issue: {len(harness.pending_issue)}")
    
    for i, tracker in enumerate(harness.completed_trackers):
        print(f"\nInstruction {i}:")
        print(f"  PC: {tracker.instr.pc.int}")
        print(f"  Issue cycle: {tracker.issue_cycle}")
        print(f"  Completion cycle: {tracker.actual_completion_cycle}")
        print(f"  Latency: {tracker.actual_completion_cycle - tracker.issue_cycle}")
        print(f"  Result: {tracker.result_instr.wdat[0].int}")

if __name__ == "__main__":
    main()
