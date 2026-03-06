# this is a class that builds the sm flow and framework setup.
from __future__ import annotations
from builtins import float
from dataclasses import dataclass
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
from simulator.mem.dcache import LockupFreeCacheStage
from simulator.mem.ld_st import Ldst_Fu
from simulator.mem.mem_controller import MemController
from simulator.mem.Memory import Mem
from simulator.decode.decode_class import DecodeStage
from simulator.decode.predicate_reg_file import PredicateRegFile

@dataclass 
class SMConfig:
    sm_no: int #number identifier for the sm 
    test_file: Path # this is the binary that will be loaded into memory, and turned into a dictionary
    test_file_type: str # can be hex or binary
    num_warps: int
    num_preds: int
    threads_per_warp: int

    # memory and memory controller values 
    mem_start_pc: int
    mem_lat: int # the number of fixed cycles of memory latency
    mem_mod: dict # some structure here of how to modify the memory at specific 'addresses' pot init
            # this can be possible bc mem is initialized to be be a dicitonayr anyway so  we can send
            # an overwriting dictionary of sorts
    memc_policy: str

    # setup requirements
    kern_init: dict 

    icache_config: dict # icache
    fu_config: dict #execute
    wb_config: dict # writeback
    rf_config: dict # writeback
    prf_rf_config: dict # writeback

    # custom initializations
    custom_regfile_init: dict
    custom_prf_init: dict

    stage_order: List # probably not needed

class SM:
    def __init__(self, 
        SMConfig: SMConfig
    ):
        self.name="SM Stage"
        self.SMConfig = SMConfig
        self.call_order = self._setup_pipeline()
        self._initialize_inputs()
    
    def __init_memory(self):
        "This function is to manually modify the memory before the program flow."
    
    def get_test_values(self, warp_id: int, threads_per_warp: int) -> dict:
        """Initial register values identical to sm-no-mem.py."""
        return {
            # 1:  [0  + i + warp_id for i in range(threads_per_warp)],
            # 2:  [5  + i + warp_id for i in range(threads_per_warp)],
            # 3:  [3  for _ in range(threads_per_warp)],
            # 4:  [2  for _ in range(threads_per_warp)],
            # 5:  [-5 - i + warp_id for i in range(threads_per_warp)],
            # 10: [10.5 + i * 0.5  + warp_id for i in range(threads_per_warp)],
            # 11: [2.5  + i * 0.25 + warp_id for i in range(threads_per_warp)],
            # 12: [1.57 for _ in range(threads_per_warp)],
            # 13: [4.0  for _ in range(threads_per_warp)],
            1: [31 - i for i in range(threads_per_warp)],
            2: [i for i in range(threads_per_warp)],
            8: [100 for i in range(threads_per_warp)],
            9: [100 for i in range(threads_per_warp)],
        }
    
    def _initialize_regfile(self):
        "Initialized the register file"
        warp_ids = list(range(self.SMConfig.num_warps + (1 if self.SMConfig.num_warps % 2 else 0)))
        if (self.SMConfig.custom_prf_init is None):
            # ── initialise register files ─────────────────────────────────────────────
            for warp_id in warp_ids:
                test_vals = self.get_test_values(warp_id, 32)
                for reg_num, values in test_vals.items():
                    if reg_num >= 10:
                        data = [Bits(float=v, length=32) for v in values]
                    else:
                        data = [Bits(int=v,   length=32) for v in values]
                    self.regfile.write_warp_gran(warp_id=warp_id,
                                                dest_operand=Bits(uint=reg_num, length=32),
                                                data=data)
                    
        # populate the reg file as specified in the dictionary, I haven't figured out how we want to do this yet..
    
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
            csrtable = self.csr_table,
            warp_count=self.SMConfig.num_warps,
        )
        
        self.icache = ICacheStage(
            name="ICache",
            behind_latch=self.sched_icache_if,
            ahead_latch=self.icache_decode_if,
            mem_req_if=self.icache_mem_req_if,
            mem_resp_if=self.mem_icache_resp_if,
            cache_config=self.SMConfig.icache_config, # a dictionary
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

        self.kernel_base_ptrs = KernelBasePointers(max_kernels_per_SM=self.SMConfig.kern_init["Kern_per_SM"])
        self.kernel_base_ptrs.write(0, Bits(uint=self.SMConfig.kern_init["Kern_ID"], length=32))

        self.prf = PredicateRegFile(
                num_preds_per_warp=self.SMConfig.num_preds,
                num_warps=self.SMConfig.num_warps
        )
        self.prf_config = PredicateRegisterFileConfig.get_config_from_pred_reg_file(pred_reg_file=self.prf)
            
        self.decode = DecodeStage(
            name="Decode Stage",
            behind_latch=self.icache_decode_if,
            ahead_latch=self.decode_issue_if,
            prf=self.prf,
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

        self.regfile = RegisterFile()
        self.rf_config = RegisterFileConfig.get_config_from_reg_file(reg_file=self.regfile)

        self.writeback = WritebackStage.create_pipeline_stage(
            wb_config=self.wb_config,
            rf_config=self.rf_config,
            pred_rf_config=self.prf_config,
            ex_stage_ahead_latches=self.execute.ahead_latches,
            reg_file=self.regfile,
            pred_reg_file=self.prf,
            forward_ifs_write=self.scheduler.forward_ifs_read,
            fsu_names=list(self.fust.keys())
        )

        self.issue = IssueStage(
            fust_latency_cycles=1,
            regfile=self.regfile,
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
 
        return ([self.writeback.name, self.dcache.name, self.execute.name, self.execute.name, self.issue.name, self.decode.name, self.memc.name, self.icache.name, self.scheduler.name])
        
    def _initialize_inputs(self):
        
        #initialize the regular reg file
        # self._initialize_regfile()

        # initialize all the values in the predicat reg file to:
        for warp in range(32):
            for pred in range(16):  # num_preds_per_warp * 2
                for neg in range(2):  # both positive and negative versions
                    # nothing second is being indexed
                    self.prf.reg_file[warp][pred] = [True] * 32  # all 32 threads active
        
        self.tbs_ws_if.push([0, 1024, Bits(uint=self.SMConfig.mem_start_pc, length=32).int])        # tbs_ws_if.push([0, 1024, START_PC])

            # Bootstrap forwarding IFs so the scheduler never sees None on cycle 0
        filler_decode  = {"type": DecodeType.MOP, "warp_id": 0, "pc": 0}
        filler_issue   = [0] * self.scheduler.num_groups
        self.icache_scheduler_fwif.payload    = None
        self.decode_scheduler_fwif.push(filler_decode)
        self.issue_scheduler_fwif.push(filler_issue)
        self.branch_scheduler_fwif.payload    = None
        self.writeback_scheduler_fwif.payload = None

    
    def compute(self):
        "Compute all pipeline stage ticks."
        self.writeback.tick()
        self.dcache.compute()
        self.execute.tick()
        self.execute.compute()
        self.issue.compute()
        self.decode.compute()
        self.memc.compute()
        self.icache.compute()
        self.scheduler.compute()
