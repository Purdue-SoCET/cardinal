# this is a class that builds the sm flow and framework setup.
from __future__ import annotations
from builtins import float

import argparse
import io
import math
import sys
from pathlib import Path
from typing import List, Optional

from bitstring import Bits

# ── path setup ────────────────────────────────────────────────────────────────
FILE_ROOT     = Path(__file__).resolve().parent
GPU_SIM_ROOT  = Path(__file__).resolve().parents[3]
sys.path.append(str(GPU_SIM_ROOT))

# ── simulator imports ──────────────────────────────────────────────────────────
from gpu.common.custom_enums_multi import (
    Instr_Type, R_Op, I_Op, F_Op, S_Op, B_Op, U_Op, J_Op, P_Op, H_Op, C_Op, Op
)

from simulator.latch_forward_stage import (
    LatchIF, ForwardingIF, Instruction, DecodeType
)
from simulator.execute.stage import ExecuteStage, FunctionalUnitConfig
from simulator.writeback.stage import WritebackStage, WritebackBufferConfig, RegisterFileConfig, PredicateRegisterFileConfig
from simulator.issue.regfile import RegisterFile
from simulator.issue.stage import IssueStage
from simulator.csr_table import CsrTable
from simulator.kernel_base_pointers import KernelBasePointers
from simulator.scheduler.scheduler import SchedulerStage
from simulator.mem.icache_stage import ICacheStage
from simulator.mem.mem_controller import MemController
from simulator.mem.Memory import Mem
from simulator.decode.decode_class import DecodeStage
from simulator.decode.predicate_reg_file import PredicateRegFile

@dataclass 
class SMConfig:
    sm_no: int #number identifier for the sm 
    test_file: str # this is the binary that will be loaded into memory, and turned into a dictionary
    test_file_type: str # can be hex or binary
    num_warps: int
    num_preds: int
    threads_per_warp: int

    # memory and memory controller values 
    mem_start_pc: 
    mem_lat: int # the number of fixed cycles of memory latency
    mem_mod: dict # some structure here of how to modify the memory at specific 'addresses' pot init
            # this can be possible bc mem is initialized to be be a dicitonayr anyway so  we can send
            # an overwriting dictionary of sorts
    memc_policy: str

    # setup requirements
    kern_init: dict 

    icache_config: dict # icache

    # we should make the structures below as a part of the SM class.
    # define hardwarre structures, initialize port paramters and inputs!

    # csr_table: # scheduler, decode
    # kbp: # decode 
    # prf: # decode 
    # fust: # decode , issue, execute
    # reg_file: #issue, writeback

    fu_config: #execute
    wb_config: # writeback
    rf_config: # writeback
    prf_rf_config: # writeback
    fsu_names: # writeback

    stage_order: List # probably not needed

class SM(Stage):
    def __init__(self, 
        SMConfig: SMConfig
    ):
        super().__init__(name="SM Stage")
        self.SMConfig = SMConfig
        self._setup_pipeline()
        self._initialize_inputs()
    
    #TEST USE: when you want to manually prepopulate the reg file before the program flow 
    def __init_regfile():
        "This function is to manually prepopulate the reg file before the program flow."
    
    def __init_memory(self):
        "This function is to manually modify the memory before the program flow."
    
    def _setup_pipeline(self):
        "This function is to setup the pipline and initialize it"

        # Latch IFs
        self.tbs_ws_if              = LatchIF("TBS-WS")
        self.sched_icache_if        = LatchIF("Sched-ICache")
        self.icache_mem_req_if      = LatchIF("ICache-Mem")
        self.dcache_mem_req_if      = LatchIF("Dcache-Mem")
        self.lsu_dcache_if          = LatchIF("LDST-DCache")
        self.mem_icache_resp_if     = LatchIF("Mem-ICache")
        self.mem_dcache_resp_if     = LatchIF("Mem-DCache")
        self.icache_decode_if       = LatchIF("ICache-Decode")
        self.decode_issue_if        = LatchIF("Decode-Issue")
        self.issue_execute_if    = LatchIF("IS-EX")
        self.execute_writback_if = LatchIF("EX-WB")
        
        # Forwarding IFs
        self.icache_scheduler_fwif      = ForwardingIF(name="icache_forward_if")
        self.decode_scheduler_fwif      = ForwardingIF(name="decode_forward_if")
        self.issue_scheduler_fwif       = ForwardingIF(name="issue_forward_if")
        self.branch_scheduler_fwif      = ForwardingIF(name="branch_forward_if")
        self.writeback_scheduler_fwif   = ForwardingIF(name="Writeback_forward_if")
        self.decode_issue_fwif          = ForwardingIF(name="Decode_issue_fwif")
        self.scheduler_ldst_fwif        = ForwardingIF(name="scheduler_ldst_fwif")
        self.ldst_scheduler_fwif        = ForwardingIF(name="ldst_scheduler_fwif")
        self.branch_scheduler_fwif      = ForwardingIF(name="branch_scheduler_fwif")
        self.dcache_lsu_fwif            = ForwardingIF(name="dcache_lsu_fwif")

        self.mem = Mem(start_pc=self.SMConfig.mem_start_pc, 
                  input_file=self.SMConfig.test_file,
                  fmt=self.SMConfig.test_file_type)
        
        self.memc = MemController(
            name="Memory Controller",
            ic_req_latch=self.icache_mem_req_if,
            dc_req_latch=self.dcache_mem_req_if,
            ic_serve_latch=self.mem_icache_resp_if,
            dc_serve_latch=self.mem_dcache_resp_if,
            mem_backend=self.mem,
            policy=self.SMConfig.memc_policy
        )

        if self.SMConfig.fu_config is None:
            self.fu_config = FunctionalUnitConfig.get_default_config()
        else:
            self.fu_config = self.SMConfig.fu_config
        
        self.fust = self.fu_config.generate_fust_dict()

        self.csr_table = CsrTable()

        self.scheduler = SchedulerStage(
            name="Scheduler",
            behind_latch=self.tbs_ws_if,
            ahead_latch=self.sched_icache_if,
            forward_ifs_read={
                "ICache_Scheduler":    self.icache_scheduler_fwif,
                "Decode_Scheduler":    self.decode_scheduler_fwif,
                "Issue_Scheduler":     self.issue_scheduler_fwif,
                "Branch_Scheduler":    self.branch_scheduler_fwif,
                "Writeback_Scheduler": self.writeback_scheduler_fwif,
                "LDST_Scheduler":      self.ldst_scheduler_fwif
            },
            # forward_ifs_write=None,
            forward_ifs_write={"Scheduler_LDST": self.scheduler_ldst_fwif},
            csrtable = self.SMConfig.csr_table,
            warp_count=self.SMConfig.num_warps,
        )
        
        self.icache = ICacheStage(
            name="ICache",
            behind_latch=self.sched_icache_if,
            ahead_latch=self.icache_decode_if,
            mem_req_if=self.icache_mem_req_if,
            mem_resp_if=self.mem_icache_resp_if,
            cache_config=self.SMConfig.icache_config # a dictionary
            forward_ifs_write={"ICache_Scheduler": self.icache_scheduler_fwif}
        )
    # DCache
        self.dcache = LockupFreeCacheStage(
            name = "dCache",
            behind_latch = self.lsu_dcache_if,    # Change this to dummy
            forward_ifs_write = {"DCache_LSU_Resp": self.dcache_lsu_fwif},   # Change this to dummy
            mem_req_if = self.dcache_mem_req_if,
            mem_resp_if = self.mem_dcache_resp_if
        )

        self.kernel_base_ptrs = KernelBasePointers(max_kernels_per_SM=self.SMConfig.kern_per_SM)
        self.kernel_base_ptrs.write(0, Bits(uint=self.SMConfig.kern_init["Kern_ID"], length=32))

        if self.SMConfig.prf_rf_config is None:
            self.prf = PredicateRegFile(
                num_preds_per_warp=self.SMConfig.num_preds,
                num_warps=self.SMConfig.num_warps
            )
            self.prf_config = PredicateRegisterFileConfig.get_config_from_pred_reg_file(pred_reg_file=self.prf)
        else:
            self.prf_config = self.SMConfig.prf_rf_config
            
        self.decode_stage = DecodeStage(
            name="Decode Stage",
            behind_latch=self.icache_decode_if,
            ahead_latch=self.decode_issue_if,
            prf=self.prf_config,
            fust=self.fust,
            csr_table=self.csr_table,
            kernel_base_ptrs=self.kernel_base_ptrs,
            forward_ifs_read={"ICache_Decode_Ihit": self.icache_scheduler_fwif},
            forward_ifs_write={"Decode_Scheduler_Pckt": self.decode_scheduler_fwif},
        )
        self.execute = ExecuteStage.create_pipeline_stage(
            functional_unit_config=self.fu_config,
            fust=self.fust
        )

        self.execute.behind_latch = self.issue_execute_if
        self.execute.functional_units["MemBranchJumpUnit_0"].subunits["Jump_0"].schedule_if = (
            self.branch_scheduler_fwif
        )

        self.ldst = self.execute.functional_units['MemBranchJumpUnit_0'].subunits['Ldst_Fu_0']
        self.ldst.connect_interfaces(dcache_if = self.lsu_dcache_if, sched_ldst_if = self.scheduler_ldst_fwif, ldst_sched_if = self.ldst_scheduler_fwif)
        
        if self.SMConfig.wb_config is None:
            self.wb_config = WritebackBufferConfig.get_default_config()
        else:
            self.wb_config = self.SMConfig.wb_config
        
        self.wb_config.validate_config(fsu_names=list(self.fust.keys()))

        if self.SMConfig.rf_config is None:
            self.register_file = RegisterFile()
            self.rf_config = RegisterFileConfig.get_config_from_reg_file(reg_file=self.register_file)
        else:
            self.rf_config = self.SMConfig.rf_config
        
        self.wb_stage = WritebackStage.create_pipeline_stage(
            wb_config=self.wb_buffer_config,
            rf_config=self.rf_config,
            pred_rf_config=self.prf_config,
            ex_stage_ahead_latches=self.execute.ahead_latches,
            reg_file=self.rf_config,
            pred_reg_file=self.prf_config,
            fsu_names=list(self.fust.keys())
        )

        self.issue = IssueStage(
            fust_latency_cycles=1,
            regfile=self.register_file,
            fust=self.fust,
            name="IssueStage",
            behind_latch=self.decode_issue_if,
            ahead_latch=self.issue_execute_if,
            forward_ifs_read=None,
            forward_ifs_write={
                "issue_scheduler_fwif": self.issue_scheduler_fwif,
                "decode_issue_fwif":    self.decode_issue_fwif,
            }
        )


    def _initialize_inputs(self):
        self.tbs_ws_if.push([0, 1024, START_PC])        # tbs_ws_if.push([0, 1024, START_PC])
