# this is a class that builds the sm flow and framework setup.
from __future__ import annotations
from contextlib import redirect_stdout
from dataclasses import dataclass
import math
from pathlib import Path
from typing import List, Optional
from bitstring import Bits

# ── simulator imports ──────────────────────────────────────────────────────────
from simulator.interfaces import LatchIF, ForwardingIF
from simulator.instruction import Instruction
from simulator.mem_types import DecodeType
from simulator.execute.stage import ExecuteStage, FunctionalUnitConfig
from simulator.execute.functional_unit import MemBranchJumpUnitConfig, IntUnitConfig, FpUnitConfig, SpecialUnitConfig
from simulator.writeback.stage import WritebackStage, WritebackBufferConfig, RegisterFileConfig, PredicateRegisterFileConfig
from simulator.issue.regfile import RegisterFile
from simulator.issue.stage import IssueStage
from simulator.scheduler.csrtable import CsrTable
from simulator.kernel_base_pointers import KernelBasePointers
from simulator.scheduler.scheduler import SchedulerStage
from simulator.mem.icache_stage import ICacheStage
from simulator.mem.dcache import LockupFreeCacheStage
from simulator.execute.functional_sub_unit import Ldst_Fu
from simulator.mem.mem_controller import MemController
from simulator.mem.memory import Mem
from simulator.decode.decode_class import DecodeStage
from simulator.decode.predicate_reg_file import PredicateRegFile
from simulator.utils.performance_counter import PerfConfig, Telemeter
from simulator.tbs.tbs import ThreadBlockScheduler
from config import Settings, get_settings

class SM:
    def __init__(self, 
        test_file: Path,
        test_file_type: str = "bin",
        config: Optional[Settings] = None,
        config_path: Optional[Path] = None
    ):
        """Initialize Streaming Multiprocessor.
        
        Args:
            test_file: Path to binary/hex test file
            test_file_type: File format ("bin" or "hex")
            config: Pre-loaded Settings (optional)
            config_path: Path to config file (optional, uses default if not provided)
        """
        # Load configuration
        if config is None:
            if config_path:
                self.config = get_settings(config_path)
            else:
                # Use the default config from gpu/gpu/config.toml
                self.config = get_settings()
        else:
            self.config = config
        
        self.name = f"SM_{self.config.sm.sm_no}"
        self.test_file = test_file
        self.test_file_type = test_file_type
        
        # Initialize simulation state
        self.cycle = 0
        self.finished = False
        
        # Initialize Telemeter based on configuration
        self.telemeter = self._create_telemeter()
        
        # Build the pipeline
        self.pipeline = self._build_pipeline()
    
    def _create_telemeter(self) -> Telemeter:
        """Create and configure the Telemeter based on PerfCounterConfig."""
        perf_cfg = self.config.perf_counter
        
        if not perf_cfg.enabled:
            # Return disabled telemeter
            return Telemeter(PerfConfig.disabled())
        
        # Create output directory if it doesn't exist
        output_dir = Path(perf_cfg.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build enabled units set
        enabled_units = set(perf_cfg.enabled_units) if perf_cfg.enabled_units else set()
        
        if perf_cfg.summary_only:
            # Summary only mode
            perf_config = PerfConfig.summary_only()
        elif perf_cfg.trace_enabled:
            # Full trace mode
            perf_config = PerfConfig.full_trace(
                start=perf_cfg.trace_start_cycle,
                end=perf_cfg.trace_end_cycle,
                enabled_units=enabled_units,
                buffer_limit=perf_cfg.buffer_limit,
            )
        else:
            # Fallback to summary only
            perf_config = PerfConfig.summary_only()
        
        return Telemeter(perf_config, output_dir=str(output_dir), output_prefix=perf_cfg.output_prefix)
    
    def _build_functional_unit_config(self) -> FunctionalUnitConfig:
        """Build FunctionalUnitConfig from Settings.functional_units configuration.
        
        Converts the nested functional unit configuration from the Settings object
        into the structured FunctionalUnitConfig format used by the functional units.
        
        Returns
        -------
        FunctionalUnitConfig
            Structured configuration with all sub-configs
        """
        fu_cfg = self.config.functional_units
        
        # Create individual unit configs from nested settings
        int_config = IntUnitConfig(
            alu_count=fu_cfg.int_unit.alu_count,
            mul_count=fu_cfg.int_unit.mul_count,
            div_count=fu_cfg.int_unit.div_count,
            alu_latency=fu_cfg.int_unit.alu_latency,
            mul_latency=fu_cfg.int_unit.mul_latency,
            div_latency=fu_cfg.int_unit.div_latency,
        )
        
        fp_config = FpUnitConfig(
            alu_count=fu_cfg.fp_unit.alu_count,
            mul_count=fu_cfg.fp_unit.mul_count,
            div_count=fu_cfg.fp_unit.div_count,
            sqrt_count=fu_cfg.fp_unit.sqrt_count,
            alu_latency=fu_cfg.fp_unit.alu_latency,
            mul_latency=fu_cfg.fp_unit.mul_latency,
            div_latency=fu_cfg.fp_unit.div_latency,
            sqrt_latency=fu_cfg.fp_unit.sqrt_latency,
        )
        
        special_config = SpecialUnitConfig(
            trig_count=fu_cfg.special_unit.trig_count,
            inv_sqrt_count=fu_cfg.special_unit.inv_sqrt_count,
            conv_count=fu_cfg.special_unit.conv_count,
            trig_latency=fu_cfg.special_unit.trig_latency,
            inv_sqrt_latency=fu_cfg.special_unit.inv_sqrt_latency,
            conv_latency=fu_cfg.special_unit.conv_latency,
        )
        
        membranchjump_config = MemBranchJumpUnitConfig(
            ldst_count=fu_cfg.membranchjump_unit.ldst_count,
            branch_count=fu_cfg.membranchjump_unit.branch_count,
            jump_count=fu_cfg.membranchjump_unit.jump_count,
            ldst_buffer_size=fu_cfg.membranchjump_unit.ldst_buffer_size,
            ldst_queue_size=fu_cfg.membranchjump_unit.ldst_queue_size,
        )
        
        # Create and return the FunctionalUnitConfig
        return FunctionalUnitConfig(
            int_unit_count=fu_cfg.int_unit_count,
            fp_unit_count=fu_cfg.fp_unit_count,
            special_unit_count=fu_cfg.special_unit_count,
            membranchjump_unit_count=fu_cfg.membranchjump_unit_count,
            int_config=int_config,
            fp_config=fp_config,
            special_config=special_config,
            membranchjump_config=membranchjump_config,
        )
    
    def _build_writeback_configs(self):
        """Build writeback configs from Settings.
        
        Returns
        -------
        tuple of (WritebackBufferConfig, RegisterFileConfig, PredicateRegisterFileConfig)
            Writeback configuration objects
        """
        from simulator.writeback.config import (
            WritebackBufferConfig as WritebackBufferConfigImpl,
            WritebackBufferCount,
            WritebackBufferSize,
            WritebackBufferStructure,
            WritebackBufferPolicy,
            RegisterFileConfig as RegisterFileConfigImpl,
            PredicateRegisterFileConfig as PredicateRegisterFileConfigImpl,
        )
        
        wb_cfg = self.config.writeback.buffer_config
        rf_cfg = self.config.register_file
        pred_rf_cfg = self.config.predicate_register_file
        
        # Map pydantic enum values to implementation enum values
        count_scheme_map = {
            "buffer_per_fsu": WritebackBufferCount.BUFFER_PER_FSU,
            "buffer_per_bank": WritebackBufferCount.BUFFER_PER_BANK,
        }
        size_scheme_map = {
            "fixed": WritebackBufferSize.FIXED,
            "variable": WritebackBufferSize.VARIABLE,
        }
        structure_map = {
            "stack": WritebackBufferStructure.STACK,
            "queue": WritebackBufferStructure.QUEUE,
            "circular": WritebackBufferStructure.CIRCULAR,
        }
        policy_map = {
            "age_priority": WritebackBufferPolicy.AGE_PRIORITY,
            "capacity_priority": WritebackBufferPolicy.CAPACITY_PRIORITY,
            "fsu_priority": WritebackBufferPolicy.FSU_PRIORITY,
        }
        
        # Convert pydantic enums (which are strings) to implementation enums
        count_scheme = count_scheme_map[wb_cfg.count_scheme.value]
        size_scheme = size_scheme_map[wb_cfg.size_scheme.value]
        structure = structure_map[wb_cfg.structure.value]
        primary_policy = policy_map[wb_cfg.primary_policy.value]
        secondary_policy = policy_map[wb_cfg.secondary_policy.value]
        
        # Determine size configuration based on scheme
        if size_scheme == WritebackBufferSize.VARIABLE and wb_cfg.variable_sizes:
            size_config = wb_cfg.variable_sizes
        else:
            size_config = wb_cfg.size
        
        # Create WritebackBufferConfig
        wb_buffer_config = WritebackBufferConfigImpl(
            count_scheme=count_scheme,
            size_scheme=size_scheme,
            structure=structure,
            primary_policy=primary_policy,
            secondary_policy=secondary_policy,
            size=size_config,
            fsu_priority=wb_cfg.fsu_priorities,
        )
        
        # Create RegisterFileConfig
        reg_file_config = RegisterFileConfigImpl(
            num_banks=rf_cfg.num_banks
        )
        
        # Create PredicateRegisterFileConfig
        pred_reg_file_config = PredicateRegisterFileConfigImpl(
            num_banks=pred_rf_cfg.num_banks
        )
        
        return wb_buffer_config, reg_file_config, pred_reg_file_config
    
    def _build_pipeline(self) -> dict:
        """Instantiate all pipeline stages and return them as a dict."""
        enable_tbs = self.config.sm.enable_tbs
        
        # Latches
        tbs_ws_if               = LatchIF("TBS-WS Latch")
        sched_icache_if         = LatchIF("Sched-ICache Latch")
        icache_mem_req_if       = LatchIF("ICache-Mem Latch")
        mem_icache_resp_if      = LatchIF("Mem-ICache Latch")
        icache_decode_if        = LatchIF("ICache-Decode Latch")
        decode_issue_if         = LatchIF("Decode-Issue Latch")
        is_ex_latch             = LatchIF("IS-EX Latch")
        # D-Cache latches (LSU ↔ DCache ↔ MemController)
        lsu_dcache_latch        = LatchIF("LSU-DCache Latch")
        dcache_lsu_forward      = ForwardingIF(name="dcache_lsu_forward")
        lsu_dcache_latch.forward_if = dcache_lsu_forward   # binds response IF onto request latch
        dcache_mem_latch        = LatchIF("DCache-Mem Latch")
        mem_dcache_latch        = LatchIF("Mem-DCache Latch")

        # Forwarding IFs - only create scheduler_tbs_fwif if TBS is enabled
        forwarding_ifs = {}
        if enable_tbs:
            scheduler_tbs_fwif = ForwardingIF(name="scheduler_tbs_if")
            forwarding_ifs["scheduler_tbs_fwif"] = scheduler_tbs_fwif
        
        icache_scheduler_fwif   = ForwardingIF(name="icache_forward_if")
        decode_scheduler_fwif   = ForwardingIF(name="decode_forward_if")
        issue_scheduler_fwif    = ForwardingIF(name="issue_forward_if")
        branch_scheduler_fwif   = ForwardingIF(name="branch_forward_if")
        writeback_scheduler_fwif = ForwardingIF(name="Writeback_forward_if")
        decode_issue_fwif       = ForwardingIF(name="Decode_issue_fwif")
        scheduler_ldst_fwif     = ForwardingIF(name="scheduler_ldst_fwif")
        ldst_scheduler_fwif     = ForwardingIF(name="ldst_scheduler_fwif")
        
        # Get config values
        start_pc = self.config.memory.start_pc
        warp_count = self.config.sm.num_warps
        mem_latency = self.config.memory.latency
        mem_policy = self.config.memory.policy
        tb_size = self.config.sm.tb_size
        
        # Use the single num_preds parameter for both modes
        num_preds = self.config.sm.num_preds
        
        # Initialize memory
        mem = Mem(start_pc=start_pc, input_file=str(self.test_file), fmt=self.test_file_type)
                
        # Memory controller
        memc = MemController(
            name="Mem_Controller",
            ic_req_latch=icache_mem_req_if,
            dc_req_latch=dcache_mem_latch,
            ic_serve_latch=mem_icache_resp_if,
            dc_serve_latch=mem_dcache_latch,
            mem_backend=mem,
            latency=mem_latency,
            policy="rr",
        )

        # D-Cache stage
        dcache_stage = LockupFreeCacheStage(
            name="dCache",
            behind_latch=lsu_dcache_latch,
            forward_ifs_write={"DCache_LSU_Resp": dcache_lsu_forward},
            mem_req_if=dcache_mem_latch,
            mem_resp_if=mem_dcache_latch,
            cache_config=self.config.to_dcache_dict(),
        )

        fu_config = self._build_functional_unit_config()
        fu_config.membranchjump_config.block_size_words = self.config.dcache.block_size_words
        fu_config.membranchjump_config.word_size_bytes = self.config.dcache.word_size_bytes

        fust      = fu_config.generate_fust_dict()

        csr_table = CsrTable()
        
        # Create TBS only if enabled
        tbs = None
        if enable_tbs:
            scheduler_tbs_fwif = forwarding_ifs["scheduler_tbs_fwif"]
            tbs = ThreadBlockScheduler(
                name="Thread_Block_Scheduler",
                behind_latch=None,
                ahead_latch=tbs_ws_if,
                forward_ifs_read={
                    "Scheduler_TBS": scheduler_tbs_fwif
                },
                forward_ifs_write=None,
                input_file=self.test_file
            )

            tbs.add_SM() 
            kernel_pointer_addr = tbs.load()
        else:
            # No-TBS mode: manually push thread block info to the scheduler
            tbs_ws_if.push([0, tb_size, start_pc])  # [kernel_id, tb_size, start_pc]
            kernel_pointer_addr = self.config.sm.kernel_pointer_addr

        # Build scheduler forward_ifs_write based on TBS mode
        scheduler_fwif_write = {"Scheduler_LDST": scheduler_ldst_fwif}
        if enable_tbs:
            scheduler_fwif_write["Scheduler_TBS"] = forwarding_ifs["scheduler_tbs_fwif"]

        scheduler_stage = SchedulerStage(
            name="Scheduler_Stage",
            behind_latch=tbs_ws_if,
            ahead_latch=sched_icache_if,
            forward_ifs_read={
                "ICache_Scheduler":    icache_scheduler_fwif,
                "Decode_Scheduler":    decode_scheduler_fwif,
                "Issue_Scheduler":     issue_scheduler_fwif,
                "Branch_Scheduler":    branch_scheduler_fwif,
                "Writeback_Scheduler": writeback_scheduler_fwif,
                "LDST_Scheduler":      ldst_scheduler_fwif
            },
            forward_ifs_write=scheduler_fwif_write,
            csrtable = csr_table,
            warp_count=warp_count,
        )

        icache_stage = ICacheStage(
            name="ICache_Stage",
            behind_latch=sched_icache_if,
            ahead_latch=icache_decode_if,
            mem_req_if=icache_mem_req_if,
            mem_resp_if=mem_icache_resp_if,
            cache_config=self.config.to_icache_dict(),
            forward_ifs_write={"ICache_Scheduler": icache_scheduler_fwif},
        )

        prf = PredicateRegFile(
            num_preds_per_warp=num_preds, 
            num_warps=warp_count
        )
        for warp in range(warp_count):
            for pred in range(num_preds):
                prf.reg_file[warp][pred] = [True] * self.config.sm.threads_per_warp

        kernel_base_ptrs = KernelBasePointers(max_kernels_per_SM=1)
        kernel_base_ptrs.write(0, Bits(uint=kernel_pointer_addr, length=32))

        decode_stage = DecodeStage(
            name="Decode Stage",
            behind_latch=icache_decode_if,
            ahead_latch=decode_issue_if,
            prf=prf,
            fust=fust,
            csr_table=csr_table,
            kernel_base_ptrs=kernel_base_ptrs,
            forward_ifs_read={"ICache_Decode_Ihit": icache_scheduler_fwif},
            forward_ifs_write={"Decode_Scheduler_Pckt": decode_scheduler_fwif},
        )

        pipeline_rf = RegisterFile()
        golden_rf   = RegisterFile()

        ex_stage = ExecuteStage.create_pipeline_stage(
            functional_unit_config=fu_config,
            fust=fust,
            telemeter=self.telemeter
        )
        ex_stage.behind_latch = is_ex_latch
        ex_stage.functional_units["MemBranchJumpUnit_0"].subunits["Jump_0"].schedule_if = (
            branch_scheduler_fwif
        )

        # Wire LSU to D-Cache
        ldst = ex_stage.functional_units["MemBranchJumpUnit_0"].subunits["Ldst_Fu_0"]
        ldst.connect_interfaces(
            dcache_if=lsu_dcache_latch,
            sched_ldst_if=scheduler_ldst_fwif,
            ldst_sched_if=ldst_scheduler_fwif,
        )

        wb_buffer_config, rf_config, pred_reg_file_config = self._build_writeback_configs()
        wb_buffer_config.validate_config(fsu_names=list(fust.keys()))
        
        wb_stage = WritebackStage.create_pipeline_stage(
            wb_config=wb_buffer_config,
            rf_config=rf_config,
            pred_rf_config=pred_reg_file_config,
            ex_stage_ahead_latches=ex_stage.ahead_latches,
            reg_file=pipeline_rf,
            pred_reg_file=prf,
            forward_ifs_write=scheduler_stage.forward_ifs_read,
            fsu_names=list(fust.keys()),
        )

        issue_stage = IssueStage(
            fust_latency_cycles=1,
            regfile=pipeline_rf,
            fust=fust,
            name="IssueStage",
            behind_latch=decode_issue_if,
            ahead_latch=is_ex_latch,
            forward_ifs_read=None,
            forward_ifs_write={
                "issue_scheduler_fwif": issue_scheduler_fwif,
                "decode_issue_fwif":    decode_issue_fwif,
            },
        )

        # Bootstrap forwarding IFs so the scheduler never sees None on cycle 0
        filler_decode  = {"type": DecodeType.MOP, "warp_id": 0, "pc": 0}
        filler_issue   = [0] * scheduler_stage.num_groups
        icache_scheduler_fwif.payload    = None
        decode_scheduler_fwif.push(filler_decode)
        issue_scheduler_fwif.push(filler_issue)
        branch_scheduler_fwif.payload    = None
        writeback_scheduler_fwif.payload = None        

        pipeline_dict = {
            "scheduler":   scheduler_stage,
            "icache":      icache_stage,
            "decode":      decode_stage,
            "issue":       issue_stage,
            "ex":          ex_stage,
            "wb":          wb_stage,
            "memc":        memc,
            "dcache":      dcache_stage,
            "ldst":        ldst,
            "pipeline_rf": pipeline_rf,
            "golden_rf":   golden_rf,
            "csr_table":   csr_table,
            "kbp":         kernel_base_ptrs,
            "fust":        fust,
            "prf":         prf,
            "mem":         mem,
        }
        
        # Only add TBS to pipeline if enabled
        if enable_tbs and tbs is not None:
            pipeline_dict["tbs"] = tbs
        
        return pipeline_dict

    def tick(self):
        if self.finished:
            print(f"Simulation finished in {self.cycle} cycles.")
            return
         
        self.pipeline["wb"].tick()
        self.pipeline["ex"].tick()
        self.pipeline["ex"].compute()
        self.pipeline["dcache"].compute()
        self.pipeline["issue"].compute()
        self.pipeline["decode"].compute()
        self.pipeline["memc"].compute()
        self.pipeline["icache"].compute()
        self.pipeline["scheduler"].compute()
        if "tbs" in self.pipeline:
            self.pipeline["tbs"].compute()
        
        self.cycle += 1
        self.finished = self.pipeline["scheduler"].system_finished
    
    def finalize(self):
        """Finalize simulation and output performance counter data."""
        if self.telemeter:
            try:
                self.telemeter.finalize()
                print(f"Performance counter data written to {self.config.perf_counter.output_dir}/")
            except Exception as e:
                print(f"Error finalizing performance counters: {e}")
                import traceback
                traceback.print_exc()
