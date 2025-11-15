import sys, os
from collections import deque
from dataclasses import dataclass, field
from typing import List, Any, Optional, Dict
from enum import Enum
from base import DecodeType, Instruction, WarpState, Warp, ForwardingIF, LatchIF, Stage

class SchedulerStage(Stage):
    def __init__(self, *args, start_pc, warp_count: int = 32, warp_size: int = 32, **kwargs):
        super().__init__(*args, **kwargs)

        # static shit
        self.warp_count: int = warp_count
        self.num_groups: int = (warp_count + 1) // 2
        self.warp_size: int = warp_size
        self.at_barrier: int = 0

        # warp table
        self.warp_table: List[Warp] = [Warp(pc=start_pc, group_id=wid // 2) for wid in range(warp_count)]

        # scheduler bookkeeping
        self.rr_index: int = 0
        self.max_issues_per_cycle: int = 1
        self.ready_queue = deque(range(warp_count))

        # debug
        self.issued_warp_last_cycle: Optional[int] = None

        # could add perf counters
    
    # figuring out which warps can/cant issue
    # ALL PSEUDOCODE CURRENTLY I NEED TO KMS BAD LOL
    def collision(self):
        # waiting stuff
        for fwd_if in self.forward_ifs_read.values():
            if fwd_if.wait:
                print(f"[{self.name}] Stalled due to wait from next stage")
                return None
            
        # pop from decode
        decode_ctrl = self.forward_ifs_read["Decode_Scheduler"].pop()
        issue_ctrl = self.forward_ifs_read["Issue_Scheduler"].pop()
        wb_ctrl = self.forward_ifs_read["WB_Scheduler"].pop()
        

        # check end of packet decode
        if decode_ctrl["type"] == DecodeType.EOP:
            if self.warp_table[decode_ctrl["warp"]].state == WarpState.READY:
                self.warp_table[decode_ctrl["warp"]].state = WarpState.SHORTSTALL

        # check from issue and memory
        for warp_group in issue_ctrl:
            # set both warps
            if warp_group is full:
                self.warp_table[warp_group // 2].state = WarpState.LONGSTALL
                self.warp_table[(warp_group // 2) + 1].state = WarpState.LONGSTALL
            # clear both warps by setting to shortstall and then check the in flight counter last to see if i can really issue them (since from LONGSTALL idk if im going back to READY or SHORTSTALL)
            else:
                self.warp_table[warp_group // 2].state = WarpState.SHORTSTALL
                self.warp_table[(warp_group // 2) + 1].state = WarpState.SHORTSTALL

        # decrement counter from writeback from writeback
        self.warp_table[wb_ctrl["warp"]].in_flight = max(self.warp_table[wb_ctrl["warp"]].in_flight - 1, 0)
        if self.warp_table[wb_ctrl["warp"]].state == WarpState.SHORTSTALL and self.warp_table[wb_ctrl["warp"]].in_flight == 0:
            self.warp_table[wb_ctrl["warp"]].state = WarpState.READY

        # BARRIER
        if decode_ctrl["type"] == DecodeType.Barrier:
            self.warp_table[decode_ctrl["warp"]].state == WarpState.BARRIER
            self.at_barrier = self.at_barrier + 1

        # THIS ONLY WORKS RIGHT NOW FOR ONE TB
        if self.at_barrier == self.warp_count:
            for warp in range(self.warp_count):
                self.warp_table[warp].state = WarpState.READY

        return

    # PURE ROUND ROBIN RIGHT NOW, NEED TO FIND THE RR_INDEX
    def compute(self):
        self.collision()

        # round robin scheduling loop
        for tries in range(self.warp_count):
            warp = self.warp_table[self.rr_index]
            self.rr_index = (self.rr_index + 1) % self.warp_count

            # issue that specific warp
            if warp.state == WarpState.READY and not warp.halt:
                warp.in_flight = warp.in_flight + 1 # increment in flight counter by 1
                return # ISSUE INSTRUCTION OBJECT
        
        # every warp is unable to issue
        return None