import sys, os

here = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(here, "..", ".."))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

from collections import deque
from dataclasses import dataclass, field
from typing import List, Any, Optional, Dict
from enum import Enum
from base_class import DecodeType, Instruction, WarpState, WarpGroup, ForwardingIF, LatchIF, Stage

class SchedulerStage(Stage):
    def __init__(self, *args, start_pc, warp_count: int = 32, warp_size: int = 32, **kwargs):
        super().__init__(*args, **kwargs)

        # static shit
        self.warp_count: int = warp_count
        self.num_groups: int = (warp_count + 1) // 2
        self.warp_size: int = warp_size
        self.at_barrier: int = 0

        # warp table
        self.warp_table: List[WarpGroup] = [WarpGroup(pc=start_pc, group_id=id) for id in range(self.num_groups)]

        # scheduler bookkeeping
        self.rr_index: int = 0
        # self.max_issues_per_cycle: int = 1
        # self.ready_queue = deque(range(warp_count))

        # debug
        self.issued_warp_last_cycle: Optional[int] = None

        # could add perf counters
    
    # figuring out which warps can/cant issue
    def collision(self):
        # pop from decode, issue, writeback
        decode_ctrl = self.forward_ifs_read["Decode_Scheduler"].pop()
        issue_ctrl = self.forward_ifs_read["Issue_Scheduler"].pop()
        branch_ctrl = self.forward_ifs_read["Branch_Scheduler"].pop()
        writeback_ctrl = self.forward_ifs_read["Writeback_Scheduler"].pop()

        # if im getting my odd warp EOP out of my decode
        if decode_ctrl["type"] == DecodeType.EOP and decode_ctrl["warp_id"] % 2:
            self.warp_table[decode_ctrl["warp_id"] // 2].state = WarpState.STALL
            self.warp_table[decode_ctrl["warp_id"] // 2].pc = decode_ctrl["pc"]
            self.warp_table[decode_ctrl["warp_id"] // 2].finished_packet = True
        
        # if im getting my odd warp barrier out of my decode
        elif decode_ctrl["type"] == DecodeType.Barrier and decode_ctrl["warp_id"] % 2:
            self.warp_table[decode_ctrl["warp_id"] // 2].state = WarpState.BARRIER
            self.warp_table[decode_ctrl["warp_id"] // 2].pc = decode_ctrl["pc"]
            self.at_barrier += 1

        # if im getting my odd warp halt out of my decode
        elif decode_ctrl["type"] == DecodeType.halt and decode_ctrl["warp_id"] % 2:
            self.warp_table[decode_ctrl["warp_id"] // 2].state = WarpState.HALT

        # # clear barrier MIGHT NOT NEED BARRIER ANYMORE
        # if self.at_barrier == self.num_groups:
        #     self.at_barrier = 0
        #     self.rr_index = 0
        #     for warp_group in self.warp_table:
        #         warp_group.state = WarpState.READY
        #         return

        # change pc for branch
        if branch_ctrl is not None:
            self.warp_table[branch_ctrl["warp_group"]].pc = branch_ctrl["dest"]
        
        # check all my things in the issue
        for ibuffer in range(len(issue_ctrl)):
            if self.warp_table[ibuffer].state != WarpState.BARRIER and self.warp_table[ibuffer].state != WarpState.HALT:
                # i buffer full, stop issuing
                if issue_ctrl[ibuffer] == 1:
                    self.warp_table[ibuffer].state = WarpState.STALL
                # i buffer opens up but you can only issue to it if you haven't finished scheduling ur current packet
                else:
                    if not self.warp_table[ibuffer].finished_packet:
                        self.warp_table[ibuffer].state = WarpState.READY

        # decrement my in flight counter and go back to ready
        if writeback_ctrl is not None:
            self.warp_table[writeback_ctrl["warp_group"]].in_flight -= 1
            if self.warp_table[writeback_ctrl["warp_group"]].in_flight == 0 and self.warp_table[writeback_ctrl["warp_group"]].state != WarpState.BARRIER and self.warp_table[writeback_ctrl["warp_group"]].state != WarpState.HALT:
                self.warp_table[writeback_ctrl["warp_group"]].state = WarpState.READY
                self.warp_table[writeback_ctrl["warp_group"]].finished_packet = False

    # PURE ROUND ROBIN RIGHT NOW, NEED TO FIND THE RR_INDEX
    def compute(self):
        # waiting for ihit
        for fwd_if in self.forward_ifs_read.values():
            if fwd_if.wait:
                print(f"[{self.name}] Stalled due to wait from next stage")
                # same issue here with nontype and ints
                return 10000, 10000, 10000

        # detecting stalls
        self.collision()

        # round robin scheduling loop
        for tries in range(self.num_groups):
            warp_group = self.warp_table[self.rr_index]

            # we can issue this warp group DONT 
            if warp_group.state == WarpState.READY:
                # increment in flight counter
                warp_group.in_flight += 1

                # if the last issue for the group was odd DONT INCREASE RR_INDEX
                if not warp_group.last_issue_even:
                    warp_group.last_issue_even = True
                    return warp_group.group_id, warp_group.group_id * 2, warp_group.pc # EVEN WARP INSTRUCTION
                
                # if the last issue for the group was even MOVE ON WITH RR_INDEX
                if warp_group.last_issue_even:
                    self.rr_index = (self.rr_index + 1) % self.num_groups
                    current_pc = warp_group.pc
                    warp_group.pc += 4
                    warp_group.last_issue_even = False
                    return warp_group.group_id, (warp_group.group_id * 2) + 1, current_pc # ODD WARP INSTRUCTION
            
            # we cant issue this warp group
            else:
                self.rr_index = (self.rr_index + 1) % self.num_groups
        
        # every warp is unable to issue (syntax with type of thing returned --> needs to go back to none)
        return 10000, 10000, 10000