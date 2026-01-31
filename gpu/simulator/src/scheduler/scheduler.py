import sys, os
from collections import deque
from dataclasses import dataclass, field
from typing import List, Any, Optional, Dict
from enum import Enum
from base import DecodeType, Instruction, WarpState, WarpGroup, ForwardingIF, LatchIF, Stage

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
    
if __name__ == "__main__":
    # forward interfaces into warp scheduler
    decode_scheduler = ForwardingIF(name = "decode_forward_if")
    issue_scheduler = ForwardingIF(name = "issue_forward_if")
    branch_scheduler = ForwardingIF(name = "branch_forward_if")
    writeback_scheduler = ForwardingIF(name = "writeback_forward_if")

    scheduler_stage = SchedulerStage(
        name = "Schedule",
        behind_latch = None, # needs instantiation from TBS
        ahead_latch = None, # needs instantiation to i$
        forward_ifs_read = {"Decode_Scheduler": decode_scheduler, "Issue_Scheduler": issue_scheduler, "Branch_Scheduler": branch_scheduler, "Writeback_Scheduler": writeback_scheduler},
        forward_ifs_write = None,
        start_pc = 0,
        warp_count = 6
    )

    #### CHECKING TO SEE WARPS ALL AT INITIAL STATE ####
    # initialization check
    print("INITIAL CHECK OF STATES")
    for warp_group in scheduler_stage.warp_table:
        print(f"warp group: {warp_group.group_id} || pc: {warp_group.pc} || state: {warp_group.state}\n")
    #### END OF INITIALIZATION CHECK ####

    #### CYCLING SCHEDULER FOR 2 * (NUMBER OF WARPS) AND CHECKING PC AND STATES EACH TIME (NORAL OPERATION)
    decode_scheduler.push({"type": DecodeType.MOP, "warp_id": 0, "pc": 0})
    issue_scheduler.push([0] * scheduler_stage.num_groups)
    branch_scheduler.push(None)
    writeback_scheduler.push(None)

    for i in range(scheduler_stage.warp_count):
        group, warp, pc = scheduler_stage.compute()
        print(f"group: {group}, warp: {warp}, current pc: {pc}, in fight: {scheduler_stage.warp_table[group].in_flight}\n")
    #### END OF CHECKING SCHEDULER CYCLING (NORMAL OPERATION)

    #### END OF A PACKET FOR A GROUP
    print(f"\nEOP for group 0 -------\n")

    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}, next_pc: {scheduler_stage.warp_table[group].pc}\n")

    decode_scheduler.push({"type": DecodeType.EOP, "warp_id": 0, "pc": scheduler_stage.warp_table[group].pc})
    
    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}, next_pc: {scheduler_stage.warp_table[group].pc}\n")

    decode_scheduler.push({"type": DecodeType.EOP, "warp_id": 1, "pc": scheduler_stage.warp_table[group].pc})

    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n") 

    print(f"CURRENT STATES ===\n")
    for warp_group in scheduler_stage.warp_table:
        print(f"warp group: {warp_group.group_id} || pc: {warp_group.pc} || state: {warp_group.state}\n")
    #### END OF EOP TEST

    #### RESETTING
    decode_scheduler.push({"type": DecodeType.MOP, "warp_id": 0, "pc": 0})
    ####

    print(f"cycling through warps a couple times")
    for i in range(7):
        group, warp, pc = scheduler_stage.compute()
        print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}, next_pc: {scheduler_stage.warp_table[group].pc}\n")

    print(f"\n\nWriteback writes back both instructions for group 0 -------\n")
    for i in range(4):
        writeback_scheduler.push({"warp_group": 0})

        group, warp, pc = scheduler_stage.compute()
        print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}")
        print(f"group: {0}, current pc: {scheduler_stage.warp_table[0].pc}, in flight: {scheduler_stage.warp_table[0].in_flight}\n")

    print(f"CURRENT STATES ===\n")
    for warp_group in scheduler_stage.warp_table:
        print(f"warp group: {warp_group.group_id} || pc: {warp_group.pc} || state: {warp_group.state}\n")

    writeback_scheduler.push(None)

    print(f"\n\nI Buffer begins to fill up for groups 1 and 2 --------\n")
    issue_scheduler.push([0, 1, 1])

    for i in range(4):
        group, warp, pc = scheduler_stage.compute()
        print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")

    print(f"CURRENT STATES ===\n")
    for warp_group in scheduler_stage.warp_table:
        print(f"warp group: {warp_group.group_id} || pc: {warp_group.pc} || state: {warp_group.state}\n")

    issue_scheduler.push([0, 0, 0])

    print(f"\n\n Testing all warps hit barrier -----------\n")
    for i in range(4):
        group, warp, pc = scheduler_stage.compute()
        print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")

    print(f"CURRENT STATES ===\n")
    for warp_group in scheduler_stage.warp_table:
        print(f"warp group: {warp_group.group_id} || pc: {warp_group.pc} || state: {warp_group.state}\n")

    print(f"barrier at pc = 24\n")
    for i in range(2):
        group, warp, pc = scheduler_stage.compute()
        print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")     

    print(f"\nCURRENT STATES ===\n")
    for warp_group in scheduler_stage.warp_table:
        print(f"warp group: {warp_group.group_id} || pc: {warp_group.pc} || state: {warp_group.state}\n")
    
    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")

    decode_scheduler.push({"type": DecodeType.Barrier, "warp_id": warp, "pc": scheduler_stage.warp_table[group].pc})
    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")

    decode_scheduler.push({"type": DecodeType.Barrier, "warp_id": warp, "pc": scheduler_stage.warp_table[group].pc})
    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")

    print(f"\ngroups at barrier: {scheduler_stage.at_barrier}\n")
    print(f"\nCURRENT STATES ===\n")
    for warp_group in scheduler_stage.warp_table:
        print(f"warp group: {warp_group.group_id} || pc: {warp_group.pc} || state: {warp_group.state}\n")

    decode_scheduler.push({"type": DecodeType.Barrier, "warp_id": warp, "pc": scheduler_stage.warp_table[group].pc})
    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")

    decode_scheduler.push({"type": DecodeType.Barrier, "warp_id": warp, "pc": scheduler_stage.warp_table[group].pc})
    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")

    print(f"\ngroups at barrier: {scheduler_stage.at_barrier}\n")
    print(f"\nCURRENT STATES ===\n")
    for warp_group in scheduler_stage.warp_table:
        print(f"warp group: {warp_group.group_id} || pc: {warp_group.pc} || state: {warp_group.state}\n")
    
    decode_scheduler.push({"type": DecodeType.Barrier, "warp_id": warp, "pc": scheduler_stage.warp_table[group].pc})
    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")

    decode_scheduler.push({"type": DecodeType.Barrier, "warp_id": warp, "pc": scheduler_stage.warp_table[group].pc})
    scheduler_stage.compute()
    print("STALL DIE TO BARRIER->NOBODY SCHEDULED")

    print(f"\ngroups at barrier: {scheduler_stage.at_barrier}\n")
    print(f"\nCURRENT STATES ===\n")
    for warp_group in scheduler_stage.warp_table:
        print(f"warp group: {warp_group.group_id} || pc: {warp_group.pc} || state: {warp_group.state}\n")

    decode_scheduler.push({"type": DecodeType.MOP, "warp_id": 0, "pc": scheduler_stage.warp_table[0].pc})
    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")

    print(f"\ngroups at barrier: {scheduler_stage.at_barrier}\n")
    print(f"\nCURRENT STATES ===\n")
    for warp_group in scheduler_stage.warp_table:
        print(f"warp group: {warp_group.group_id} || pc: {warp_group.pc} || state: {warp_group.state}\n")


    print(f"\n\nBranch unit gives new pc for group 2 --------\n")
    branch_scheduler.push({"warp_group": 2, "dest": 100})
    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")
    print(f"Branch happens now->pc set to 100")

    branch_scheduler.push(None)
    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")

    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")

    for i in range(8):
        group, warp, pc = scheduler_stage.compute()
        print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")

    print(f"HALT CASE ------- \n\n")
    decode_scheduler.push({"type": DecodeType.halt, "warp_id": 0, "pc":scheduler_stage.warp_table[0].pc})
    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")

    decode_scheduler.push({"type": DecodeType.halt, "warp_id": 1, "pc":scheduler_stage.warp_table[0].pc})
    group, warp, pc = scheduler_stage.compute()
    print(f"IN SCHEDULER: group: {group}, warp: {warp}, current pc: {pc}\n")

    print(f"\nCURRENT STATES ===\n")
    for warp_group in scheduler_stage.warp_table:
        print(f"warp group: {warp_group.group_id} || pc: {warp_group.pc} || state: {warp_group.state}\n")

