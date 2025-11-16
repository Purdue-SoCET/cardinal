from __future__ import annotations
from dataclasses import dataclass
from abc import ABC
from typing import List
from functional_sub_unit import FunctionalSubUnit, Alu, Mul, Div, AddSub, Sqrt, Trig, InvSqrt
from compact_queue import CompactQueue
from latch_forward_stage import Instruction

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

class ArithmeticFunctionalUnit(ABC):
    def __init__(self, subunits: list[FunctionalSubUnit], num: int):
        self.name = f"{self.__class__.__name__}_{num}"

        # Convert list of subunits to dict using the names of the subunits as keys
        self.subunits = {subunit.name: subunit for subunit in subunits}        

    def compute(self):
        for subunit in self.subunits.values():
            subunit.compute()

    def tick(self, in_data: Instruction) -> List[Instruction]:
        out_data = {}
        for subunit in self.subunits.values():
            if isinstance(in_data, Instruction) and in_data.intended_FSU == subunit.name:
              out_data[subunit.ex_wb_interface.name] = subunit.tick(in_data)
            else:
              out_data[subunit.ex_wb_interface.name] = subunit.tick(None)

        return out_data

class IntUnit(ArithmeticFunctionalUnit):
    def __init__(self, config: IntUnitConfig, num: int):
        subunits = []
        for i in range(config.alu_count):
            subunits.append(Alu(latency=config.alu_latency, type_=int, num=i * (num + 1)))
        for i in range(config.mul_count):
            subunits.append(Mul(latency=config.mul_latency, type_=int, num=i * (num + 1)))
        for i in range(config.div_count):
            subunits.append(Div(latency=config.div_latency, type_=int, num=i * (num + 1)))
        super().__init__(subunits=subunits, num=num)

class FpUnit(ArithmeticFunctionalUnit):
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

class SpecialUnit(ArithmeticFunctionalUnit):
    def __init__(self, config: SpecialUnitConfig, num: int):
        subunits = []
        for i in range(config.trig_count):
            subunits.append(Trig(latency=config.trig_latency, type_=float, num=i * (num + 1)))
        for i in range(config.inv_sqrt_count):
            subunits.append(InvSqrt(latency=config.inv_sqrt_latency, type_=float, num=i * (num + 1)))

        super().__init__(subunits=subunits, num=num)