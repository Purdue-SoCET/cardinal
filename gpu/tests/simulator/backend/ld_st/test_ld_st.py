from logging import handlers
import unittest
import logging
import sys

from src.mem import dcache
from latch_forward_stage import ForwardingIF, LatchIF
from src.mem.ld_st import Ldst_Fu
from src.mem.ld_st_payload import Dcache_Ldst_Payload, Ldst_Dcache_Payload
from latch_forward_stage import Instruction
from bitstring import Bits

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

class TestLoadStoreUnit(unittest.TestCase):
    zero_vec = [Bits(int=0, length=32) for i in range(32)]
    def genLoad(self, pc: int, rd=0, rdat1 = [Bits(int=0, length=32) for i in range(32)], rdat2 =  [Bits(int=0, length=32) for i in range(32)], wdat = [None for i in range(32)]) -> Instruction:
        instr = Instruction(pc=pc, intended_FU="ldst", warp_id=0, warp_group_id=0, rs1=0, rs2=0, rd=rd, wdat=wdat, opcode=Bits(bin='0b0100'))
        instr.pc = pc
        instr.intended_FU = "ldst_fu"
        instr.warp_id = 0
        instr.warp_group_id = 0

        instr.rs1 = 0
        instr.rs2 = 0
        instr.rd = rd
        instr.opcode = Bits(bin="0b0100", length=4)

        instr.rdat1 = rdat1
        instr.rdat2 = rdat2
        instr.wdat = wdat 
        return instr
    
    def genStore(self, pc: int, rd=0, rdat1 = [Bits(int=0, length=32) for i in range(32)], rdat2 =  [Bits(int=0, length=32) for i in range(32)]) -> Instruction:
        instr = Instruction(pc=pc, intended_FU="ldst", warp_id=0, warp_group_id=0, rs1=0, rs2=0, rd=rd, opcode=Bits(bin='0b0100'))
        instr.pc = pc
        instr.intended_FU = "ldst_fu"
        instr.warp_id = 0
        instr.warp_group_id = 0

        instr.rs1 = 0
        instr.rs2 = 0
        instr.rd = rd
        instr.opcode = Bits(bin="0b0100", length=4)

        instr.rdat1 = rdat1
        instr.rdat2 = rdat2

        return instr
    
    def genHit(self, hex_data:str):
        dcache_req: Ldst_Dcache_Payload = self.dcache_if.pop()
        logging.info(f"Servicing hit for addr: {dcache_req.addr.hex} for pc: {dcache_req.pc}")
        assert type(dcache_req) == Ldst_Dcache_Payload
        self.dcache_fwd.push(
            Dcache_Ldst_Payload(
                data=[Bits(hex=hex_data, length=32) for i in range(32)],
                pc=dcache_req.pc,
                hit=True,
                miss=False,
                addr=dcache_req.addr
            )
        )

    def mshrHit(self, mshr_data: tuple[int, Bits], hex_data:str):
        pc = mshr_data[0]
        addr = mshr_data[1]
        logging.info(f"Servicing MSHR hit for addr: {addr} for pc {pc}")

        self.dcache_fwd.push(
            Dcache_Ldst_Payload(
                data=[Bits(hex=hex_data, length=32) for i in range(32)],
                pc=pc,
                hit=True,
                miss=False,
                addr=addr
            )
        )

    def intToHex(self, num) -> str:
        return Bits(auto=num, length=32).hex()
    
    def genMiss(self) -> tuple[int, Bits]:
        dcache_req: Ldst_Dcache_Payload = self.dcache_if.pop()
        logging.info(f"Servicing miss for addr: {dcache_req.addr} for pc {dcache_req.pc}")

        if type(dcache_req) != Ldst_Dcache_Payload:
            logger.warning("Err in genMiss")
            logger.warning(f" {type(dcache_req)}")
            logger.warning(f" {dcache_req}")
            logger.warning(f" {self.dcache_if.valid}")

        assert type(dcache_req) == Ldst_Dcache_Payload
        self.dcache_fwd.push(
            Dcache_Ldst_Payload(
                data=None,
                pc=dcache_req.pc,
                hit=False,
                miss=True,
                addr=dcache_req.addr
            )
        )
        return (dcache_req.pc, dcache_req.addr)
        


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
        
        cls.ldst_fu.connect_interfaces(cls.dcache_if, cls.issue_if, cls.wb_if, cls.sched_if)
        cls.dcache_fwd.push(None)

    @unittest.skip("Skipping while singleLoadMiss isn't working")
    def test_singleLoadHit(self):
        instr = self.genLoad(pc=0, rd=0, rdat1 = [Bits(int=i, length=32) for i in range(0, 0x400, 32)])
        self.issue_if.push(instr)
        self.ldst_fu.tick()

        while not self.wb_if.valid:
            if self.dcache_if.valid:
                self.genHit('0xAA')
            else:
                self.dcache_fwd.push(None)
            self.ldst_fu.tick()
        self.dcache_if.valid = False

        instr: Instruction = self.wb_if.pop()
        assert(type(instr) == Instruction)
        for i, d in enumerate(instr.wdat):
            assert(d == Bits(hex='0xAA', length=32))

    # @unittest.skip("Skipping while singleLoadHit isn't working")
    def test_singleLoadMiss(self):
        mshr_addrs = []
        instr = self.genLoad(pc=0, rd=0, rdat1 = [Bits(int=i, length=32) for i in range(0, 0x400, 32)])
        self.issue_if.push(instr)
        self.ldst_fu.tick()
        
        miss_count = 0
        while miss_count < 8:
            if self.dcache_if.valid:
                mshr_addrs.append(self.genMiss()) # [tuple(int, int)]
                miss_count += 1
            else:
                self.dcache_fwd.push(None)
            self.ldst_fu.tick()
        
        while len(mshr_addrs) > 0:
            mshr_addr = mshr_addrs.pop(0)
            self.mshrHit(mshr_addr, '0xAA')
            self.ldst_fu.tick()
        
        self.dcache_fwd.push(None)
        self.ldst_fu.tick()
        
        assert(self.wb_if.valid)
        
        for i, d in enumerate(instr.wdat):
            assert(d == Bits(hex='0xAA', length=32))
        



if __name__ == '__main__':
    unittest.main()