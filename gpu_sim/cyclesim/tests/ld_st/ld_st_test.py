"""Unit test bench: This testbench sends a memory request to every bank in the cache. Initially the cache is empty and
every memory request misses. It fetches from main memory that has been prepopulated with 0x01010101 at every address.
Every missed request has a miss penalty of 200 cycles.
"""

import sys
from pathlib import Path

# 1) Add the directory that contains `gpu_sim/` to sys.path
# File: /home/.../gpu/gpu_sim/cyclesim/tests/dcache/readFromAllBanks.py
# parents:
#   0 -> dcache
#   1 -> tests
#   2 -> cyclesim
#   3 -> gpu_sim
#   4 -> gpu   <-- this directory contains the `gpu_sim` package
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from collections import deque

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