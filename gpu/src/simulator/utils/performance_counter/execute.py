import pandas as pd
from typing import Any
from common.custom_enums_multi import Op
from simulator.instruction import Instruction
from simulator.utils.performance_counter.perf_counter_base import PerfCounterBase

class ExecutePerfCount(PerfCounterBase):
    def __init__(self, name: str):
        super().__init__(name)
        self.instruction_counts: dict[Op, int] = {}
        self.overflow_counts: dict[Op, int] = {}

    def _record_unit_cycle(self, *, instr: Instruction = None, overflow: bool = False, **kwargs) -> None:
        if instr is not None:
            self.instruction_counts[instr.opcode] = self.instruction_counts.get(instr.opcode, 0) + 1
        else:
            self.instruction_counts[None] = self.instruction_counts.get(None, 0) + 1

        if overflow and instr is not None:
            self.overflow_counts[instr.opcode] = self.overflow_counts.get(instr.opcode, 0) + 1

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
        
        return {
            "instruction_summary": instr_summary,
            "overflow_summary": overflow_summary,
        }
    
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
    
    def increment_overflow(self, opcode: Op) -> None:
        """Increment overflow counter for a specific operation"""
        if opcode in self.overflow:
            self.overflow[opcode] += 1
        else:
            self.overflow[opcode] = 1
    