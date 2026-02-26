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
print = lambda *args, **kwargs: None

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
        self.gto_index: int = -1

        # debug
        self.issued_warp_last_cycle: Optional[int] = None

        # could add perf counters
        self.stop_fetching = False

    ####### HELPER CLASSES
    # figuring out which warps can/cant issue
    def collision(self):
        # pop from decode, issue, writeback
        decode_ctrl = self.forward_ifs_read["Decode_Scheduler"].pop()
        issue_ctrl = self.forward_ifs_read["Issue_Scheduler"].pop()
        branch_ctrl = self.forward_ifs_read["Branch_Scheduler"].pop()
        writeback_ctrl = self.forward_ifs_read["Writeback_Scheduler"].pop()
        
        print("[SchedulerStage] Warp Issue Check, Decode Control:", decode_ctrl)
        print("[SchedulerStage] Warp Issue Check, Issue Control:", issue_ctrl)
        print("[SchedulerStage] Warp Issue Check, Branch Control:", branch_ctrl)
        print("[SchedulerStage] Warp Issue Check, Writeback Control:", writeback_ctrl)

        # if im getting my odd warp EOP out of my decode
        if decode_ctrl is not None and decode_ctrl["type"] == DecodeType.EOP and decode_ctrl["warp_id"] % 2:
            if decode_ctrl["type"] == DecodeType.EOP and decode_ctrl["warp_id"] % 2:
                self.warp_table[decode_ctrl["warp_id"] // 2].state = WarpState.STALL
                self.warp_table[decode_ctrl["warp_id"] // 2].pc = decode_ctrl["pc"]
                self.warp_table[decode_ctrl["warp_id"] // 2].finished_packet = True

        # if im getting my odd warp halt out of my decode
        elif decode_ctrl is not None and decode_ctrl["type"] == DecodeType.halt and decode_ctrl["warp_id"] % 2:
            self.warp_table[decode_ctrl["warp_id"] // 2].state = WarpState.HALT

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
            self.warp_table[writeback_ctrl["warp_group"]].in_flight -= 1
            if self.warp_table[writeback_ctrl["warp_group"]].in_flight == 0 and self.warp_table[writeback_ctrl["warp_group"]].state != WarpState.BARRIER and self.warp_table[writeback_ctrl["warp_group"]].state != WarpState.HALT:
                self.warp_table[writeback_ctrl["warp_group"]].state = WarpState.READY
                self.warp_table[writeback_ctrl["warp_group"]].finished_packet = False

    # creating instruction class
    def make_instruction(self, group, warp, pc):
        inst = Instruction(pc=pc, warp_id=warp, warp_group_id=group)
        return inst 
    
    # pushing to latch
    def push_instruction(self, inst):
        print(f"[Scheduler] Pushing inst to ahead latch")
        self.ahead_latch.push(inst)
        return

    # SEND HALT BACK TO TBS SOMEWHERE 
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
            
            self.csrtable.write_data(self.free_warp, base_id, tb_id, tb_size)
            base_id += self.warp_size
            self.free_warp += 1

    # round robin policy
    def round_robin(self):
        for tries in range(self.num_groups):
            print(len(self.warp_table))
            warp_group = self.warp_table[self.rr_index]

            # if we can issue this warp group
            if warp_group.state == WarpState.READY:
                # increment in-flight counter
                warp_group.in_flight += 1

                # if the last issue for the group was odd DONT INCREATE RR_INDEX
                if not warp_group.last_issue_even:
                    warp_group.last_issue_even = True
                    
                    instr = self.make_instruction(warp_group.group_id, (warp_group.group_id * 2), warp_group.pc)
                    print(f"[Scheduler] Issuing an instruction for {warp_group.group_id}, {(warp_group.group_id * 2)}, {warp_group.pc}")
                    self.push_instruction(instr)
                    return 
                

                # if the last issue for the group was even increase index
                else:
                    self.rr_index = (self.rr_index + 1) % self.num_groups
                    current_pc = warp_group.pc
                    warp_group.pc += 4
                    warp_group.last_issue_even = False

                    instr = self.make_instruction(warp_group.group_id, (warp_group.group_id * 2) + 1, current_pc)
                    print(f"[Scheduler] Issuing an instruction for {warp_group.group_id}, {(warp_group.group_id * 2) + 1}, {current_pc}")
                    self.push_instruction(instr)
                    return
                
            else:
                print(f"[Scheduler] Round-robin skipping this warp group {tries} due to being stalled.")
                self.rr_index = (self.rr_index + 1) % self.num_groups

        # nothing can fetch here
        return # NONE

    ############### greedy policy WIP
    def greedy_oldest(self):
        # current warp group is good for issue
        if self.warp_table[self.gto_index].state == WarpState.READY:
            group = self.warp_table[self.gto_index]
            group.in_flight += 1

            # issue even
            if not group.last_issue_even:
                group.last_issue_even = True

                instr = self.make_instruction(group.group_id, (group.group_id * 2), group.pc)
                print(f"[Scheduler] Issuing an instruction for {group.group_id}, {(group.group_id * 2)}, {group.pc}")
                self.push_instruction(instr)
                return

            # issue odd
            else:
                current_pc = group.pc
                group.pc += 4
                group.last_issue_even = False

                instr = self.make_instruction(group.group_id, (group.group_id * 2) + 1, current_pc)
                print(f"[Scheduler] Issuing an instruction for {group.group_id}, {(group.group_id * 2) + 1}, {group.pc}")
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
                        print(f"[Scheduler] Issuing an instruction for {group.group_id}, {(group.group_id * 2)}, {group.pc}")
                        self.push_instruction(instr)
                        return

                    # issue odd
                    else:
                        current_pc = group.pc
                        group.pc += 4
                        group.last_issue_even = False

                        instr = self.make_instruction(group.group_id, (group.group_id * 2) + 1, current_pc)
                        print(f"[Scheduler] Issuing an instruction for {group.group_id}, {(group.group_id * 2) + 1}, {group.pc}")
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
                        print(f"[Scheduler] Issuing an instruction for {group.group_id}, {(group.group_id * 2)}, {group.pc}")
                        self.push_instruction(instr)
                        return

                    # issue odd
                    else:
                        current_pc = group.pc
                        group.pc += 4
                        group.last_issue_even = False

                        instr = self.make_instruction(group.group_id, (group.group_id * 2) + 1, current_pc)
                        print(f"[Scheduler] Issuing an instruction for {group.group_id}, {(group.group_id * 2) + 1}, {group.pc}")
                        self.push_instruction(instr)
                        return
                    
        # nothing can fetch here
        return

    # warp scheduler compute method
    def compute(self):
        # nothing on the sm LOL
        if not self.warp_table:
            return

        # determining next states
        self.collision()

        # wait for ihit
        if not self.forward_ifs_read["ICache_Scheduler"].pop():
            print("[Scheduler] MISS in ICache, STALLING.")
            return # RETURN NOTHING DONT PUSH ANYTHING EITHER

        match self.policy:
            case "RR":
                self.round_robin()
            case "GTO":
                self.greedy_oldest()

        # init from TBS if needed
        self.tbs_init()

        # self.ahead_latch.push(instr)
