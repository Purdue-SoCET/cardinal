import numpy as np
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
    - Base metrics: total_cycles, busy_cycles, stall_cycles, idle_cycles, etc.
    """
    
    def __init__(self, name: str):
        super().__init__(name)
        self.instruction_counts: dict[Op, int] = {}
        self.instruction_latencies: dict[Op, list[int]] = {}  # Track latencies per opcode
        self.current_instruction_cycle: dict[int, int] = {}  # Map instruction ID to entry cycle
        
    def _record_unit_cycle(self, *, instr: Instruction, cycle: int = None, **kwargs) -> None:
        """Record a cycle for LDST unit.
        
        Parameters
        ----------
        instr : Instruction
            The instruction being processed this cycle
        cycle : int
            Current simulation cycle (used to calculate latency when instruction completes)
        **kwargs : Any additional parameters
        """
        if instr is not None:
            # Track instruction count
            self.instruction_counts[instr.opcode] = self.instruction_counts.get(instr.opcode, 0) + 1
            
            # Track instruction entry (use id() as unique identifier)
            instr_id = id(instr)
            if instr_id not in self.current_instruction_cycle and cycle is not None:
                self.current_instruction_cycle[instr_id] = cycle
        else:
            self.instruction_counts[None] = self.instruction_counts.get(None, 0) + 1
    
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
        
        return {
            "instruction_summary": instr_summary,
            "avg_latency": avg_latency,
            "p99_latency": p99_latency,
        }
