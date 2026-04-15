from builtins import all, print
from collections import deque
from dataclasses import dataclass, field
from typing import List, Any, Optional, Dict
from enum import Enum
from pathlib import Path
from bitstring import Bits
from common.custom_enums_multi import H_Op, I_Op
from simulator.mem_types import DecodeType
from simulator.instruction import Instruction
from simulator.warp import WarpState, WarpGroup, Warp
from simulator.stage import Stage
from simulator.scheduler.csrtable import CsrTable
import math
from simulator.interfaces import ForwardingIF, LatchIF
from simulator.utils.performance_counter.scheduler import SchedulerPerfCount as PerfCount
from simulator.utils.performance_counter.telemeter import Telemeter

# comment/uncomment for printing out debug info
# print = lambda *args, **kwargs: None

class SchedulerStage(Stage):
    def __init__(self, *args, csrtable, warp_count: int = 32, warp_size: float = 32, policy: str = "RR", telemeter: Telemeter, **kwargs):
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
        self.warp_table: List[WarpGroup] = [WarpGroup(group_id=id, warps=[Warp(pc=0, id=id*2, finished_packet=True), Warp(pc=0, id=id*2+1, finished_packet=True)], halt_mask_even=Bits(uint=0x0, length=32), halt_mask_odd=Bits(uint=0x0, length=32)) for id in range(self.num_groups)]
        self.warp_init: int = 0

        # initialization
        self.free_warp: int = 0

        # gto index queues
        self.oldest: List[int] = []
        self.unissued: List[int] = [group for group in range(self.num_groups)]

        # scheduler bookkeeping
        self.rr_index: int = 0
        self.gto_index: int = 0

        # eop stuff
        self.eop: bool = False
        self.warp_id: int = 0

        # Kai Ze: create halt signal to only fire once
        self.halt_sent: bool = False

        # debug / temp
        self.issued_warp_last_cycle: Optional[int] = None
        self.stop_fetching = False
        self.system_finished: bool = False

        # perf counters
        self.telemeter = telemeter
        self.perf_count = PerfCount(name=self.name)
        self.telemeter.register_unit(self.perf_count)

    def dump(self):
        print(f"\n{'='*80}")
        print(f"{'WARPGROUP TABLE DUMP':^80}")
        print(f"{'='*80}")
        print(f"---------\n")
        print(f"Warp id: base_id | tb_id | tb_size")

        for group in self.warp_table:
            print(f"group: {group.group_id}, halt: {group.halt}, issue: {group.issue}")
            print(f"    warp: {group.warps[0].id}, state: {group.warps[0].state}, halt_mask: {group.halt_mask_even}, pc: {group.warps[0].pc}, in_flight: {group.warps[0].in_flight}, finished_packet: {group.warps[0].finished_packet}")
            print(f"    warp: {group.warps[1].id}, state: {group.warps[1].state}, halt_mask: {group.halt_mask_odd}, pc: {group.warps[1].pc}, in_flight: {group.warps[1].in_flight}, finished_packet: {group.warps[1].finished_packet}\n")

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

    # init blocks onto sm TODO: UPDATE FOR INDIVIDUAL WARPS
    def tbs_init(self):
        if not self.behind_latch.valid:
            return

        # TODO: simulate (num warps + (2 or 1 depending on how tbs works) cycles to init)
        tb_id, tb_size, start_pc = self.behind_latch.pop()
        print("receive")

        # print(f"\n FUCKING TBS SHIT:\n")
        # print(f"{tb_id, tb_size, start_pc}\n\n")
        base_id = 0
        self.csrtable.add_blk(tb_id)

        self.halt_sent = False
        self.system_finished = False

        # WILL NEED TO CHANGE FOR FUTURE ITERATIONS, BLOCK SIZE != 1024 AND # OF BLOCKS != 1
        gto_init = self.unissued.pop(0)
        self.oldest.append(gto_init)

        temp_tb_size = tb_size
        for _ in range(math.ceil(tb_size / self.warp_size)):
            self.warp_table[self.free_warp // 2].warps[self.free_warp % 2].pc = start_pc
            self.warp_table[self.free_warp // 2].warps[self.free_warp % 2].state = WarpState.READY
            self.warp_table[self.free_warp // 2].warps[self.free_warp % 2].finished_packet = False

            if self.free_warp % 2 == 0:
                # TODO: CHECK THIS SHIT AFTER U FINISH COLLISION
                self.warp_table[self.free_warp // 2].issue = True
                if temp_tb_size - 32 >= 0:
                    self.warp_table[self.free_warp // 2].halt_mask_even = Bits(uint=0xffffffff, length=32)
                else:
                    mask_even = 0
                    for i in range(32):
                        mask_even |= (i < temp_tb_size) << i
                    self.warp_table[self.free_warp // 2].halt_mask_even = Bits(uint=mask_even, length=32)
                self.warp_table[self.free_warp // 2].halt = 0
                self.warp_table[self.free_warp // 2].last_issue_even = False
            else:
                if temp_tb_size - 32 == 0:
                    self.warp_table[self.free_warp // 2].halt_mask_odd = Bits(uint=0xffffffff, length=32)
                else:
                    mask_odd = 0
                    for i in range(32):
                        mask_odd |= (i < temp_tb_size) << i
                    self.warp_table[self.free_warp // 2].halt_mask_odd = Bits(uint=mask_odd, length=32)
            temp_tb_size -= 32
            
            self.csrtable.write_data(self.free_warp, base_id, tb_id, tb_size)
            base_id += self.warp_size
            self.free_warp += 1
        
        print(f"CSR TABLE DUMP INITIALIZED FOR TBID#{tb_id}")
        self.csrtable.dump()
        print(f"WARP TABLE DUMP INITIALIZED FOR TBID#{tb_id}")
        self.dump()  

    def halt(self):
        # Kai Ze: only fire when at least one warp has been initialized, and only once
        if not self.halt_sent and self.free_warp > 0 and all(group.halt == 1 for group in self.warp_table):
                # print("RECEIVED HALT FOR ALL WARPS, ENABLING DCACHE FLUSH.")
            self.forward_ifs_write["Scheduler_LDST"].push({"halt": True})
            self.halt_sent = True

        return

    # figuring out which warps can/cant issue 
    def collision(self):
        # pop from issue, jump, writeback
        issue_ctrl = self.forward_ifs_read["Issue_Scheduler"].pop()
        jump_ctrl = self.forward_ifs_read["Branch_Scheduler"].pop()
        writeback_ctrl = self.forward_ifs_read["Writeback_Scheduler"].pop()

        # move to halt function later
        ldst_ctrl = self.forward_ifs_read["LDST_Scheduler"].pop()
        if ldst_ctrl is not None and ldst_ctrl.get("flush_complete"):
            print("Scheduler: Received halt")
            self.system_finished = True
            self.free_warp = 0
            self.rr_index = 0
            self.gto_index = 0
            self.oldest = []
            self.unissued = [group for group in range(self.num_groups)]

            print("CSR TABLE DUMP AT HALT:")
            self.csrtable.dump()
            print("WARP TABLE DUMP AT HALT:")
            self.dump()
            ## TODO: will need to expand for non 1024 size tb in cx02
            self.forward_ifs_write["Scheduler_TBS"].push(list(self.csrtable.active_blks))
            self.csrtable.reset_csr()
            
            # TODO: plug in reset signals to the reg file and pred reg 

        # if im getting my odd warp EOP out of my i$
        if self.eop:
            self.warp_table[self.warp_id // 2].warps[self.warp_id % 2].state = WarpState.STALL
            self.warp_table[self.warp_id // 2].warps[self.warp_id % 2].finished_packet = True

        # change pc for branch
        if jump_ctrl is not None:
            self.warp_table[jump_ctrl["warp"] // 2].warps[jump_ctrl["warp"] % 2].pc = jump_ctrl["dest"]
        
        # check all my things in the issue
        if issue_ctrl is not None:
            for ibuffer in range(self.num_groups):
                if self.warp_table[ibuffer].halt != 1:
                    # i buffer full, stop issuing
                    if issue_ctrl[ibuffer] == 1:
                        self.warp_table[ibuffer].warps[0].state = WarpState.STALL
                        self.warp_table[ibuffer].warps[1].state = WarpState.STALL

                    # i buffer opens up but you can only issue to it if you haven't finished scheduling ur current packet
                    else:
                        for warp in self.warp_table[ibuffer].warps:
                            if not warp.finished_packet:
                                warp.state = WarpState.READY

        # decrement my in flight counter and go back to ready
        if not len(writeback_ctrl) == 0:
            # print("hello")

            # multiple writebacks can happen in the same cycle so we need to loop through all of them and apply the changes to the warp table accordingly
            for data in writeback_ctrl:
                group = data["warp_group_id"]
                warp_id = data["warp_id"]
                new_mask = data["new_mask"]

                # print(f"Group: {group}, Warp ID: {warp_id}, New Mask: {new_mask}")

                # TODO: change this later so it can decrement the inflight counter as many times for the number of writebacks the buffer was able to do.
                self.warp_table[group].warps[warp_id % 2].in_flight -= 1

                if new_mask is not None:
                    if warp_id % 2 == 0:
                        self.warp_table[group].halt_mask_even = new_mask
                        print(f"even mask: {new_mask}\n")
                        even_dead = self.warp_table[group].halt_mask_even.uint == 0
                        if even_dead:
                            self.warp_table[group].warps[0].state = WarpState.HALT

                    else:
                        self.warp_table[group].halt_mask_odd = new_mask
                        print(f"odd mask: {new_mask}\n")
                        odd_dead  = self.warp_table[group].halt_mask_odd.uint == 0
                        if odd_dead:
                            self.warp_table[group].warps[1].state = WarpState.HALT

                if self.warp_table[group].halt_mask_even.uint == 0 and self.warp_table[group].halt_mask_odd.uint == 0:
                    self.warp_table[group].halt = 1

                if self.warp_table[group].warps[warp_id % 2].in_flight == 0:
                    if self.warp_table[group].warps[warp_id % 2].state != WarpState.HALT:
                        self.warp_table[group].warps[warp_id % 2].state = WarpState.READY
                        self.warp_table[group].warps[warp_id % 2].finished_packet = False
                    
                    # else:
                    #     self.warp_table[group].halt = 1
        
        # setting stall for warpgroup if BOTH warps in group are stalled
        for group in self.warp_table:
            if group.warps[0].state == WarpState.READY or group.warps[1].state == WarpState.READY:
                group.issue = True
            else:
                group.issue = False

    # fetching warp from group
    def fetch(self, warp_group: WarpGroup):
        # if the last issue for the group was even DONT INCREATE RR_INDEX
        if not warp_group.last_issue_even:
            warp_group.last_issue_even = True
            
            # only fetch if warp is able to issue
            if warp_group.warps[0].state == WarpState.READY:
                instr = self.make_instruction(warp_group.group_id, (warp_group.group_id * 2), warp_group.warps[0].pc)
                warp_group.warps[0].in_flight += 1
                warp_group.warps[0].pc += 4
                print(f"[Scheduler] Issuing an instruction for warp group: {instr.warp_group_id}, warp: {instr.warp_id}, pc: {instr.pc}, state: {warp_group.warps[0].state}")
                self.push_instruction(instr)
            return 
        

        # if the last issue for the group was odd increase index
        else:
            self.rr_index = (self.rr_index + 1) % self.num_groups
            warp_group.last_issue_even = False

            if warp_group.warps[1].state == WarpState.READY:
                instr = self.make_instruction(warp_group.group_id, (warp_group.group_id * 2) + 1, warp_group.warps[1].pc)
                warp_group.warps[1].in_flight += 1
                warp_group.warps[1].pc += 4
                print(f"[Scheduler] Issuing an instruction for warp group: {instr.warp_group_id}, warp: {instr.warp_id}, pc: {instr.pc}, state: {warp_group.warps[1].state}")
                self.push_instruction(instr)
            return
        return

    # round robin policy 
    def round_robin(self):
        for _ in range(self.num_groups):
            # print(len(self.warp_table))
            warp_group = self.warp_table[self.rr_index]

            # if we can fetch this warp group
            if warp_group.issue:
                self.fetch(warp_group=warp_group)
                return True
                
            else:
                self.rr_index = (self.rr_index + 1) % self.num_groups

        # nothing can fetch here
        return False # NONE

    # greedy policy WIP
    def greedy_oldest(self):
        # local bookeeping metrics
        oldest_max = len(self.oldest)
        oldest_idx = 0
        unissued_idx = 0
        oldest_stall = False

        # check to see if current group is good for issue
        for _ in range(self.num_groups):
            warp_group = self.warp_table[self.gto_index]
            oldest_stall = True if oldest_max == oldest_idx else False

            # if we can fetch this warp group
            if warp_group.issue:
                self.fetch(warp_group=warp_group)

                # if we picked out of the unissued list
                if oldest_stall:
                    self.oldest.append(self.unissued.pop(unissued_idx - 1))
                return True
            
            else:
                # look through greedy
                if not oldest_stall:
                    self.gto_index = self.oldest[oldest_idx]
                    oldest_idx += 1

                # look through unissued
                else:
                    self.gto_index = self.unissued[unissued_idx]
                    unissued_idx += 1
                

        # nothing can fetch here
        return False

    # warp scheduler compute method
    def compute(self):
        # nothing on the sm LOL
        if not self.warp_table:
            return

        # wait for ihit
        icache_ctrl = self.forward_ifs_read["ICache_Scheduler"].pop()
        # print("[SchedulerStage] Warp Issue Check, ICache Control:", icache_ctrl)

        self.eop = icache_ctrl["eop"]
        self.warp_id = icache_ctrl["warp_id"]
        
        # check halt condition before we do any work
        self.halt()
        # determining next states
        self.collision()

        if not icache_ctrl["fetch"]:
            # print("[Scheduler] MISS in ICache, STALLING.")
            return # RETURN NOTHING DONT PUSH ANYTHING EITHER

        fetch: bool
        
        match self.policy:
            case "RR":
                fetch = self.round_robin()
            case "GTO":
                fetch = self.greedy_oldest()

        # init from TBS if needed
        self.tbs_init()

        self.perf_count.record_cycle(is_stalled=fetch, is_busy=not fetch, WarpTable=self.warp_table)

        # self.ahead_latch.push(instr)