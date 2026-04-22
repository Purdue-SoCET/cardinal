import pandas as pd
from typing import Any
from bitstring import Bits
from common.custom_enums_multi import Op
from simulator.instruction import Instruction
from simulator.utils.performance_counter.perf_counter_base import PerfCounterBase

class ExecutePerfCount(PerfCounterBase):
    def __init__(self, name: str):
        super().__init__(name)
        self.instruction_counts: dict[Op, int] = {}
        self.overflow_counts: dict[Op, int] = {}
        self.overflow_details: list[dict[str, Any]] = []  # Track PC and thread count for each overflow

    def _record_unit_cycle(self, *, instr: Instruction, overflow: bool = False, pc: int = None, overflow_thread_count: int = None, **kwargs) -> None:
        if instr is not None:
            self.instruction_counts[instr.opcode] = self.instruction_counts.get(instr.opcode, 0) + 1
        else:
            self.instruction_counts[None] = self.instruction_counts.get(None, 0) + 1

        if overflow and instr is not None:
            self.overflow_counts[instr.opcode] = self.overflow_counts.get(instr.opcode, 0) + 1
            # Record overflow details for later reporting
            self.overflow_details.append({
                'opcode': instr.opcode.name if hasattr(instr.opcode, 'name') else str(instr.opcode),
                'pc': pc if pc is not None else 0,
                'thread_count': overflow_thread_count if overflow_thread_count is not None else 1,
            })

    def _extra_summary(self) -> dict[str, Any]:
        """Convert instruction and overflow counts to JSON-serializable format for Parquet export.
        
        Converts Op enum keys to strings and filters out None values with warnings.
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
        
        # Convert overflow counts: Op enum -> string, filter out None
        overflow_counts_str = {}
        if None in self.overflow_counts:
            print(f"Warning: {self.unit_name} has overflow_counts[None]={self.overflow_counts[None]}, filtering out")
        for opcode, count in self.overflow_counts.items():
            if opcode is None:
                continue
            if count is None:
                print(f"Warning: {self.unit_name} overflow_counts[{opcode}] is None, filtering out")
                continue
            opcode_str = opcode.name if hasattr(opcode, 'name') else str(opcode)
            overflow_counts_str[opcode_str] = count
        
        # Polars can't handle empty dicts, so represent them as strings
        instr_summary = str(instr_counts_str) if instr_counts_str else "no_instructions"
        overflow_summary = str(overflow_counts_str) if overflow_counts_str else "no_overflows"
        
        # Format overflow details: list of dicts with opcode, pc, and thread count
        overflow_details_str = "no_overflows"
        if self.overflow_details:
            overflow_details_str = str([
                {'op': d['opcode'], 'pc': d['pc'], 'num_threads': d['thread_count']} 
                for d in self.overflow_details
            ])
        
        return {
            "instruction_summary": instr_summary,
            "overflow_summary": overflow_summary,
            "overflow_details": overflow_details_str,
        }
    
class BranchPerfCount(ExecutePerfCount):
    def __init__(self, name: str):
        super().__init__(name)
        self.divergent_branches: int = 0
        self.non_divergent_branches: int = 0
        self.total_branches: int = 0

    def record_branch(self, wdat_pred: list) -> None:
        """Call after compute() with the wdat_pred result to classify the branch."""
        if wdat_pred is None:
            return
        self.total_branches += 1
        all_one = all(b == Bits(uint=1, length=1) for b in wdat_pred)
        all_zero = all(b == Bits(uint=0, length=1) for b in wdat_pred)
        if all_one or all_zero:
            self.non_divergent_branches += 1
        else:
            self.divergent_branches += 1

    def _extra_summary(self) -> dict[str, Any]:
        base = super()._extra_summary()
        base.update({
            "total_branches": self.total_branches,
            "divergent_branches": self.divergent_branches,
            "non_divergent_branches": self.non_divergent_branches,
            "divergent_branch_rate": self._safe_div(self.divergent_branches, self.total_branches),
            "non_divergent_branch_rate": self._safe_div(self.non_divergent_branches, self.total_branches),
        })
        return base

    def _reset_unit_counters(self) -> None:
        super()._reset_unit_counters()
        self.divergent_branches = 0
        self.non_divergent_branches = 0
        self.total_branches = 0


    def increment(self, instr: Instruction, ready_out: bool = True, ex_wb_interface_ready: bool = True) -> None:
        self.total_instructions += 1
        self.total_cycles += 1

        if not ex_wb_interface_ready:
            self.stall_cycles += 1 
          
        if not ready_out:
            self.pipeline_full_cycles += 1
            
        if instr is None:
            self.nop_cycles += 1
        elif instr.opcode in self.instruction_types:
            self.instruction_types[instr.opcode] += 1
        else:
            self.instruction_types[instr.opcode] = 1
        
        if instr is not None and ready_out:
            self.utilization_cycles += 1
    