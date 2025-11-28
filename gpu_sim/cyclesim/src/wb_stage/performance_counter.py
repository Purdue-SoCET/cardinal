import pandas as pd
import numpy as np
from typing import Optional, List
from custom_enums_multi import Op
from latch_forward_stage import Instruction

class PerfCount:
    def __init__(self, name: str):
        self.name = f"{name}_Performance_Counter"
        self.total_cycles: int = 0
        self.stall_cycles: int = 0
        self.buffer_full_cycles: int = 0
        self.store_cycles: int = 0
        self.writeback_cycles: int = 0
        
        # Tracking lists for computing statistics
        self._occupancy_samples: List[int] = []
        self._instruction_ages: List[int] = []
        
        # Computed statistics (will be calculated at end)
        self.average_buffer_occupancy: float = 0.0
        self.average_instruction_age: float = 0.0
        self.percentile_90_buffer_occupancy: float = 0.0
        self.percentile_99_buffer_occupancy: float = 0.0
    
    def increment(
        self, 
        cycle: int,
        buffer_occupancy: int,
        buffer_capacity: int,
        stored_this_cycle: bool,
        writeback_this_cycle: bool,
        instructions_in_buffer: Optional[List[Instruction]] = None
    ) -> None:
        """
        Increment performance counters for the Writeback Buffer.
        
        Args:
            cycle: Current simulation cycle
            buffer_occupancy: Current number of entries in the buffer
            buffer_capacity: Maximum capacity of the buffer
            stored_this_cycle: Whether a store operation occurred this cycle
            writeback_this_cycle: Whether a writeback operation occurred this cycle
            instructions_in_buffer: List of instructions currently in the buffer (for age tracking)
        """
        self.total_cycles += 1
        
        # Track buffer occupancy
        self._occupancy_samples.append(buffer_occupancy)
        
        # Check if buffer is full
        if buffer_occupancy >= buffer_capacity:
            self.buffer_full_cycles += 1
        
        # Track store operations
        if stored_this_cycle:
            self.store_cycles += 1
        
        # Track writeback operations
        if writeback_this_cycle:
            self.writeback_cycles += 1
        
        # Track stall cycles (when buffer is full and can't accept new data)
        if buffer_occupancy >= buffer_capacity:
            self.stall_cycles += 1
        
        # Track instruction ages in buffer
        if instructions_in_buffer is not None:
            for instr in instructions_in_buffer:
                if instr is not None and instr.issued_cycle is not None:
                    age = cycle - instr.issued_cycle
                    self._instruction_ages.append(age)
    
    def finalize_statistics(self) -> None:
        """
        Calculate final statistics from collected samples.
        Should be called at the end of simulation before outputting CSV.
        """
        if len(self._occupancy_samples) > 0:
            self.average_buffer_occupancy = float(np.mean(self._occupancy_samples))
            self.percentile_90_buffer_occupancy = float(np.percentile(self._occupancy_samples, 90))
            self.percentile_99_buffer_occupancy = float(np.percentile(self._occupancy_samples, 99))
        
        if len(self._instruction_ages) > 0:
            self.average_instruction_age = float(np.mean(self._instruction_ages))

    def to_csv(self, directory: str = ".") -> None:
        """Output performance counter statistics to CSV file."""
        # Finalize statistics before saving
        self.finalize_statistics()
        
        path = f"{directory}/{self.name}_Stats.csv"
        
        # Create a dictionary with only the statistics (not the tracking lists)
        stats_dict = {
            'name': self.name,
            'total_cycles': self.total_cycles,
            'stall_cycles': self.stall_cycles,
            'buffer_full_cycles': self.buffer_full_cycles,
            'store_cycles': self.store_cycles,
            'writeback_cycles': self.writeback_cycles,
            'average_buffer_occupancy': self.average_buffer_occupancy,
            'average_instruction_age': self.average_instruction_age,
            'percentile_90_buffer_occupancy': self.percentile_90_buffer_occupancy,
            'percentile_99_buffer_occupancy': self.percentile_99_buffer_occupancy
        }
        
        df = pd.DataFrame([stats_dict])
        df.to_csv(path, index=False)
    
    @staticmethod
    def to_combined_csv(perf_counts: List['PerfCount'], directory: str) -> None:
        """Combine multiple PerfCount instances into a single CSV"""
        
        # Finalize all statistics before combining
        for pc in perf_counts:
            pc.finalize_statistics()
        
        # Create list of dictionaries with only statistics
        data = []
        for pc in perf_counts:
            stats_dict = {
                'name': pc.name,
                'total_cycles': pc.total_cycles,
                'stall_cycles': pc.stall_cycles,
                'buffer_full_cycles': pc.buffer_full_cycles,
                'store_cycles': pc.store_cycles,
                'writeback_cycles': pc.writeback_cycles,
                'average_buffer_occupancy': pc.average_buffer_occupancy,
                'average_instruction_age': pc.average_instruction_age,
                'percentile_90_buffer_occupancy': pc.percentile_90_buffer_occupancy,
                'percentile_99_buffer_occupancy': pc.percentile_99_buffer_occupancy
            }
            data.append(stats_dict)
        
        df = pd.DataFrame(data)
        df.to_csv(f"{directory}/Combined_WbStage_PerfCount_Stats.csv", index=False)
    