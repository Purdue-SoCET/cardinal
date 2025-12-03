import enum
from typing import Optional
# from gpu_sim.cyclesim.test import ldst
from src.mem import dcache
from base import *
import logging
from bitstring import Bits

logger = logging.getLogger(__name__)


class Ldst_Fu:
    def __init__(self, mshr_size=4, ldst_q_size=4):
        self.ldst_q: list[Coalesce] = []
        self.ldst_q_size: int = ldst_q_size

        # self.dcache_if: Optional[LatchIF] = None
        # self.issue_if: Optional[LatchIF] = None
        # self.wb_if: Optional[LatchIF] = None
        # self.sched_if: Optional[ForwardingIF] = None

        self.wb_buffer = [] #completed dcache access buffer

        self.outstanding = False #Outstanding dcache request addr and uid

    def connect_interfaces(self, dcache_if: LatchIF, issue_if: LatchIF, wb_if: LatchIF, sched_if: ForwardingIF):
        self.dcache_if: LatchIF = dcache_if
        self.issue_if: LatchIF = issue_if
        self.wb_if: LatchIF = wb_if
        self.sched_if: ForwardingIF = sched_if
    
    def forward_miss(self, instr: Instruction):
        self.sched_if.push(instr)

    def tick(self):
        # self.ldst_q[0].logState()
        #populate ldst_q if not full
        if len(self.ldst_q) + 1 < self.ldst_q_size:
            instr = self.issue_if.pop()
            if instr != None:
                self.ldst_q.append(Coalesce(instr))

        #apply backpressure if ldst_q full
        if len(self.ldst_q) == self.ldst_q_size:
            self.issue_if.forward_if.set_wait(True)
        else:
            self.issue_if.forward_if.set_wait(False)

        #send instr to wb if ready
        if self.wb_if.ready_for_push():
            if len(self.wb_buffer) > 0:
                self.wb_if.push(self.wb_buffer.pop(0).instr)
        
        #Push cache access if no outstanding
        if self.outstanding == False and self.dcache_if.ready_for_push() and len(self.ldst_q) > 0 and not self.ldst_q[0].readyWB() and len(self.ldst_q[0].pending_addrs) > 0:
            #push cache access if no outstanding and dcache ready and instr not complete
            coal: Coalesce = self.ldst_q[0]
            addr = coal.genRequestAddr()
            write = coal.write
            pc = coal.instr.pc
            self.outstanding = True
            self.dcache_if.push(
                # CHANGED
                dCacheRequest(
                    addr_val = addr, 
                    rw_mode = write)
            )

        #Handle hit or miss
        if self.dcache_if.forward_if.pop():
            if len(self.ldst_q) == 0:
                logger.warning(f"LSQ is length 0 and recieved a dcache response")
            
            # CHANGED
            payload: dMemResponse = self.dcache_if.forward_if.pop()

            ldst_coal = self.ldst_q[0]
            if payload.hit == True and ldst_coal.in_flight_addr:
                if ldst_coal.inRange(payload.addr, ldst_coal.in_flight_addr):
                    self.outstanding = False
                    ldst_coal.parseHit(payload)
                    if ldst_coal.readyWB():
                        ldst_coal = self.ldst_q.pop(0)
                        self.wb_buffer.append(ldst_coal)
                else:
                    logging.warning("Error: Cache hit wasn't a LDST_Q addr")
            elif payload.hit and ldst_coal.inMSHR(payload.addr):
                ldst_coal.parseHit(payload)
                if ldst_coal.readyWB():
                        ldst_coal = self.ldst_q.pop(0)
                        self.wb_buffer.append(ldst_coal)
                        self.outstanding = False
            elif payload.miss == True:
                if len(self.ldst_q) == 0:
                    logger.warning("LSQ is length 0 and recieved a dcache response")
                if not ldst_coal.missed:
                    self.forward_miss(ldst_coal.instr)
                ldst_coal.parseMiss(payload)
                self.outstanding = False
            else:
                logger.warning(f"Dcache response ignored")
                logger.warning(f" {payload.addr}")
                logger.warning(f" {ldst_coal.inMSHR(payload.addr)}")
                logger.warning(f" {ldst_coal.mshr_addrs}")



class Coalesce():
    cache_line_mask =  '0xFF_FF_FF_80'

    def __init__(self, instr):
        self.instr: Instruction = instr
        self.write = False # Whether instruction is a ld or st
        self.addrs: list[Bits] = [] # initialized with all addr mem addrs
        self.pending_addrs = [] # List of to be issued addrs
        self.finished_idxs = [0 for i in range(32)] # Hot list of completed thread hits
        self.mshr_addrs = [] # List of missed addresses waiting for mshr hit
        self.in_flight_addr = None # None when no in-flight
        self.missed = False #Flag to indicate whether 
        for i in range(32):
            addr = Bits(int=self.instr.rdat1[i].int + self.instr.rdat2[i].int, length=32)
            self.addrs.append(addr)
            if addr & self.cache_line_mask not in self.pending_addrs:
                self.pending_addrs.append(addr & self.cache_line_mask)
        self.instr.wdat = [None for i in range(32)]


    def inRange(self, base_addr: Bits, addr: Bits) -> bool:
        '''
        Returns whether addr can be coalesced with base_addr
        '''
        if base_addr == None or addr == None:
            return False
        base_addr = base_addr & self.cache_line_mask
        addr = addr & self.cache_line_mask
        if addr == base_addr:
            return True
        else:
            return False
    
    def inMSHR(self, addr: Bits) -> bool:
        if len(self.mshr_addrs) == 0:
            return False
    
        addr = addr & self.cache_line_mask
        if addr == self.mshr_addrs[0]:
            return True
        return False

    def genRequestAddr(self) -> int:
        if len(self.pending_addrs) == 0:
            self.logState(logging.WARN)
        self.in_flight_addr = self.pending_addrs.pop(0) & self.cache_line_mask
        coal_addrs = [addr for addr in self.pending_addrs if self.inRange(self.in_flight_addr, addr)]
        return self.in_flight_addr

    def parseHit(self, payload) -> None:
        data_addr = payload.addr
        logger.info(f"Parsing hit for addr {payload.addr}")

        #Sanity check that addr is in-flight or mshr
        if not (self.inRange(self.in_flight_addr, data_addr) or self.inMSHR(data_addr)):
            logger.warning("Err: parseHit called for payload not in-flight or in MSHR")

        if self.write == False:
            for idx, addr in enumerate(self.addrs):
                if self.inRange(data_addr, addr):
                    d_idx = (addr.int - data_addr.int) >> 5
                    self.instr.wdat[idx] = payload.data[d_idx]
                    self.finished_idxs[idx] = 1
                    if self.inMSHR(addr):
                        self.mshr_addrs.pop(0)
                    else:
                        self.in_flight_addr = None
        self.in_flight_addr = None
        

    def parseMiss(self, payload) -> None:
        if self.in_flight_addr != payload.addr:
            logger.warning(f"Err: in-flight-address not same as miss address")
        self.mshr_addrs.append(self.in_flight_addr)
        
        self.in_flight_addr = None
        self.missed = True

    def readyMSHR(self):
        return len(self.pending_addrs) == 0 and self.in_flight_addr == None

    def readyWB(self):
        return all(self.finished_idxs) and len(self.pending_addrs) == 0 and self.in_flight_addr == None
    
    def logState(self, level=logging.INFO):
        logger.log(level, f"num pending: {len(self.pending_addrs)}")
        logger.log(level, f"num mshr   : {len(self.mshr_addrs)}")
        logger.log(level, f"finish idxs: {str(self.finished_idxs)}")
        logger.log(level, f"wdat {self.instr.wdat}")
        logger.log(level, f"wdat size {len(self.instr.wdat)}")
        logger.log(level, f"pending    : {str(self.pending_addrs)}")