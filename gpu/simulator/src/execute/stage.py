from __future__ import annotations

from dataclasses import dataclass
from simulator.latch_forward_stage import Stage, LatchIF, Instruction
from simulator.execute.functional_unit import MemBranchUnitConfig, IntUnitConfig, FpUnitConfig, SpecialUnitConfig, IntUnit, FpUnit, SpecialUnit, MemBranchUnit
from typing import Dict, Optional


@dataclass
class FunctionalUnitConfig:
    int_unit_count: int
    fp_unit_count: int
    special_unit_count: int
    membranch_unit_count: int

    int_config: IntUnitConfig
    fp_config: FpUnitConfig
    special_config: SpecialUnitConfig
    membranch_config: MemBranchUnitConfig

    @classmethod
    def get_default_config(cls) -> FunctionalUnitConfig:
        return cls(
            int_unit_count=1,
            fp_unit_count=1,
            special_unit_count=1,
            membranch_unit_count=1,
            int_config=IntUnitConfig.get_default_config(),
            fp_config=FpUnitConfig.get_default_config(),
            special_config=SpecialUnitConfig.get_default_config(),
            membranch_config=MemBranchUnitConfig.get_default_config()
        )
    
    @classmethod
    def get_config(cls, int_config: IntUnitConfig, fp_config: FpUnitConfig, special_config: SpecialUnitConfig, membranch_config: MemBranchUnitConfig, int_unit_count: int =1, fp_unit_count: int =1, special_unit_count: int =1, membranch_unit_count: int =1) -> FunctionalUnitConfig:
        return cls(
            int_unit_count=int_unit_count,
            fp_unit_count=fp_unit_count,
            special_unit_count=special_unit_count,
            membranch_unit_count=membranch_unit_count,
            int_config=int_config,
            fp_config=fp_config,
            special_config=special_config,
            membranch_config=membranch_config
        )
    
    def generate_fust_dict(self) -> Dict[str, bool]:
        fust = {}
        for i in range(self.int_unit_count):
            int_unit = IntUnit(config=self.int_config, num=i)
            for fsu_name in int_unit.subunits.keys():
                fust[fsu_name] = True
        for i in range(self.fp_unit_count):
            fp_unit = FpUnit(config=self.fp_config, num=i)
            for fsu_name in fp_unit.subunits.keys():
                fust[fsu_name] = True
        for i in range(self.special_unit_count):
            special_unit = SpecialUnit(config=self.special_config, num=i)
            for fsu_name in special_unit.subunits.keys():
                fust[fsu_name] = True
        for i in range(self.membranch_unit_count):
            membranch_unit = MemBranchUnit(config=self.membranch_config, num=i)
            for fsu_name in membranch_unit.subunits.keys():
                fust[fsu_name] = True
                
        return fust

class ExecuteStage(Stage):
    def __init__(self, config: FunctionalUnitConfig, fust: Dict[str, bool]):
        super().__init__(name="Execute_Stage")
      
        self.behind_latch = LatchIF(name="IS_EX_Latch")

        self.ahead_latch = None
        self.forward_ifs_read = None
        self.forward_ifs_write = None
        self.cycle = 0

        self.fust = fust

        functional_units_list = []

        for i in range(config.int_unit_count):
            functional_units_list.append(IntUnit(config=config.int_config, num=i))
        for i in range(config.fp_unit_count):
            functional_units_list.append(FpUnit(config=config.fp_config, num=i))
        for i in range(config.special_unit_count):
            functional_units_list.append(SpecialUnit(config=config.special_config, num=i))
        for i in range(config.membranch_unit_count):
            functional_units_list.append(MemBranchUnit(config=config.membranch_config, num=i))

        self.functional_units = {fu.name: fu for fu in functional_units_list}

        self.ahead_latches = {}
        self.fsu_perf_counts = {}

        for fu_name, fu in self.functional_units.items():
            for fsu_name, fsu in fu.subunits.items():
                self.ahead_latches[fsu.ex_wb_interface.name] = fsu.ex_wb_interface
                self.fsu_perf_counts[fsu.name] = fsu.perf_count
              

    def compute(self) -> None:
        # Dispatch to functional units
        for fu in self.functional_units.values():
            fu.compute()
        

    def tick(self) -> None:
        # Tick all functional units
        for fu in self.functional_units.values():
            in_data = self.behind_latch.snoop()

            if isinstance(in_data, Instruction):
                if in_data.rd.int == 53:
                    abcHI = 1
                in_data.mark_stage_enter(self.name, self.cycle)
            
            fu_out_data = fu.tick(self.behind_latch, fust=self.fust)

            new_in_data = self.behind_latch.snoop()

            if not (new_in_data is in_data) and isinstance(new_in_data, Instruction):
                in_data.mark_stage_enter(self.name, self.cycle)


            for name, out_data in fu_out_data.items():
                # print(f"[{self.name}] Cycle #{self.cycle}: FSU output on latch {name}: {out_data}")
                if out_data is not False:
                    push_success = self.ahead_latches[name].push(out_data)
                    if not push_success:
                        raise RuntimeError(f"[{self.name}] Unable to push data to ahead latch {self.ahead_latches[name].name}")
                    if isinstance(out_data, Instruction):
                        out_data.mark_stage_exit(self.name, self.cycle)

        self.cycle += 1
    
    def get_data(self) -> Optional[Instruction]:
        raise NotImplementedError()
    
    def send_output(self) -> None:
        raise NotImplementedError()
 

    @classmethod
    def create_pipeline_stage(cls, functional_unit_config: FunctionalUnitConfig, fust: Dict[str, bool]) -> ExecuteStage:
        # execute stage
        ex_stage = ExecuteStage(config=functional_unit_config, fust=fust)

        return ex_stage