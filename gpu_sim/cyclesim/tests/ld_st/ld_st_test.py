from ast import For
from gpu_sim.cyclesim.latch_forward_stage import ForwardingIF, LatchIF
from gpu_sim.cyclesim.src.mem.ld_st import Ldst_Fu
import unittest 

class TestLoadStoreUnit(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.ldst_fu = Ldst_Fu()

        cls.dcache_if = LatchIF()
        cls.dcache_if_fwd = ForwardingIF()
        cls.dcache_if.forward_if = cls.dcache_if_fwd

        cls.issue_if = LatchIF()
        cls.issue_if_fwd = ForwardingIF()
        cls.issue_if.forward_if = cls.issue_if_fwd

        cls.wb_if = ForwardingIF()
        
        cls.ldst_fu.connect_interfaces(cls.dcache_if, cls.issue_if, cls.wb_if)
    
    def singleLoadHit(self):
        pass