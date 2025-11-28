#!/usr/bin/env python3
"""
Simple test to verify PerfCount integration with WritebackBuffer.
This tests that performance counters are properly tracking metrics.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/wb_stage'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../common'))

from performance_counter import PerfCount
from latch_forward_stage import Instruction
from bitstring import Bits
from custom_enums_multi import Op, R_Op

def test_perf_count_basic():
    """Test basic PerfCount functionality."""
    print("=" * 80)
    print("Testing PerfCount Basic Functionality")
    print("=" * 80)
    
    # Create a performance counter
    perf_count = PerfCount(name="test_buffer")
    
    # Simulate some cycles with varying buffer occupancy
    buffer_capacity = 16
    
    # Cycle 1: Empty buffer
    perf_count.increment(
        cycle=0,
        buffer_occupancy=0,
        buffer_capacity=buffer_capacity,
        stored_this_cycle=False,
        writeback_this_cycle=False,
        instructions_in_buffer=[]
    )
    
    # Cycle 2: Store one instruction
    instr1 = Instruction(
        pc=Bits(uint=0, length=32),
        intended_FSU="Alu_int",
        warp_id=0,
        warp_group_id=0,
        rs1=Bits(uint=1, length=5),
        rs2=Bits(uint=2, length=5),
        rd=Bits(uint=3, length=5),
        opcode=R_Op.ADD,
        rdat1=[Bits(uint=10, length=32)],
        rdat2=[Bits(uint=20, length=32)],
        wdat=[Bits(uint=0, length=32)],
        predicate=[Bits(uint=1, length=1)],
        issued_cycle=0
    )
    
    perf_count.increment(
        cycle=1,
        buffer_occupancy=1,
        buffer_capacity=buffer_capacity,
        stored_this_cycle=True,
        writeback_this_cycle=False,
        instructions_in_buffer=[instr1]
    )
    
    # Cycle 3: Buffer getting fuller
    perf_count.increment(
        cycle=2,
        buffer_occupancy=5,
        buffer_capacity=buffer_capacity,
        stored_this_cycle=True,
        writeback_this_cycle=False,
        instructions_in_buffer=[instr1]
    )
    
    # Cycle 4: Buffer full
    perf_count.increment(
        cycle=3,
        buffer_occupancy=16,
        buffer_capacity=buffer_capacity,
        stored_this_cycle=False,
        writeback_this_cycle=False,
        instructions_in_buffer=[instr1]
    )
    
    # Cycle 5: Writeback occurs
    perf_count.increment(
        cycle=4,
        buffer_occupancy=15,
        buffer_capacity=buffer_capacity,
        stored_this_cycle=False,
        writeback_this_cycle=True,
        instructions_in_buffer=[]
    )
    
    # Finalize statistics
    perf_count.finalize_statistics()
    
    # Print results
    print(f"\nPerformance Counter Results for '{perf_count.name}':")
    print(f"  Total Cycles: {perf_count.total_cycles}")
    print(f"  Stall Cycles: {perf_count.stall_cycles}")
    print(f"  Buffer Full Cycles: {perf_count.buffer_full_cycles}")
    print(f"  Store Cycles: {perf_count.store_cycles}")
    print(f"  Writeback Cycles: {perf_count.writeback_cycles}")
    print(f"  Average Buffer Occupancy: {perf_count.average_buffer_occupancy:.2f}")
    print(f"  Average Instruction Buffer Age: {perf_count.average_instruction_buffer_age:.2f}")
    print(f"  10th Percentile Buffer Occupancy: {perf_count.percentile_10_buffer_occupancy:.2f}")
    print(f"  1st Percentile Buffer Occupancy: {perf_count.percentile_1_buffer_occupancy:.2f}")
    
    # Validate expected results
    assert perf_count.total_cycles == 5, "Expected 5 total cycles"
    assert perf_count.stall_cycles == 1, "Expected 1 stall cycle (when buffer was full)"
    assert perf_count.buffer_full_cycles == 1, "Expected 1 buffer full cycle"
    assert perf_count.store_cycles == 2, "Expected 2 store cycles"
    assert perf_count.writeback_cycles == 1, "Expected 1 writeback cycle"
    
    print("\n✓ All basic tests passed!")
    
    # Test CSV output
    output_dir = "/tmp/test_perf_count"
    os.makedirs(output_dir, exist_ok=True)
    perf_count.to_csv(directory=output_dir)
    print(f"\n✓ CSV output saved to {output_dir}")
    
    return True

def test_perf_count_combined_csv():
    """Test combined CSV output for multiple performance counters."""
    print("\n" + "=" * 80)
    print("Testing Combined CSV Output")
    print("=" * 80)
    
    # Create multiple performance counters
    perf_counts = []
    for i in range(3):
        pc = PerfCount(name=f"buffer_{i}")
        
        # Simulate some cycles
        for cycle in range(10):
            pc.increment(
                cycle=cycle,
                buffer_occupancy=i + cycle % 5,
                buffer_capacity=16,
                stored_this_cycle=(cycle % 2 == 0),
                writeback_this_cycle=(cycle % 3 == 0),
                instructions_in_buffer=[]
            )
        
        perf_counts.append(pc)
    
    # Export combined CSV
    output_dir = "/tmp/test_perf_count"
    PerfCount.to_combined_csv(perf_counts, directory=output_dir)
    print(f"\n✓ Combined CSV output saved to {output_dir}/Combined_WbStage_PerfCount_Stats.csv")
    
    return True

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("WRITEBACK BUFFER PERFORMANCE COUNTER TESTS")
    print("=" * 80 + "\n")
    
    try:
        test_perf_count_basic()
        test_perf_count_combined_csv()
        
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED!")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
