import numpy as np
import statistics
from typing import Any
from common.custom_enums_multi import Op
from simulator.instruction import Instruction
from simulator.utils.performance_counter.perf_counter_base import PerfCounterBase


class LdstPerfCount(PerfCounterBase):
    """Performance counters for Load/Store functional units (Ldst_Fu).
    
    Tracks:
    - Instruction opcode distribution
    - Average latency to service memory requests
    - 99th percentile (1% high) latency to service memory requests
    - Queue occupancy metrics (average, 99th percentile, full cycles)
    - Base metrics: total_cycles, busy_cycles, stall_cycles, idle_cycles, etc.
    """
    
    def __init__(self, name: str):
        super().__init__(name)
        self.instruction_counts: dict[Op, int] = {}
        self.instruction_latencies: dict[Op, list[int]] = {}  # Track latencies per opcode
        self.current_instruction_cycle: dict[int, int] = {}  # Map instruction ID to entry cycle
        self.q_occupancy_history: list[int] = []  # Queue occupancy per cycle
        self.q_full_cycles: int = 0  # Cycles where queue was full
        
    def _record_unit_cycle(self, *, instr: Instruction, cycle: int = None, q_occupancy: int = 0, q_capacity: int = 1, **kwargs) -> None:
        """Record a cycle for LDST unit.
        
        Parameters
        ----------
        instr : Instruction
            The instruction being processed this cycle
        cycle : int
            Current simulation cycle (used to calculate latency when instruction completes)
        q_occupancy : int
            Current number of entries in the LDST queue
        q_capacity : int
            Maximum capacity of the LDST queue
        **kwargs : Any additional parameters
        """
        if instr is not None:
            if self.unit_name not in [entry['fu'] for entry in instr.fu_entries]:
                # Track instruction count
                instr.mark_fu_enter(self.unit_name, cycle)  # Mark the instruction with the cycle it entered this unit
                self.instruction_counts[instr.opcode] = self.instruction_counts.get(instr.opcode, 0) + 1
            
            # Track instruction entry (use id() as unique identifier)
            instr_id = id(instr)
            if instr_id not in self.current_instruction_cycle and cycle is not None:
                self.current_instruction_cycle[instr_id] = cycle
        else:
            self.instruction_counts[None] = self.instruction_counts.get(None, 0) + 1
        
        # Track queue occupancy
        self.q_occupancy_history.append(q_occupancy)
        
        # Track full cycles
        if q_occupancy >= q_capacity:
            self.q_full_cycles += 1
    
    def record_instruction_completion(self, instr: Instruction, completion_cycle: int) -> None:
        """Record when an instruction completes (call when moving to wb_buffer).
        
        Parameters
        ----------
        instr : Instruction
            The instruction that completed
        completion_cycle : int
            The cycle when the instruction completed
        """
        if instr is None:
            return
            
        instr_id = id(instr)
        
        # Calculate latency if we have entry cycle
        if instr_id in self.current_instruction_cycle:
            entry_cycle = self.current_instruction_cycle[instr_id]
            latency = completion_cycle - entry_cycle
            
            # Track latency for this opcode
            if instr.opcode not in self.instruction_latencies:
                self.instruction_latencies[instr.opcode] = []
            self.instruction_latencies[instr.opcode].append(latency)
            
            # Clean up entry tracking
            del self.current_instruction_cycle[instr_id]
    
    def _extra_summary(self) -> dict[str, Any]:
        """Convert tracked metrics to JSON-serializable format for Parquet export.
        
        Returns
        -------
        dict[str, Any]
            Summary dict containing:
            - instruction_summary: dict of opcode counts
            - avg_latency: average latency in cycles for all memory requests
            - p99_latency: 99th percentile latency in cycles (1% high latency)
            - avg_ldst_q_occupancy: average queue occupancy
            - 99p_ldst_q_occupancy: 99th percentile queue occupancy
            - num_q_full_cycles: number of cycles where queue was at capacity
        """
        # Convert instruction counts: Op enum -> string, filter out None
        instr_counts_str = {}
        if None in self.instruction_counts:
            print(f"Warning: {self.unit_name} has instruction_counts[None]={self.instruction_counts[None]}, filtering out")
        for opcode, count in self.instruction_counts.items():
            if opcode is None:
                continue
            if count is None:
                print(f"Warning: {self.unit_name} instruction_counts[{opcode}] is None, filtering out")
                continue
            opcode_str = opcode.name if hasattr(opcode, 'name') else str(opcode)
            instr_counts_str[opcode_str] = count
        
        instr_summary = str(instr_counts_str) if instr_counts_str else "no_instructions"
        
        # Calculate average and 99th percentile latencies
        avg_latency = 0.0
        p99_latency = 0.0
        
        # Collect all latencies across all opcodes
        all_latencies = []
        for opcode, latencies in self.instruction_latencies.items():
            if latencies:
                all_latencies.extend(latencies)
        
        if all_latencies:
            avg_latency = float(np.mean(all_latencies))
            p99_latency = float(np.percentile(all_latencies, 99))
        
        # Calculate queue occupancy metrics
        avg_ldst_q_occupancy = 0.0
        p99_ldst_q_occupancy = 0.0
        
        if self.q_occupancy_history:
            avg_ldst_q_occupancy = float(np.mean(self.q_occupancy_history))
            p99_ldst_q_occupancy = float(np.percentile(self.q_occupancy_history, 99))
        
        return {
            "instruction_summary": instr_summary,
            "avg_latency": avg_latency,
            "p99_latency": p99_latency,
            "avg_ldst_q_occupancy": avg_ldst_q_occupancy,
            "99p_ldst_q_occupancy": p99_ldst_q_occupancy,
            "num_q_full_cycles": self.q_full_cycles,
        }
