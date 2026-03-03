from builtins import all, print
from collections import deque
from dataclasses import dataclass, field
from typing import List, Any, Optional, Dict
from enum import Enum
from pathlib import Path
from bitstring import Bits
from simulator.latch_forward_stage import DecodeType, Instruction, WarpState, WarpGroup, ForwardingIF, LatchIF, Stage
from simulator.scheduler.csrtable import CsrTable
import math

# comment/uncomment for printing out debug info
# print = lambda *args, **kwargs: None

class SchedulerStage(Stage):
    def __init__(self, *args, csrtable, warp_count: int = 32, warp_size: float = 32, policy: str = "RR", **kwargs):
        super().__init__(*args, **kwargs)

        # static shit
        self.warp_count: int = warp_count
        self.num_groups: int = (warp_count + 1) // 2
        self.warp_size: float = warp_size
        self.at_barrier: int = 0
        self.policy: str = policy
        self.csrtable = csrtable
        self.start_flush: bool = False

        # warp table
        self.warp_table: List[WarpGroup] = [WarpGroup(pc=0, group_id=id) for id in range(self.num_groups)]
        self.warp_init: int = 0

        # initialization
        self.free_warp: int = 0

        # oldest queue
        self.oldest: List[int] = []
        self.unissued: List[int] = [warp for warp in range(self.num_groups)]

        # scheduler bookkeeping
        self.rr_index: int = 0
        self.gto_index: int = 0

        # eop stuff
        self.eop: bool = False
        self.warp_id: int = 0

        # debug
        self.issued_warp_last_cycle: Optional[int] = None

        # could add perf counters
        self.stop_fetching = False

    # figuring out which warps can/cant issue
    def collision(self):
        # pop from decode, issue, writeback
        decode_ctrl = self.forward_ifs_read["Decode_Scheduler"].pop()
        issue_ctrl = self.forward_ifs_read["Issue_Scheduler"].pop()
        branch_ctrl = self.forward_ifs_read["Branch_Scheduler"].pop()
        writeback_ctrl = self.forward_ifs_read["Writeback_Scheduler"].pop()
        
        # print("[SchedulerStage] Warp Issue Check, Decode Control:", decode_ctrl)
        # print("[SchedulerStage] Warp Issue Check, Issue Control:", issue_ctrl)
        # print("[SchedulerStage] Warp Issue Check, Branch Control:", branch_ctrl)
        # print("[SchedulerStage] Warp Issue Check, Writeback Control:", writeback_ctrl)

        # if im getting my odd warp EOP out of my i$
        if self.eop and self.warp_id % 2:
            self.warp_table[self.warp_id // 2].state = WarpState.STALL
            self.warp_table[self.warp_id // 2].finished_packet = True

        # change pc for branch
        if branch_ctrl is not None:
            self.warp_table[branch_ctrl["warp_group"]].pc = branch_ctrl["dest"]
        
        # check all my things in the issue
        if issue_ctrl is not None:
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
            # print("hello")

            # multiple writebacks can happen in the same cycle so we need to loop through all of them and apply the changes to the warp table accordingly
            for data in writeback_ctrl:
                group = data["warp_group_id"]
                warp_id = data["warp_id"]
                new_mask = data["new_mask"]

                # print(f"Group: {group}, Warp ID: {warp_id}, New Mask: {new_mask}")

                # TODO: change this later so it can decrement the inflight counter as many times for the number of writebacks the buffer was able to do.
                self.warp_table[group].in_flight -= 1

                if new_mask is not None:
                    if warp_id % 2 == 0:
                        self.warp_table[group].halt_mask_even = new_mask
                    else:
                        self.warp_table[group].halt_mask_odd = new_mask

                even_dead = self.warp_table[group].halt_mask_even.uint == 0
                odd_dead  = self.warp_table[group].halt_mask_odd.uint == 0

                if even_dead and odd_dead:
                    self.warp_table[group].state = WarpState.HALT
                    self.warp_table[group].halt = 1
                    return

                if self.warp_table[group].in_flight == 0:
                    if self.warp_table[group].state != WarpState.HALT:
                        self.warp_table[group].state = WarpState.READY
                        self.warp_table[group].finished_packet = False
                    
                    else:
                        self.warp_table[group].halt = 1
        
        # set group to halt

    # creating instruction class
    def make_instruction(self, group, warp, pc):
        if warp % 2 == 0:
            active_mask = self.warp_table[group].halt_mask_even
        else:            
            active_mask = self.warp_table[group].halt_mask_odd 

        inst = Instruction(pc=Bits(uint=pc, length=32), warp_id=warp, warp_group_id=group, active_mask=active_mask)
        return inst 
    
    # pushing to latch
    def push_instruction(self, inst):
        # print(f"[Scheduler] Pushing inst to ahead latch")
        self.ahead_latch.push(inst)
        return

    # init blocks onto sm 
    def tbs_init(self):
        if not self.behind_latch.valid:
            return

        # TODO: simulate (num warps + (2 or 1 depending on how tbs works) cycles to init)
        tb_id, tb_size, start_pc = self.behind_latch.pop()

        # print(f"\n FUCKING TBS SHIT:\n")
        # print(f"{tb_id, tb_size, start_pc}\n\n")
        base_id = 0

        for _ in range(math.ceil(tb_size / self.warp_size)):
            if not (self.free_warp % 2):
                self.warp_table[self.free_warp // 2].pc = start_pc
                self.warp_table[self.free_warp // 2].state = WarpState.READY
                self.warp_table[self.free_warp // 2].halt = 0
            
            self.csrtable.write_data(self.free_warp, base_id, tb_id, tb_size)
            base_id += self.warp_size
            self.free_warp += 1

    def halt(self):
        if self.start_flush is False:
            if all(group.halt == 1 for group in self.warp_table):
                # print("RECEIVED HALT FOR ALL WARPS, ENABLING DCACHE FLUSH.")
                self.start_flush = True
                self.forward_ifs_write["Scheduler_LDST"].push({"flush_start": 1})
        return

    # round robin policy
    def round_robin(self):
        for tries in range(self.num_groups):
            # print(len(self.warp_table))
            warp_group = self.warp_table[self.rr_index]

            # if we can issue this warp group
            if warp_group.state == WarpState.READY:
                # increment in-flight counter
                warp_group.in_flight += 1

                # if the last issue for the group was odd DONT INCREATE RR_INDEX
                if not warp_group.last_issue_even:
                    warp_group.last_issue_even = True
                    
                    instr = self.make_instruction(warp_group.group_id, (warp_group.group_id * 2), warp_group.pc)
                    # print(f"[Scheduler] Issuing an instruction for warp group: {warp_group.group_id}, warp: {instr.warp_id}, {(warp_group.group_id * 2)}, pc: {warp_group.pc}")
                    self.push_instruction(instr)
                    return 
                

                # if the last issue for the group was even increase index
                else:
                    self.rr_index = (self.rr_index + 1) % self.num_groups
                    current_pc = warp_group.pc
                    warp_group.pc += 4
                    warp_group.last_issue_even = False

                    instr = self.make_instruction(warp_group.group_id, (warp_group.group_id * 2) + 1, current_pc)
                    # print(f"[Scheduler] Issuing an instruction for warp group: {warp_group.group_id}, warp: {instr.warp_id}, {(warp_group.group_id * 2)}, pc: {warp_group.pc}")
                    self.push_instruction(instr)
                    return
                
            else:
                # print(f"[Scheduler] Round-robin skipping this warp group {tries} due to being stalled.")
                self.rr_index = (self.rr_index + 1) % self.num_groups

        # nothing can fetch here
        return # NONE

    # greedy policy 
    def greedy_oldest(self):
        # current warp group is good for issue
        if self.warp_table[self.gto_index].state == WarpState.READY:
            group = self.warp_table[self.gto_index]
            group.in_flight += 1

            # issue even
            if not group.last_issue_even:
                group.last_issue_even = True

                instr = self.make_instruction(group.group_id, (group.group_id * 2), group.pc)
                # print(f"[Scheduler] Issuing an instruction for {group.group_id}, {(group.group_id * 2)}, {group.pc}")
                self.push_instruction(instr)
                return

            # issue odd
            else:
                current_pc = group.pc
                group.pc += 4
                group.last_issue_even = False

                instr = self.make_instruction(group.group_id, (group.group_id * 2) + 1, current_pc)
                # print(f"[Scheduler] Issuing an instruction for {group.group_id}, {(group.group_id * 2) + 1}, {current_pc}")
                self.push_instruction(instr)
                return

        # need to find next potential warp group
        else:
            # look through oldest queue
            for group_id in self.oldest:
                if self.warp_table[group_id].state == WarpState.READY:
                    # update gto trackers
                    self.gto_index = group_id

                    group = self.warp_table[group_id]
                    group.in_flight += 1

                    # issue even
                    if not group.last_issue_even:
                        group.last_issue_even = True

                        instr = self.make_instruction(group.group_id, (group.group_id * 2), group.pc)
                        # print(f"[Scheduler] Issuing an instruction for {group.group_id}, {(group.group_id * 2)}, {group.pc}")
                        self.push_instruction(instr)
                        return

                    # issue odd
                    else:
                        current_pc = group.pc
                        group.pc += 4
                        group.last_issue_even = False

                        instr = self.make_instruction(group.group_id, (group.group_id * 2) + 1, current_pc)
                        # print(f"[Scheduler] Issuing an instruction for {group.group_id}, {(group.group_id * 2) + 1}, {current_pc}")
                        self.push_instruction(instr)
                        return

            # look through unstarted warps
            for idx, group_id in enumerate(self.unissued):
                if self.warp_table[group_id].state == WarpState.READY:
                    # update gto trackers
                    self.gto_index = group_id
                    self.oldest.append(group_id)
                    self.unissued.pop(idx)

                    group = self.warp_table[group_id]
                    group.in_flight += 1

                    # issue even
                    if not group.last_issue_even:
                        group.last_issue_even = True

                        instr = self.make_instruction(group.group_id, (group.group_id * 2), group.pc)
                        # print(f"[Scheduler] Issuing an instruction for {group.group_id}, {(group.group_id * 2)}, {group.pc}")
                        self.push_instruction(instr)
                        return

                    # issue odd
                    else:
                        current_pc = group.pc
                        group.pc += 4
                        group.last_issue_even = False

                        instr = self.make_instruction(group.group_id, (group.group_id * 2) + 1, current_pc)
                        # print(f"[Scheduler] Issuing an instruction for {group.group_id}, {(group.group_id * 2) + 1}, {current_pc}")
                        self.push_instruction(instr)
                        return
                    
        # nothing can fetch here
        return

    # warp scheduler compute method
    def compute(self):
        # nothing on the sm LOL
        if not self.warp_table:
            return

        # wait for ihit
        icache_ctrl = self.forward_ifs_read["ICache_Scheduler"].pop()
        # print("[SchedulerStage] Warp Issue Check, ICache Control:", icache_ctrl)

        if not icache_ctrl["fetch"]:
            # print("[Scheduler] MISS in ICache, STALLING.")
            return # RETURN NOTHING DONT PUSH ANYTHING EITHER

        self.eop = icache_ctrl["eop"]
        self.warp_id = icache_ctrl["warp_id"]
        
        # check halt condition before we do any work
        self.halt()
        # determining next states
        self.collision()

        match self.policy:
            case "RR":
                self.round_robin()
            case "GTO":
                self.greedy_oldest()

        # init from TBS if needed
        self.tbs_init()

        # self.ahead_latch.push(instr)
