from __future__ import annotations
from dataclasses import dataclass
from abc import ABC
from typing import List
from gpu.simulator.src.execute.functional_sub_unit import FunctionalSubUnit, Alu, Mul, Div, AddSub, Sqrt, Trig, InvSqrt
from gpu.simulator.src.compact_queue import CompactQueue
from gpu.simulator.src.latch_forward_stage import Instruction
from gpu.simulator.src.mem.ld_st import Ldst_Fu

@dataclass
class MemBranchUnitConfig:
    ldst_count: int
    branch_count: int

    branch_latency: int

    ldst_buffer_size: int
    ldst_queue_size: int

    @classmethod
    def get_default_config(cls) -> MemBranchUnitConfig:
        return cls(
            ldst_count=1,
            branch_count=1,
            branch_latency=1,
            ldst_buffer_size=1,
            ldst_queue_size=4
        )

@dataclass
class IntUnitConfig:
    alu_count: int
    mul_count: int
    div_count: int
    
    alu_latency: int
    mul_latency: int
    div_latency: int

    @classmethod
    def get_default_config(cls) -> IntUnitConfig:
        return cls(
            alu_count=1,
            mul_count=1,
            div_count=1,
            alu_latency=1,
            mul_latency=2,
            div_latency=17
        )

@dataclass
class FpUnitConfig:
    add_sub_count: int
    mul_count: int
    div_count: int
    sqrt_count: int
    
    add_sub_latency: int
    mul_latency: int
    div_latency: int
    sqrt_latency: int

    @classmethod
    def get_default_config(cls) -> FpUnitConfig:
        return cls(
            add_sub_count=1,
            mul_count=1,
            div_count=1,
            sqrt_count=1,
            add_sub_latency=1,
            mul_latency=4,
            div_latency=24,
            sqrt_latency=20
        )

@dataclass
class SpecialUnitConfig:
    trig_count: int
    inv_sqrt_count: int

    trig_latency: int
    inv_sqrt_latency: int

    @classmethod
    def get_default_config(cls) -> SpecialUnitConfig:
        return cls(
            trig_count=1,
            inv_sqrt_count=1,
            trig_latency=16,
            inv_sqrt_latency=12
        )    
    
class FunctionalUnit(ABC):
    def __init__(self, subunits: list[FunctionalSubUnit], num: int):
        self.name = f"{self.__class__.__name__}_{num}"

        # Convert list of subunits to dict using the names of the subunits as keys
        self.subunits = {subunit.name: subunit for subunit in subunits}    

    def compute(self):
        for subunit in self.subunits.values():
            subunit.compute()

    def tick(self, behind_latch: LatchIF, fust: dict[str, bool]) -> List[Instruction]:
        out_data = {}
        for subunit_name, subunit in self.subunits.items():
            in_data = behind_latch.snoop()
            if isinstance(in_data, Instruction) and in_data.intended_FU == subunit.name:
              out_data[subunit.ex_wb_interface.name] = subunit.tick(behind_latch)
            else:
              out_data[subunit.ex_wb_interface.name] = subunit.tick(None)
            
            # False: subunit is NOT full, and it is ready to accept new input
            # True: subunit is full, and it is NOT ready to accept new input
            # Therefore, we must negate the ready_out value to get the correct status for fust
            fust[subunit_name] = not subunit.ready_out

        return out_data

class MemBranchUnit(FunctionalUnit):
    def __init__(self, config: MemBranchUnitConfig, num: int):
        subunits = []
        for i in range(config.ldst_count):
            subunits.append(Ldst_Fu(wb_buffer_size=config.ldst_buffer_size, ldst_q_size=config.ldst_queue_size, num=i * (num + 1)))
        super().__init__(subunits=subunits, num=num)
    
class IntUnit(FunctionalUnit):
    def __init__(self, config: IntUnitConfig, num: int):
        subunits = []
        for i in range(config.alu_count):
            subunits.append(Alu(latency=config.alu_latency, type_=int, num=i * (num + 1)))
        for i in range(config.mul_count):
            subunits.append(Mul(latency=config.mul_latency, type_=int, num=i * (num + 1)))
        for i in range(config.div_count):
            subunits.append(Div(latency=config.div_latency, type_=int, num=i * (num + 1)))
        super().__init__(subunits=subunits, num=num)

class FpUnit(FunctionalUnit):
    def __init__(self, config: FpUnitConfig, num: int):
        subunits = []
        for i in range(config.add_sub_count):
            subunits.append(AddSub(latency=config.add_sub_latency, type_=float, num=i * (num + 1)))
        for i in range(config.mul_count):
            subunits.append(Mul(latency=config.mul_latency, type_=float, num=i * (num + 1)))
        for i in range(config.div_count):
            subunits.append(Div(latency=config.div_latency, type_=float, num=i * (num + 1)))
        for i in range(config.sqrt_count):
            subunits.append(Sqrt(latency=config.sqrt_latency, type_=float, num=i * (num + 1)))
        super().__init__(subunits=subunits, num=num)

class SpecialUnit(FunctionalUnit):
    def __init__(self, config: SpecialUnitConfig, num: int):
        subunits = []
        for i in range(config.trig_count):
            subunits.append(Trig(latency=config.trig_latency, type_=float, num=i * (num + 1)))
        for i in range(config.inv_sqrt_count):
            subunits.append(InvSqrt(latency=config.inv_sqrt_latency, type_=float, num=i * (num + 1)))

        super().__init__(subunits=subunits, num=num)