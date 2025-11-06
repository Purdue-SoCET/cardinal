

from email.mime import base
import enum


class ldst_fu:
    def __init__(self, name, mshr_size, ldst_q_size):
        self.name = name

        self.mshr = [None for i in range(mshr_size)]
        self.mshr_size = mshr_size

        self.ldst_q: list[Coalesce] = []
        self.ldst_q_size = ldst_q_size

        self.dcache_if = None
        self.issue_if = None
        self.wb_if = None

        self.wb_buffer = [] #completed dcache access buffer

        self.outstanding = False #Outstanding dcache request addr and uid

    def connect_interfaces(self, dcache_if: "StageInterface", issue_if: "StageInterface", wb_if: "StageInterface"):
        self.dcache_if = dcache_if
        self.issue_if = issue_if
        self.wb_if = wb_if

    def tick(self, instr):
        if len(self.ldst_q) + 1 < self.ldst_q_size:
            self.ldst_q.append(Coalesce(instr))
        
        if len(self.ldst_q) == self.ldst_q_size:
            self.issue_if.push({"full": 1}) # backpressure
        
        if self.outstanding == False:
            coalesce: Coalesce = self.ldst_q[0]
            addr = coalesce.genRequestAddr()
            mode = coalesce.write
            uid = 0
        else:
            if dcache_if.hit:
                if dcache_if.data.uid == 1:
                    

                self.outstanding = False
        

class Coalesce():
    cache_line_mask = 0xFF_FF_FF_FF_FF_FF_FF_00
    cache_fetch_step = 0x4

    def __init__(self, instr):
        self.instr = instr
        self.write = True # Whether instruction is a ld or st
        self.addrs = [] # initialized with all addr mem addrs
        self.data = []
        self.pending_addrs = []
        self.in_flight_idx = [0 for i in range(32)]
        self.in_flight_addr = 0

    def inRange(self, base_addr, addr):
        '''
        Returns whether addr can be coalesced with base_addr
        '''
        base_addr = base_addr & 0xFF_FF_FF_FF_FF_FF_FF_00
        addr = addr & 0xFF_FF_FF_FF_FF_FF_FF_00
        pass

    def genRequestAddr(self) -> int:
        self.in_flight_addr = self.pending_addrs[0] & coalesce.cache_line_mask
        coal_addrs = [addr for addr in self.pending_addrs if self.inRange(self.in_flight_addr, addr)]
        for idx, addr in self.addrs:
            if addr in coal_addrs:
                self.in_flight_idx[idx] = 1
        return self.in_flight_addr

    def parseHit(self, data):
        if len(data) != 32:
            print("Err: data is not of right size")
            print(data)
        data_addr = self.in_flight_addr
        for i, d in enumerate(data):
            if self.in_flight_idx[i]:
                self.data[i] = d
            data_addr += coalesce.cache_fetch_step
        
        self.in_flight_idx = [0 for i in range(32)]
    
    def readyWB(self):
        return len(self.pending_addrs) == 0 and not any(self.in_flight_idx)
