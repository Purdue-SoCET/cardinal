import pandas as pd
from custom_enums_multi import Op
from latch_forward_stage import Instruction

class PerfCount:
    def __init__(self, name: str):
        self.name = f"{name}_Performance_Counter"
        self.total_cycles: int = 0
        self.stall_cycles: int = 0
        self.pipeline_full_cycles: int = 0
        self.nop_cycles: int = 0
        self.utilization_cycles: int = 0
        self.total_instructions: int = 0
        self.instruction_types: dict[Op, int] = {}
        self.overflow: dict[Op, int] = {}
    
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

    def to_csv(self, directory: str = ".") -> None:
        path = f"{directory}/{self.name}_Stats.csv"
        df = pd.DataFrame([vars(self)])
        df.to_csv(path, index=False)
    
    @staticmethod
    def to_combined_csv(perf_counts: list['PerfCount'], directory: str) -> None:
        """Combine multiple PerfCount instances into a single CSV"""
        
        data = [vars(pc) for pc in perf_counts]
        df = pd.DataFrame(data)
        df.to_csv(f"{directory}/Combined_ExStage_PerfCount_Stats.csv", index=False)
    