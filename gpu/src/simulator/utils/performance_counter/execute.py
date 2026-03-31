import pandas as pd
from common.custom_enums_multi import Op
from simulator.instruction import Instruction
from simulator.utils.performance_counter.perf_counter_base import PerfCounterBase

class ExecutePerfCount(PerfCounterBase):
    def __init__(self, name: str):
        super().__init__(name)
        self.instruction_counts: dict[Op, int] = {}
        self.overflow_counts: dict[Op, int] = {}

    def _record_unit_cycle(self, *, instr: Instruction, overflow: bool, **kwargs) -> None:
        if instr is not None:
            self.instruction_counts[instr.opcode] = self.instruction_counts.get(instr.opcode, 0) + 1
        else:
            self.instruction_counts[None] = self.instruction_counts.get(None, 0) + 1

        if overflow:
            self.overflow_counts[instr.opcode] = self.overflow_counts.get(instr.opcode, 0) + 1

    def _extra_summary(self) -> dict[str, Any]:
        
        return {
            "instruction_counts": self.instruction_counts,
            "overflow_counts": self.overflow_counts,
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
    