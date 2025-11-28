from typing import Optional
from gpu_sim.cyclesim.src.mem import dcache
from latch_forward_stage import Instruction, ForwardingIF, LatchIF


class Ldst_Fu:
    def __init__(self, mshr_size=4, ldst_q_size=4):

        self.mshr: list[Coalesce] = [None for i in range(mshr_size)]
        self.mshr_size = mshr_size

        self.ldst_q: list[Coalesce] = []
        self.ldst_q_size: int = ldst_q_size

        self.dcache_if: Optional[LatchIF] = None
        self.issue_if: Optional[LatchIF] = None
        self.wb_if: Optional[ForwardingIF] = None

        self.wb_buffer = [] #completed dcache access buffer

        self.outstanding = False #Outstanding dcache request addr and uid

<<<<<<< HEAD
    def connect_interfaces(self, dcache_if: "StageInterface", issue_if: "StageInterface", wb_if: "StageInterface"):
=======
    def connect_interfaces(self, dcache_if: LatchIF, issue_if: LatchIF, wb_if: ForwardingIF):
>>>>>>> 53dd9cab02d41caf35c2c5c2540a51116b6f48e5
        self.dcache_if = dcache_if
        self.issue_if = issue_if
        self.wb_if = wb_if

<<<<<<< HEAD
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
=======
    def tick(self):

        #populate ldst_q if not full
        if len(self.ldst_q) + 1 < self.ldst_q_size:
            instr = self.issue_if.pop()
            if instr != None:
                self.ldst_q.append(Coalesce(instr))

        #apply backpressure if full
        if len(self.ldst_q) == self.ldst_q_size:
            self.issue_if.forward_if.set_wait(True)
        else:
            self.issue_if.forward_if.set_wait(False)

        #Push cache access if no outstanding
        if self.outstanding == False and self.dcache_if.ready_for_push():
            coal: Coalesce = self.ldst_q[0]
            addr = coal.genRequestAddr()
            mode = coal.write
            self.outstanding = True

            self.dcache_if.push(
                {
                    "instr":coal.instr
                    "addr": addr,
                    "mode": mode
                }
            )
        elif self.dcache_if.forward_if.payload["hit"] == True:
            payload = self.dcache_if.forward_if.pop()
            self.outstanding = False
            coal: Coalesce = self.ldst_q[0]
            coal.parseHit(payload)

        elif self.dcache_if.forward_if.payload["miss"] == True:
            payload = self.dcache_if.forward_if.pop()
            if len(self.wb_buffer) != 0:
                self.wb_buffer[0].parseHit(payload)
            else:
                self.ldst_q[0].parseHit(payload)
        

class Coalesce():
    cache_line_mask = 0xFF_FF_FF_FF_FF_FF_FC_00
>>>>>>> 53dd9cab02d41caf35c2c5c2540a51116b6f48e5
    cache_fetch_step = 0x4

    def __init__(self, instr):
        self.instr = instr
        self.write = True # Whether instruction is a ld or st
        self.addrs = [] # initialized with all addr mem addrs
        self.data = []
        self.pending_addrs = []
<<<<<<< HEAD
        self.in_flight_idx = [0 for i in range(32)]
=======
        self.finished_idxs = [0 for i in range(32)]
        self.mshr_addrs = []
>>>>>>> 53dd9cab02d41caf35c2c5c2540a51116b6f48e5
        self.in_flight_addr = 0

    def inRange(self, base_addr, addr):
        '''
        Returns whether addr can be coalesced with base_addr
        '''
        base_addr = base_addr & 0xFF_FF_FF_FF_FF_FF_FF_00
        addr = addr & 0xFF_FF_FF_FF_FF_FF_FF_00
        pass

    def genRequestAddr(self) -> int:
<<<<<<< HEAD
        self.in_flight_addr = self.pending_addrs[0] & coalesce.cache_line_mask
=======
        self.in_flight_addr = self.pending_addrs[0] & Coalesce.cache_line_mask
>>>>>>> 53dd9cab02d41caf35c2c5c2540a51116b6f48e5
        coal_addrs = [addr for addr in self.pending_addrs if self.inRange(self.in_flight_addr, addr)]
        for idx, addr in self.addrs:
            if addr in coal_addrs:
                self.in_flight_idx[idx] = 1
        return self.in_flight_addr

    def parseHit(self, data):
<<<<<<< HEAD
        if len(data) != 32:
            print("Err: data is not of right size")
            print(data)
=======
>>>>>>> 53dd9cab02d41caf35c2c5c2540a51116b6f48e5
        data_addr = self.in_flight_addr
        for i, d in enumerate(data):
            if self.in_flight_idx[i]:
                self.data[i] = d
<<<<<<< HEAD
            data_addr += coalesce.cache_fetch_step
        
        self.in_flight_idx = [0 for i in range(32)]
    
    def readyWB(self):
        return len(self.pending_addrs) == 0 and not any(self.in_flight_idx)
=======
            data_addr += Coalesce.cache_fetch_step
        self.in_flight_idx = [0 for i in range(32)]
    
    def readyWB(self):
        return all(self.finished_idxs)
>>>>>>> 53dd9cab02d41caf35c2c5c2540a51116b6f48e5
