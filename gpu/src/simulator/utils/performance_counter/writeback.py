from __future__ import annotations

from typing import Any, Optional
import statistics

from simulator.utils.performance_counter.perf_counter_base import PerfCounterBase
from simulator.instruction import Instruction


class WritebackPerfCount(PerfCounterBase):
    """Performance counter for individual Writeback Buffers.
    
    Tracks metrics for each buffer in the WritebackBuffer:
    - Average and 99th percentile buffer occupancy
    - Number of cycles where buffer is full
    - Number of cycles where instructions are stored to buffer
    - Number of cycles where instructions are written to register file
    - Average and 99th percentile instruction latency (time from entry to exit)
    """
    
    def __init__(self, name: str, enabled: bool = True) -> None:
        """Initialize WritebackPerfCount for a specific buffer.
        
        Parameters
        ----------
        name    : Buffer name (e.g., "fsu_0", "regfile_bank_1")
        enabled : Enable/disable performance tracking
        """
        super().__init__(name, enabled)
        
        # Per-cycle accumulators
        self.occupancy_history: list[int] = []  # Buffer occupancy each cycle
        self.full_cycles: int = 0  # Cycles where buffer is at capacity
        self.store_cycles: int = 0  # Cycles where instruction is stored to buffer
        self.writeback_cycles: int = 0  # Cycles where instruction exits to register file
        
        # Instruction latency tracking
        self.instruction_latencies: list[int] = []  # Latency for each instruction that exits
        
        # Derived statistics (populated by finalize)
        self.avg_occupancy: float = 0.0
        self.occupancy_p99: float = 0.0
        self.avg_latency: float = 0.0
        self.latency_p99: float = 0.0
        self.store_rate: float = 0.0
        self.writeback_rate: float = 0.0
        self.full_rate: float = 0.0
    
    def _record_unit_cycle(
        self,
        *,
        buffer_occupancy: int = 0,
        buffer_capacity: int = 1,
        stored_this_cycle: bool = False,
        writeback_this_cycle: bool = False,
        **kwargs
    ) -> None:
        """Record performance metrics for one cycle.
        
        Parameters
        ----------
        buffer_occupancy      : Current number of instructions in buffer
        buffer_capacity       : Total capacity of buffer
        stored_this_cycle     : True if instruction was stored to buffer this cycle
        writeback_this_cycle  : True if instruction was written to register file this cycle
        **kwargs              : Additional unused keyword arguments
        """
        # Track occupancy
        self.occupancy_history.append(buffer_occupancy)
        
        # Track full cycles
        if buffer_occupancy >= buffer_capacity:
            self.full_cycles += 1
        
        # Track store cycles
        if stored_this_cycle:
            self.store_cycles += 1
        
        # Track writeback cycles
        if writeback_this_cycle:
            self.writeback_cycles += 1
    
    def record_instruction_latency(self, entry_cycle: int, exit_cycle: int) -> None:
        """Record latency for an instruction that exited the buffer.
        
        Parameters
        ----------
        entry_cycle : Cycle when instruction entered the buffer
        exit_cycle  : Cycle when instruction exited the buffer
        """
        if entry_cycle is not None:
            latency = exit_cycle - entry_cycle
            self.instruction_latencies.append(latency)
    
    def _extra_summary(self) -> dict[str, Any]:
        """Compute and return derived statistics for finalized summary."""
        # Calculate occupancy statistics
        if self.occupancy_history:
            self.avg_occupancy = sum(self.occupancy_history) / len(self.occupancy_history)
            # Calculate 99th percentile occupancy
            if len(self.occupancy_history) >= 100:
                # Use quantiles for 99th percentile
                quantiles = statistics.quantiles(self.occupancy_history, n=100)
                self.occupancy_p99 = quantiles[98]  # 99th percentile is at index 98
            else:
                # For small samples, use max
                self.occupancy_p99 = max(self.occupancy_history) if self.occupancy_history else 0
        
        # Calculate instruction latency statistics
        if self.instruction_latencies:
            self.avg_latency = sum(self.instruction_latencies) / len(self.instruction_latencies)
            # Calculate 99th percentile latency
            if len(self.instruction_latencies) >= 100:
                quantiles = statistics.quantiles(self.instruction_latencies, n=100)
                self.latency_p99 = quantiles[98]  # 99th percentile is at index 98
            else:
                # For small samples, use max
                self.latency_p99 = max(self.instruction_latencies) if self.instruction_latencies else 0
        
        # Calculate rates
        self.store_rate = self._safe_div(self.store_cycles, self.total_cycles)
        self.writeback_rate = self._safe_div(self.writeback_cycles, self.total_cycles)
        self.full_rate = self._safe_div(self.full_cycles, self.total_cycles)
        
        return {
            "full_cycles": self.full_cycles,
            "full_rate": self.full_rate,
            "store_cycles": self.store_cycles,
            "store_rate": self.store_rate,
            "writeback_cycles": self.writeback_cycles,
            "writeback_rate": self.writeback_rate,
            "avg_occupancy": self.avg_occupancy,
            "occupancy_p99": self.occupancy_p99,
            "num_instructions_exited": len(self.instruction_latencies),
            "avg_latency": self.avg_latency,
            "latency_p99": self.latency_p99,
        }
    
    def _reset_unit_counters(self) -> None:
        """Reset all unit-specific counters."""
        self.occupancy_history.clear()
        self.full_cycles = 0
        self.store_cycles = 0
        self.writeback_cycles = 0
        self.instruction_latencies.clear()
        
        self.avg_occupancy = 0.0
        self.occupancy_p99 = 0.0
        self.avg_latency = 0.0
        self.latency_p99 = 0.0
        self.store_rate = 0.0
        self.writeback_rate = 0.0
        self.full_rate = 0.0
