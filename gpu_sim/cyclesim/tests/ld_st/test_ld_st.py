from logging import handlers
from re import A
import unittest
import logging
import sys

# from gpu_sim.cyclesim.src.mem import dcache
from gpu_sim.cyclesim.src.mem.base import ForwardingIF, LatchIF, dCacheRequest, dMemResponse
from gpu_sim.cyclesim.src.mem.ld_st import Ldst_Fu
from gpu_sim.cyclesim.latch_forward_stage import Instruction, LatchIF, ForwardingIF
from bitstring import Bits

'''
Unittests are intended to be ran from the top level cardinal/ directory with command
python3 -m unittest discover -s gpu_sim/cyclesim/tests/ld_st
    *Path subject to change as merging happens
Can use -k flag on this to specify a single unittest
'''

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

class TestLoadStoreUnit(unittest.TestCase):
    def genLoad(self,
                pc: Bits,
                rd=Bits(int=0, length=32),
                rdat1 = [Bits(int=0, length=32) for i in range(32)],
                rdat2 =  [Bits(int=0, length=32) for i in range(32)],
                wdat = [Bits(int=0, length=32) for i in range(32)],
                pred = [Bits(uint=1, length=1) for i in range(32)]
            ) -> Instruction:
        instr = Instruction(pc=pc,
                            intended_FU="ldst",
                            warp_id=0,
                            warp_group_id=0,
                            rs1=Bits(int=0,length=32),
                            rs2=Bits(int=0,length=32),
                            imm=Bits(int=0,length=32),
                            rd=rd,
                            wdat=wdat,
                            opcode=Bits(bin='0b0100000'),
                            rdat1 = rdat1,
                            rdat2 = rdat2,
                            predicate=pred
                            )
        return instr
    
    def genStore(self,
                pc: Bits,
                rd=Bits(int=0, length=32),
                rdat1 = [Bits(int=0, length=32) for i in range(32)],
                rdat2 =  [Bits(int=0, length=32) for i in range(32)],
                wdat = [Bits(int=0, length=32) for i in range(32)],
                pred = [Bits(uint=1, length=1) for i in range(32)]
            ) -> Instruction:
        instr = Instruction(pc=pc,
                            intended_FU="ldst",
                            warp_id=0,
                            warp_group_id=0,
                            rs1=Bits(int=0,length=32),
                            rs2=Bits(int=0,length=32),
                            imm=Bits(int=0,length=32),
                            rd=rd,
                            wdat=wdat,
                            opcode=Bits(bin='0b0110000'),
                            rdat1 = rdat1,
                            rdat2 = rdat2,
                            predicate=pred
                            )
        return instr
    
    def genHit(self, hex_data = None):
        dcache_req: dCacheRequest = self.dcache_if.pop()

        if hex_data == None:
            hex_data = hex(dcache_req.addr_val)

        logging.info(f"Servicing hit for addr: {hex(dcache_req.addr_val)} with data: {hex_data}")
        assert type(dcache_req) == dCacheRequest
        self.dcache_fwd.push(
            dMemResponse(
                type = 'HIT_COMPLETE',
                hit = True,
                req = dcache_req,
                address = dcache_req.addr_val,
                data = int(hex_data, 16)
            )
        )

    def mshrHit(self, req):
        logging.info(f"Servicing MSHR hit for addr: {req.addr_val}")

        self.dcache_fwd.push(
            dMemResponse(
                type = 'MISS_COMPLETE',
                req = req,
                address = req.addr_val,
                replay = True
            )
        )
    
    def genMiss(self):
        dcache_req: dCacheRequest = self.dcache_if.pop()
        logging.info(f"Servicing miss for addr: {hex(dcache_req.addr_val)}")

        assert type(dcache_req) == dCacheRequest

        self.dcache_fwd.push(
            dMemResponse(
                type = 'MISS_ACCEPTED',
                miss = True,
                uuid = 0,
                req = dcache_req,
                address = dcache_req.addr_val,
                is_secondary = False
            )
        )
    
    def tickLdSt(self):
        instr = self.ldst_fu.tick(self.issue_if)
        if instr:
            self.wb_if.push(instr)
        
        


    @classmethod
    def setUp(cls) -> None:
        cls.ldst_fu = Ldst_Fu()

        cls.dcache_if = LatchIF()
        cls.dcache_fwd = ForwardingIF()
        cls.dcache_if.forward_if = cls.dcache_fwd

        cls.issue_if = LatchIF()
        cls.issue_if_fwd = ForwardingIF()
        cls.issue_if.forward_if = cls.issue_if_fwd

        cls.wb_if = LatchIF()

        cls.sched_if = ForwardingIF()
        
        cls.ldst_fu.connect_interfaces(cls.dcache_if, cls.wb_if, cls.sched_if)
        cls.dcache_fwd.push(None)

    def test_singleLoadHit(self):
        instr = self.genLoad(pc=0, rd=0, rdat1 = [Bits(int=i, length=32) for i in range(0, 0x400, 32)])
        self.issue_if.push(instr)
        self.tickLdSt()

        while not self.wb_if.valid:
            if self.dcache_if.valid:
                self.genHit()
            else:
                self.dcache_fwd.push(None)
            
            self.tickLdSt()
        self.dcache_if.valid = False

        instr: Instruction = self.wb_if.pop()
        logging.info(f"HIII {type(instr)}")
        assert(type(instr) == Instruction) 
        # logger.info("test_singleLoadHit instr wdat:")
        for i, d in enumerate(instr.wdat):
            # logger.info(f"  {i}, {d}")
            assert(d == Bits(int=32*i, length=32))
        
        logger.info("test_singleLoadHit COMPLETE\n")

    # @unittest.skip("Skipping while singleLoadHit isn't working")
    def test_singleLoadMiss(self):
        mshr_reqs = []
        hit_addrs = []
        instr = self.genLoad(pc=0, rd=0, rdat1 = [Bits(int=i, length=32) for i in range(0, 0x400, 32)])
        self.issue_if.push(instr)
        self.tickLdSt()
        

        while not self.wb_if.valid:
            if self.dcache_if.valid:
                req = self.dcache_if.payload
                if req.addr_val not in hit_addrs:
                    self.genMiss()
                    mshr_reqs.append(req)
                else:
                    self.genHit('0xAA')
            elif len(mshr_reqs) > 0:
                req = mshr_reqs.pop(0)
                self.mshrHit(req)
                hit_addrs.append(req.addr_val)
            else:
                self.dcache_fwd.push(None)
            self.tickLdSt()
        
        assert(self.wb_if.valid)
        
        # logger.info("test_singleLoadHit instr wdat:")
        for i, d in enumerate(instr.wdat):
            # logger.info(f"  {i}, {d}, {Bits(hex='0xAA', length=32)}")
            assert(d == Bits(hex='0x000000AA', length=32))
        
        logger.info("test_singleLoadMiss COMPLETE\n")

    def test_singleStoreMiss(self):
        instr = self.genStore(pc=0, rd=0, rdat1 = [Bits(int=i, length=32) for i in range(0, 0x400, 32)])
        self.issue_if.push(instr)
        self.tickLdSt()

        while not self.wb_if.valid:
            if self.dcache_if.valid:
                self.genMiss()
            else:
                self.dcache_fwd.push(None)
            self.tickLdSt()
        
        assert(self.wb_if.valid)
        logger.info("test_singleStoreMiss COMPLETE\n")
    
    # @unittest.skip("Skipping while singleLoadMiss isn't working")
    def test_singlePredHit(self):
        pred = [Bits(bin='0b0') for i in range(32)]
        pred[0] = Bits(bin='0b1')
        instr = self.genLoad(pc=0, rd=0, rdat1 = [Bits(int=0, length=32) for i in range(32)], pred=pred)
        self.issue_if.push(instr)
        self.tickLdSt()

        hit_count = 0
        while not self.wb_if.valid:
            if self.dcache_if.valid:
                self.genHit('0xAA')
                hit_count += 1
            else:
                self.dcache_fwd.push(None)
            self.tickLdSt()
        
        assert(hit_count == 1)
        assert(instr.wdat[0] == Bits(hex='0x000000AA'))
        logger.info("test_singlePredHit COMPLETE\n")

    def test_backpressure(self):
        instrs = []
        finished_instrs = []
        for i in range(10):
            instrs.append(self.genLoad(pc=Bits(int=i, length=32), rd=0, rdat1 = [Bits(int=i%3, length=32) for i in range(32)]))
        
        wb_count = 0
        while wb_count<10:
            if not self.issue_if.forward_if.wait and len(instrs) > 0:
                self.issue_if.push(instrs.pop())
            elif len(instrs) > 0:
                logging.info(f"Instruction stalled")
            if self.dcache_if.valid:
                self.genHit()
            else:
                self.dcache_fwd.push(None)
            
            if self.wb_if.valid:
                wb_count += 1
                finished_instrs.append(self.wb_if.pop())
                logging.info(f"Finished instr {finished_instrs[-1].pc.hex}")
            self.tickLdSt()
        
        for instr in finished_instrs:
            logging.info(f"{instr.pc.hex}")


if __name__ == '__main__':
    unittest.main()