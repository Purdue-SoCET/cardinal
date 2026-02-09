import enum
from typing import Dict, List, Optional
import logging
from bitstring import Bits

from simulator.base_class import *
from gpu.common.custom_enums_multi import I_Op, S_Op, H_Op
from simulator.base_class import LatchIF
from simulator.execute.functional_sub_unit import FunctionalSubUnit

logger = logging.getLogger(__name__)

class Ldst_Fu(FunctionalSubUnit):
    def __init__(self, num, ldst_q_size=4, wb_buffer_size=1):
        self.ldst_q: list[pending_mem] = []
        self.ldst_q_size: int = ldst_q_size
        self.wb_buffer_size = wb_buffer_size

        self.wb_buffer = [] #completed dcache access buffer

        self.outstanding = False #Whether we have an outstanding dcache request

        super().__init__(num)
        self.dcache_if = LatchIF()
        self.dcache_if.forward_if = ForwardingIF()

        self.connect_interfaces(dcache_if=LatchIF(name=f"MemBranchUnit{num}_Dcache_Latch"), sched_if=LatchIF(name=f"MemBranchUnit{num}_Sched_Latch"))

    def connect_interfaces(self, dcache_if: LatchIF, sched_if = None):
        self.dcache_if: LatchIF = dcache_if
        # self.issue_if: LatchIF = issue_if
        # self.wb_if: LatchIF = wb_if replaced with self.ex_wb_interface
        self.sched_if = sched_if
    
    # def forward_miss(self, instr: Instruction):
    #     self.sched_if.push(instr)

    def tick(self, issue_if: Optional[LatchIF]) -> Optional[Instruction]:
        return_instr = None
        if issue_if and hasattr(issue_if, 'valid'):
            print(f"[DEBUG] Cycle Start: QueueLen={len(self.ldst_q)}, LatchValid={issue_if.valid}")

        if issue_if and len(self.ldst_q) < self.ldst_q_size:
            instr = issue_if.pop()
            if instr != None:
                print(f"LDST_FU: Accepting instruction from latch pc: {instr.pc}")
                self.ldst_q.append(pending_mem(instr))

        #apply backpressure if ldst_q full
        if len(self.ldst_q) == self.ldst_q_size:
            print(f"[LSU]: The queue is full")
            # issue_if.forward_if.set_wait(True)
            self.ready_out = False
        else:
            # issue_if.forward_if.set_wait(False)
            self.ready_out = True

        #send instr to wb if ready
        if self.ex_wb_interface.ready_for_push() and len(self.wb_buffer) > 0:
            return_instr = self.wb_buffer.pop(0)
            if (return_instr):
                print(f"LDST_FU: Pushing Instruction for WB pc: {return_instr.pc}")

        #send req to cache if not waiting for response
        if self.outstanding == False and self.dcache_if.ready_for_push() and len(self.ldst_q) > 0:
            req = self.ldst_q[0].genReq()
            if req:
                self.dcache_if.push(
                    self.ldst_q[0].genReq()
                )
                self.outstanding = True

        #move mem_req to wb_buffer if finished
        if self.outstanding == False and len(self.ldst_q) > 0 and  self.ldst_q[0].readyWB() and len(self.wb_buffer) < self.wb_buffer_size:
            print(f"LDST_FU: Finished processing Instruction pc: {self.ldst_q[0].instr.pc}")
            self.wb_buffer.append(self.ldst_q.pop(0).instr)

        #handle dcache packet
        if self.dcache_if.forward_if.pop():
            if len(self.ldst_q) == 0:
                print(f"LSQ is length 0 and recieved a dcache response")

            payload: dMemResponse = self.dcache_if.forward_if.pop()

            mem_req = self.ldst_q[0]
            match payload.type:
                case 'MISS_ACCEPTED':
                    # logger.info("Handling dcache MISS_ACCEPTED")
                    mem_req.parseMiss(payload)     
                    self.outstanding = False                   
                case 'HIT_STALL':
                    pass
                case 'MISS_COMPLETE':
                    # logger.info("Handling dcache MISS_COMPLETE")
                    mem_req.parseMshrHit(payload)
                case 'FLUSH_COMPLETE':
                    mem_req.parseHit(payload)
                case 'HIT_COMPLETE':
                    # logger.info("Handling dcache HIT_COMPLETE")
                    mem_req.parseHit(payload)
                    self.outstanding = False
    
        return return_instr
            

        


class pending_mem():
    def __init__(self, instr) -> None:
        self.instr: Instruction = instr
        self.finished_idx: List[int] = [0 for i in range(32)]
        self.write: bool
        self.mshr_idx: List[int] = [0 for i in range(32)]
        self.addrs = [0 for i in range(32)]
        
        self.halt = False
        self.write = False
        self.size = "word"

        match self.instr.opcode:
            case I_Op.LW.value:
                self.write = False
                self.size = "word"
            case I_Op.LH.value:
                self.write = False
                self.size = "half"
            case I_Op.LB.value:
                self.write = False
                self.size = "byte"
            
            case S_Op.SW.value:
                self.write = True
                self.size = "word"
            case S_Op.SH.value:
                self.write = True
                self.size = "half"
            case S_Op.SB.value:
                self.write = True
                self.size = "byte"
            
            case H_Op.HALT.value:
                self.write = False
                self.size = "word"
                self.halt = True
            
            case _:
                logger.error(f"Err: instr in ldst cannot be decoded")
                print(f"\t{instr}")
        
        for i in range(32):
            self.finished_idx[i] = 1-self.instr.predicate[i].uint #iirc pred=1'b1
            if self.write and self.instr.predicate[i].uint == 1:
                offset = 0
                if hasattr(self.instr, 'imm') and self.instr.imm is not None:
                    offset = self.instr.imm.int
                self.addrs[i] = self.instr.rdat1[i].int + offset
            elif not self.write and self.instr.predicate[i].uint == 1:
                self.addrs[i] = self.instr.rdat1[i].int + self.instr.rdat2[i].int

    def readyWB(self):
        return all(self.finished_idx)
    
    def genReq(self):
        if self.halt == True:
            return dCacheRequest(
                addr_val=0,
                rw_mode='read',
                size='word',
                halt = True
            )
        for i in range(32):
            if self.finished_idx[i] == 0 and self.mshr_idx[i] == 0:
                return dCacheRequest(
                    addr_val=self.addrs[i],
                    rw_mode='write' if self.write else 'read',
                    size=self.size,
                    store_value=self.instr.rdat2[i].int
                )
        return None
    
    def parseHit(self, payload):
        if self.halt == True:
            self.finished_idx = [1]
            return
        
        for i in range(32):
            if self.addrs[i] == payload.address:
                self.finished_idx[i] = 1

                #set wdat if instr is a read
                if self.write == False:
                    self.instr.wdat[i] = Bits(uint=payload.data, length=32)

    
    def parseMshrHit(self, payload):
        if self.write:
            self.parseHit(payload)
        else:
            num_bytes_block = BLOCK_SIZE_WORDS * WORD_SIZE_BYTES
            block_mask = ~(num_bytes_block - 1)
            incoming_block_addr = payload.address & block_mask

            for i in range(32):
                thread_addr = self.addrs[i]
                thread_block_addr = thread_addr & block_mask
                if (thread_block_addr == incoming_block_addr) and (self.mshr_idx[i] == 1):
                    print(f"[LSU] Wakeup thread {i} (Addr {hex(thread_addr)}) due to Block Match")
                    self.mshr_idx[i] = 0
    
    def parseMiss(self, payload: dMemResponse):
        for i in range(32):
            if self.addrs[i] == payload.address:
                if self.write == False:
                    self.mshr_idx[i] = 1
                elif self.write == True:
                    self.finished_idx[i] = 1