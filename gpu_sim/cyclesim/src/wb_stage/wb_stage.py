from __future__ import annotations
from dataclasses import dataclass
from typing import Dict
from latch_forward_stage import Instruction, Stage, LatchIF
from wb_buffer import WritebackBuffer, WritebackBufferConfig, RegisterFileConfig

@dataclass
class WritebackStageConfig:
    buffer_config: WritebackBufferConfig
    reg_file_config: RegisterFileConfig

    @classmethod
    def get_default_config(cls) -> WritebackStageConfig:
        return cls(
            buffer_config=WritebackBufferConfig.get_default_config(),
            reg_file_config=RegisterFileConfig.get_default_config()
        )
      
    @classmethod
    def get_config_type_one(cls) -> WritebackStageConfig:
        return cls(
            buffer_config=WritebackBufferConfig.get_config_type_one(),
            reg_file_config=RegisterFileConfig.get_default_config()
        )
      
    @classmethod
    def get_config_type_two(cls) -> WritebackStageConfig:
        return cls(
            buffer_config=WritebackBufferConfig.get_config_type_two(),
            reg_file_config=RegisterFileConfig.get_default_config()
        )
    

class WritebackStage(Stage):
    def __init__(self, config: WritebackStageConfig, behind_latches: Dict[str, LatchIF], fsu_names: list[str] = None):
        super().__init__(name="Writeback_Stage")
        self.behind_latches = behind_latches
        self.ahead_latch = None
        self.forward_ifs_read = None
        self.forward_ifs_write = None

        functional_units_list = []

        self.wb_buffer = WritebackBuffer(
            buffer_config=config.buffer_config,
            regfile_config=config.reg_file_config,
            behind_latches=behind_latches,
            fsu_names=fsu_names
        )

    def compute(self) -> None:
        # Writeback stage does not have functional units to compute
        pass
    
    def tick(self) -> None:
        # Writeback stage tick logic to be implemented
        return self.wb_buffer.tick()
    
    def get_data(self):
        raise NotImplementedError()
    
    def send_output(self) -> None:
        raise NotImplementedError()