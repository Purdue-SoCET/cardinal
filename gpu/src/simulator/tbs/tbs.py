from collections import deque
from dataclasses import dataclass, field
from typing import List, Any, Optional, Dict
from enum import Enum
from pathlib import Path
from bitstring import Bits
from simulator.mem_types import DecodeType
from simulator.instruction import Instruction
from simulator.warp import WarpState, WarpGroup
from simulator.interfaces import ForwardingIF, LatchIF
from simulator.stage import Stage
from simulator.scheduler.csrtable import CsrTable
import math

@dataclass
class ThreadBlockRecord:
    bidx: int
    bdim: int
    spc: int
    apc: int
    assigned_sm: Optional[int] = None 
    
    def assign(self, smidx: int = 0):
        self.assigned_sm = smidx
        
@dataclass
class SMRecord:
    def __init__(self, max_threads: int, threads_per_warp: int) -> None:
        self.threads_per_warp: int = threads_per_warp
        self.avail_warps: int = self.warps_from_threads(max_threads)
        # self.working: bool = False
    
    def warps_from_threads(self, nthreads: int):
        return math.ceil(nthreads / self.threads_per_warp)
    
    def can_give_threads(self, nthreads: int):
        return self.avail_warps >= self.warps_from_threads(nthreads) # and not self.working
    
    def give_threads(self, nthreads: int):
        assert self.can_give_threads(nthreads)
        self.avail_warps -= self.warps_from_threads(nthreads)
        self.working = True
        
    def free_threads(self, nthreads: int):
        self.avail_warps += self.warps_from_threads(nthreads)

class ThreadBlockScheduler(Stage):
    """
    TBS is only configured for single SM operation.
    - To Change: Need to touch sending/recieving using forward latch
                    Probably shouldn't be a Stage
    """
    
    
    def __init__(self, *args, threads_per_sm: int = 1024, min_thread_division: int = 32, **kwargs):
        super().__init__(*args, **kwargs)
        assert self.behind_latch is None

        # SM info
        self.threads_per_sm = threads_per_sm
        self.min_thread_division = min_thread_division
        
        # block list
        self.block_list: list[ThreadBlockRecord] = []
        self.blocks_not_sent: list[int] = []
        self.blocks_done: list[int] = []
        
        # SM list, tracks availability
        self.SMs: list[SMRecord] = []
    
    def reset(self) -> None:
        self.block_list = []
        self.blocks_not_sent = []
        self.blocks_done = []

    def add_SM(self) -> None:
        availability = self.threads_per_sm // self.min_thread_division
        self.SMs.append(SMRecord(self.threads_per_sm, self.min_thread_division))
        
    def append_block(self, bdim: int, spc: int, apc: int = 0) -> None:
        bidx = len(self.block_list)
        self.block_list.append(ThreadBlockRecord(bidx, bdim, spc, apc))
        self.blocks_not_sent.append(bidx)
    
    def can_send_blk_to_sm(self, bidx, smidx: int = 0):
        return self.SMs[smidx].avail_warps >= math.ceil(self.block_list[bidx].bdim / self.min_thread_division)
    
    def send_blk_to_sm(self, bidx, smidx: int = 0):
        # Occupy
        self.SMs[smidx].give_threads(self.block_list[bidx].bdim)
        self.blocks_not_sent.remove(bidx)
        self.block_list[bidx].assign(smidx)
        self.send_output(self.block_list[bidx])

    def send_output(self, blk):
        self.ahead_latch.push((blk.bidx, blk.bdim, blk.spc))
    
    def finish_blk(self, bidx, smidx: int = 0):
        # De-occupy
        self.SMs[smidx].free_threads(self.block_list[bidx].bdim)
        self.blocks_done.append(bidx)
            
    def compute(self):
        for bidx in self.blocks_not_sent:
            for smidx, _ in enumerate(self.SMs):
                if self.can_send_blk_to_sm(bidx, smidx):
                    self.send_blk_to_sm(bidx, smidx)
                    ## NOTE: Launch bandwidth not restricted.
                    
        ## TODO: ADD RECIEVE. ASK WARPSCHEDULER. OTHERWISE CAN ONLY SEND 1 WARP.
        if self.forward_ifs_read["Scheduler_TBS"].payload:
            for bidx in self.forward_ifs_read["Scheduler_TBS"].pop():
                self.finish_blk(bidx)
        
            # self.SMs[0].working = False
