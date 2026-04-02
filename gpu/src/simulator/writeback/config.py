from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Union, Optional, Tuple, List
from bitstring import Bits

# Enums for Writeback Buffer Configuration
class WritebackBufferCount(Enum):
    BUFFER_PER_FSU = 0
    BUFFER_PER_BANK = 1

class WritebackBufferSize(Enum):
    FIXED = 0
    VARIABLE = 1

class WritebackBufferStructure(Enum):
    STACK = 0
    QUEUE = 1
    CIRCULAR = 2

class WritebackBufferPolicy(Enum):
    AGE_PRIORITY = 0
    CAPACITY_PRIORITY = 1
    FSU_PRIORITY = 2

# Writeback File Enum
class WritebackFile(Enum):
    REGISTER_FILE = 1
    PREDICATE_REGISTER_FILE = 2

# Configuration Dataclasses
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
            elif "alu_float" in fsu_name.lower():
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
    def get_config_from_reg_file(cls, reg_file) -> RegisterFileConfig:
        """Create config from RegisterFile instance."""
        return cls(num_banks=reg_file.banks)
    
@dataclass
class PredicateRegisterFileConfig:
    num_banks: int

    @classmethod
    def get_config_from_pred_reg_file(cls, pred_reg_file) -> PredicateRegisterFileConfig:
        """Create config from PredicateRegFile instance."""
        return cls(num_banks=pred_reg_file.banks)

# def generate_register_file_bank_enum(regfile_config: RegisterFileConfig, pred_regfile_config: PredicateRegisterFileConfig) -> Enum:
#     """Dynamically generate an Enum for register file banks based on the number of banks."""
#     members = (
#         {f'PREDICATE_REGISTER_FILE_BANK_{i}': f'pred_regfile_bank_{i}' for i in range(pred_regfile_config.num_banks)}
#         | {f'REGISTER_FILE_BANK_{i}': f'regfile_bank_{i}' for i in range(regfile_config.num_banks)}
#     )
#     return Enum('RegisterFileBank', members)
