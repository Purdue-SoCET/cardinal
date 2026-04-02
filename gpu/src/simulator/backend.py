# from simulator.execute.arithmetic_functional_unit import IntUnitConfig, FpUnitConfig, SpecialUnitConfig
# from simulator.execute.stage import ExecuteStage
# from simulator.writeback.stage import WritebackStage, WritebackBufferConfig, RegisterFileConfig
# from simulator.execute.stage import FunctionalUnitConfig

# # Step 0: Create desired configuration classmethods in the respective files:
#     # IntUnitConfig -> /ex_stage/arithmetic_functional_unit.py
#     # FpUnitConfig -> /ex_stage/arithmetic_functional_unit.py
#     # SpecialUnitConfig -> /ex_stage/arithmetic_functional_unit.py
#     # FunctionalUnitConfig -> /ex_stage/execute_stage.py
#     # WritebackBufferConfig -> /wb_stage/wb_stage.py
#     # RegisterFileConfig -> /wb_stage/wb_stage.py

#     # Only default configurations are provided in this example. You can follow the pattern to create custom configurations as needed.
#     # Please do not use the constructors directly; always use the classmethods to ensure maintainability and consistency.

# # Step 1: Create Configurations using classmethods
#     # I am using default configurations here, but custom configurations can be created as neede by following Step 0.

# # for the functional unit config, you can do this:
# functional_unit_config = FunctionalUnitConfig.get_default_config()
# fust = functional_unit_config.generate_fust_dict()

# # OR, you can do this (same outcome):
# int_config = IntUnitConfig.get_default_config()
# fp_config = FpUnitConfig.get_default_config()
# special_config = SpecialUnitConfig.get_default_config()
# functional_unit_config = FunctionalUnitConfig.get_config(
#     int_config=int_config, fp_config=fp_config, special_config=special_config,
#     int_unit_count=1, fp_unit_count=1, special_unit_count=1
# )
# fust = functional_unit_config.generate_fust_dict()

# # Step 2: Create Execute Stage
# ex_stage = ExecuteStage.create_pipeline_stage(functional_unit_config=functional_unit_config, fust=fust)

# # Step 3: Create buffer sizes and priorities for Writeback Buffer Config
# wb_buffer_config = WritebackBufferConfig.get_default_config()
# reg_file_config = RegisterFileConfig.get_default_config()

# # Make sure ExecuteStage is created first before WritebackStage since it needs the ahead_latches from ExecuteStage
# wb_stage = WritebackStage.create_pipeline_stage(wb_buffer_config=wb_buffer_config, rf_config=reg_file_config, ex_stage_ahead_latches=ex_stage.ahead_latches)

# if __name__ == "__main__":
#     print("Execute Stage and Writeback Stage created successfully with the specified configurations.")