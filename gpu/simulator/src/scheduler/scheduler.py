import sys, os
from collections import deque
from dataclasses import dataclass, field
from typing import List, Any, Optional, Dict
from enum import Enum
from pathlib import Path
from bitstring import Bits
gpu_root = Path(__file__).resolve().parents[3]
sys.path.append(str(gpu_root))
print("here", gpu_root)
from simulator.base_class import DecodeType, Instruction, WarpState, WarpGroup, ForwardingIF, LatchIF, Stage

class SchedulerStage(Stage):
    def __init__(self, *args, start_pc, warp_count: int = 32, warp_size: int = 32, policy: str = "RR", **kwargs):
        super().__init__(*args, **kwargs)

        # static shit
        self.warp_count: int = warp_count
        self.num_groups: int = (warp_count + 1) // 2
        self.warp_size: int = warp_size
        self.at_barrier: int = 0
        self.policy: str = policy

        # warp table
        self.warp_table: List[WarpGroup] = [WarpGroup(pc=start_pc, group_id=id) for id in range(self.num_groups)]

        # oldest queue
        self.oldest: List[WarpGroup] = []

        # scheduler bookkeeping
        self.rr_index: int = 0
        self.current_warp: int = 0
        # self.max_issues_per_cycle: int = 1
        # self.ready_queue = deque(range(warp_count))

        # debug
        self.issued_warp_last_cycle: Optional[int] = None

        # could add perf counters
        self.stop_fetching = False
    
    # figuring out which warps can/cant issue
    def collision(self):
        # pop from decode, issue, writeback
        icache_ctrl = self.forward_ifs_read["ICache_Scheduler"].pop()
        decode_ctrl = self.forward_ifs_read["Decode_Scheduler"].pop()
        issue_ctrl = self.forward_ifs_read["Issue_Scheduler"].pop()
        branch_ctrl = self.forward_ifs_read["Branch_Scheduler"].pop()
        writeback_ctrl = self.forward_ifs_read["Writeback_Scheduler"].pop()

        # # if im getting my odd warp EOP out of my decode
        # print("[SchedulerStage] Warp Issue Check, Decode Control:", decode_ctrl)
        # print("[SchedulerStage] Warp Issue Check, Issue Control:", issue_ctrl)
        # print("[SchedulerStage] Warp Issue Check, Branch Control:", branch_ctrl)
        # print("[SchedulerStage] Warp Issue Check, Writeback Control:", writeback_ctrl)
        # if (decode_ctrl is None and issue_ctrl is None and branch_ctrl is None and writeback_ctrl is None):
        #     print("[SchedulerStage] No control signals received, bubble.")
        #     return

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

    def make_instruction(self, group, warp, pc):
        inst = Instruction(pc=pc, warp_id=warp, warp_group_id=group)
        return inst 
    
    def push_instruction(self, inst):
        if self.ahead_latch.ready_for_push:
            print(f"[Scheduler] Pushing inst to ahead latch")
            self.ahead_latch.push(inst)
            return True
        else:
            print(f"[Scheduler] STALLED by ahead latch")
            return False 
        
    def dummy_tbs_pop(self):
        if not self.behind_latch.valid:
            return None
        req = self.behind_latch.pop()
        print(f"[{self.name}] Popped from TBS latch: {req}")
        return req

    # RETURN INSTRUCTION OBJECT ALWAYS
    def round_robin(self):
        # initialize instruction class
        instr = Instruction(None, None, None, None, None, None, None, None, None)

        for tries in range(self.num_groups):
            warp_group = self.warp_table[self.rr_index]

            # if we can issue this warp group
            if warp_group.state == WarpState.READY:
                # increment in-flight counter
                warp_group.in_flight += 1

                # if the last issue for the group was odd DONT INCREATE RR_INDEX
                if not warp_group.last_issue_even:
                    warp_group.last_issue_even = True
                    
                    # instr = self.make_instruction(warp_group.group_id, (warp_group.group_id * 2), warp_group.pc)
                    self.push_instruction(instr)
                    return instr 
                
                    # DEPRECIATED
                    # return warp_group.group_id, warp_group.group_id * 2, warp_group.pc # EVEN WARP INSTRUCTION

                # if the last issue for the group was even increase index
                else:
                    self.rr_index = (self.rr_index + 1) % self.num_groups
                    current_pc = warp_group.pc
                    warp_group.pc += 4
                    warp_group.last_issue_even = False

                    instr.pc = Bits(current_pc)
                    instr.warp_id = (warp_group.group_id * 2) + 1
                    instr.warp_group_id = warp_group.group_id
                    return instr
                
            else:
                self.rr_index = (self.rr_index + 1) & self.num_groups

        # nothing can fetch here
        return instr # NONE


    ############### RETURN INSTRUCTION OBJECT ALWAYS WIP
    def greedy_oldest(self):
        # initialize instruction class
        instr = Instruction(None, None, None, None, None, None, None, None, None)

        # current group
        curr_group = self.warp_table[self.current_warp]

        # if current group is able to issue
        if curr_group.state == WarpState.READY:
            # odd group
            if not curr_group.last_issue_even:
                curr_group.last_issue_even = True

                instr.pc = curr_group.pc
                instr.warp_id = curr_group.group_id * 2
                instr.warp_group_id = curr_group.group_id
                return instr

            # even group
            else:
                curr_group.last_issue_even = False
                current_pc = curr_group.pc
                curr_group.pc += 4

                instr.pc = current_pc
                instr.warp_id = (curr_group.group_id * 2) + 1
                instr.warp_group_id = curr_group.group_id
                return instr
            
        # current group not able to issue
        else:

            return instr

        # nothing
        return instr
    
    # PURE ROUND ROBIN RIGHT NOW, NEED TO FIND THE RR_INDEX
    def compute(self):
        # # waiting for ihit
        # for fwd_if in self.forward_ifs_read.values():
        #     if fwd_if.wait:
        #         print(f"[{self.name}] Stalled due to wait from next stage")
        #         # same issue here with nontype and ints
        #         return 10000, 10000, 10000

        self.collision()

        # wait for ihit
        if not self.forward_ifs_read["ICache_Scheduler"].pop():
            self.ahead_latch.push(Instruction(None, None, None, None, None, None, None, None, None))
            return

        match self.policy:
            case "RR":
                instr = self.round_robin()
            case "GTO":
                instr = self.greedy_oldest()

        self.ahead_latch.push(instr)
