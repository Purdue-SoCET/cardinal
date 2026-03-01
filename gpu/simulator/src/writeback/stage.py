from __future__ import annotations
from dataclasses import dataclass
from typing import Dict
from simulator.issue.regfile import RegisterFile
from simulator.latch_forward_stage import Instruction, Stage, LatchIF
from simulator.writeback.writeback_buffer import WritebackBuffer, WritebackBufferCount, WritebackBufferSize, WritebackBufferStructure, WritebackBufferPolicy
from typing import Union, Optional, Tuple, List

@dataclass
class WritebackBufferConfig:
    count_scheme: WritebackBufferCount
    size_scheme: WritebackBufferSize
    structure: WritebackBufferStructure
    primary_policy: WritebackBufferPolicy
    secondary_policy: WritebackBufferPolicy
    size: Union[Dict[str, int], int]  # Can be a fixed size or a dict mapping FSU names to sizes
    fsu_priority: Optional[Dict[str, int]]  # Priority mapping for FSUs

    @staticmethod
    def create_fsu_mappings(fsu_names: list[str]) -> Tuple[Dict[str, int], Dict[str, int]]:
        buffer_sizes = {}
        fsu_priorities = {}

        for fsu_name in fsu_names:
            if "alu_int" in fsu_name.lower():
                buffer_sizes[fsu_name] = 16
                fsu_priorities[fsu_name] = 2
            elif "mul_int" in fsu_name.lower():
                buffer_sizes[fsu_name] = 8
                fsu_priorities[fsu_name] = 2
            elif "div_int" in fsu_name.lower():
                buffer_sizes[fsu_name] = 4
                fsu_priorities[fsu_name] = 1
            elif "addsub_float" in fsu_name.lower():
                buffer_sizes[fsu_name] = 16
                fsu_priorities[fsu_name] = 2
            elif "mul_float" in fsu_name.lower():
                buffer_sizes[fsu_name] = 8
                fsu_priorities[fsu_name] = 1
            elif "div_float" in fsu_name.lower():
                buffer_sizes[fsu_name] = 4
                fsu_priorities[fsu_name] = 0
            elif "sqrt_float" in fsu_name.lower():
                buffer_sizes[fsu_name] = 4
                fsu_priorities[fsu_name] = 3
            elif "trig_float" in fsu_name.lower():
                buffer_sizes[fsu_name] = 4
                fsu_priorities[fsu_name] = 0
            elif "invsqrt_float" in fsu_name.lower():
                buffer_sizes[fsu_name] = 4
                fsu_priorities[fsu_name] = 0
            else:
                raise ValueError(f"Unknown FSU name: {fsu_name}")
            
        return buffer_sizes, fsu_priorities

    def validate_config(self, fsu_names: List[str]) -> bool:
        for name in fsu_names:
            if self.size_scheme == WritebackBufferSize.VARIABLE:
                if not isinstance(self.size, dict) or name not in self.size:
                    raise ValueError(f"Size for FSU '{name}' must be specified in size dict for VARIABLE size scheme.")
            else:
                if not isinstance(self.size, int):
                    raise ValueError("Size must be an integer for FIXED size scheme.")
            if self.primary_policy == WritebackBufferPolicy.FSU_PRIORITY or \
               self.secondary_policy == WritebackBufferPolicy.FSU_PRIORITY:
                if not self.fsu_priority or name not in self.fsu_priority:
                    raise ValueError(f"Priority for FSU '{name}' must be specified in fsu_priority dict when using FSU_PRIORITY policy.")
        
        return True

    @classmethod
    def get_default_config(cls) -> WritebackBufferConfig:
        return cls(
            count_scheme=WritebackBufferCount.BUFFER_PER_FSU,
            size_scheme=WritebackBufferSize.FIXED,
            structure=WritebackBufferStructure.QUEUE,
            primary_policy=WritebackBufferPolicy.CAPACITY_PRIORITY,
            secondary_policy=WritebackBufferPolicy.AGE_PRIORITY,
            size=8,
            fsu_priority=None
        )

    @classmethod
    def get_config_type_one(cls, buffer_sizes: Dict[str, int], fsu_priorities: Dict[str, int]) -> WritebackBufferConfig:
        return cls(
            count_scheme=WritebackBufferCount.BUFFER_PER_FSU,
            size_scheme=WritebackBufferSize.VARIABLE,
            structure=WritebackBufferStructure.CIRCULAR,
            primary_policy=WritebackBufferPolicy.FSU_PRIORITY,
            secondary_policy=WritebackBufferPolicy.CAPACITY_PRIORITY,
            size=buffer_sizes,
            fsu_priority=fsu_priorities
        )
    
    @classmethod
    def get_config_type_two(cls, fsu_priorities: Dict[str, int]) -> WritebackBufferConfig:
        return cls(
            count_scheme=WritebackBufferCount.BUFFER_PER_BANK,
            size_scheme=WritebackBufferSize.FIXED,
            structure=WritebackBufferStructure.STACK,
            primary_policy=WritebackBufferPolicy.AGE_PRIORITY,
            secondary_policy=WritebackBufferPolicy.FSU_PRIORITY,
            size=32,
            fsu_priority=fsu_priorities
        )

@dataclass
class RegisterFileConfig:
    num_banks: int

    @classmethod
    def get_config_from_reg_File(cls, reg_file: RegisterFile) -> RegisterFileConfig:
        return cls(num_banks=reg_file.banks)

class WritebackStage(Stage):
    def __init__(self, 
        wb_config: WritebackBufferConfig, 
        rf_config: RegisterFileConfig, 
        behind_latches: Dict[str, LatchIF], 
        reg_file: RegisterFile,
        fsu_names: list[str] = None
    ):
        super().__init__(name="Writeback_Stage")
        self.behind_latches = behind_latches
        self.ahead_latch = None
        self.forward_ifs_read = None
        self.forward_ifs_write = None
        self.values_to_writeback = {}
        self.num_banks = rf_config.num_banks
        self.reg_file = reg_file

        self.values_to_writeback = {f"bank_{i}": None for i in range(self.num_banks)}


        functional_units_list = []

        self.wb_buffer = WritebackBuffer(
            buffer_config=wb_config,
            regfile_config=rf_config,
            behind_latches=behind_latches,
            fsu_names=fsu_names
        )

    def compute(self) -> None:
        # Writeback stage does not have functional units to compute
        pass
    
    def tick(self) -> None:
        # Writeback stage tick logic to be implemented
        self._write_to_reg_file()
        self.values_to_writeback = self.wb_buffer.tick()
        if self.values_to_writeback is not None and len(self.values_to_writeback) != self.num_banks:
            print(f"Error: Expected {self.num_banks} banks, but got {len(self.values_to_writeback)}")
            raise ValueError("Number of banks in values_to_writeback does not match num_banks.")


    
    def get_data(self):
        raise NotImplementedError()
    
    def send_output(self) -> None:
        raise NotImplementedError()

    def _write_to_reg_file(self):
        if self.values_to_writeback is None:
            return
        
        for _, instr in self.values_to_writeback.items():
            if instr is not None:
                for i in range(32):
                    if instr.predicate[i].bin == 0b0:
                        continue
                    self.reg_file.write_thread_gran(
                        dest_operand=instr.rd,
                        data=instr.wdat[i],
                        thread_id=i,
                        warp_id=instr.warp_id
                    )

    @classmethod
    def create_pipeline_stage(cls, wb_config: WritebackBufferConfig, rf_config: RegisterFileConfig, ex_stage_ahead_latches: Dict[str, LatchIF], reg_file: RegisterFile, fsu_names: list[str]) -> WritebackStage:
        return cls(wb_config=wb_config, rf_config=rf_config, behind_latches=ex_stage_ahead_latches, reg_file=reg_file, fsu_names=fsu_names)