from __future__ import annotations

from dataclasses import dataclass
from latch_forward_stage import Stage, LatchIF, Instruction
from arithmetic_functional_unit import IntUnitConfig, FpUnitConfig, SpecialUnitConfig, IntUnit, FpUnit, SpecialUnit


@dataclass
class FunctionalUnitConfig:
    int_unit_count: int
    fp_unit_count: int
    special_unit_count: int

    int_config: IntUnitConfig
    fp_config: FpUnitConfig
    special_config: SpecialUnitConfig

    @classmethod
    def get_default_config(cls) -> FunctionalUnitConfig:
        return cls(
            int_unit_count=1,
            fp_unit_count=1,
            special_unit_count=1,
            int_config=IntUnitConfig.get_default_config(),
            fp_config=FpUnitConfig.get_default_config(),
            special_config=SpecialUnitConfig.get_default_config()
        )

class ExecuteStage(Stage):
    def __init__(self, config: FunctionalUnitConfig):
        super().__init__(name="Execute_Stage")
      
        self.behind_latch = LatchIF(name="IS_EX_Latch")

        self.ahead_latch = None
        self.forward_ifs_read = None
        self.forward_ifs_write = None
        self.cycle = 0

        functional_units_list = []

        for i in range(config.int_unit_count):
            functional_units_list.append(IntUnit(config=config.int_config, num=i))
        for i in range(config.fp_unit_count):
            functional_units_list.append(FpUnit(config=config.fp_config, num=i))
        for i in range(config.special_unit_count):
            functional_units_list.append(SpecialUnit(config=config.special_config, num=i))

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
        in_data = self.behind_latch.pop()

        if isinstance(in_data, Instruction):
            in_data.mark_stage_enter(self.name, self.cycle)

        for fu in self.functional_units.values():
            fu_out_data = fu.tick(in_data)
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
    def create_default_execute_pipeline_stage(cls) -> Stage:
        # execute stage
        functional_unit_config = FunctionalUnitConfig.get_default_config()

        ex_stage = ExecuteStage(config=functional_unit_config)

        return ex_stage