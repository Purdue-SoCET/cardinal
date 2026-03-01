
import sys
from pathlib import Path

parent_dir = Path(__file__).resolve().parents[3]

sys.path.append(str(parent_dir))
from simulator.latch_forward_stage import ForwardingIF, LatchIF, Stage, Instruction, ICacheEntry, MemRequest, FetchRequest, DecodeType
from simulator.mem.Memory import Mem
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque
from datetime import datetime
from bitstring import Bits 

from common.custom_enums_multi import Instr_Type, R_Op, I_Op, F_Op, S_Op, B_Op, U_Op, J_Op, P_Op, H_Op
from common.custom_enums import Op

class PredicateRegFile():
    def __init__(self, num_preds_per_warp: int, num_warps: int):
        self.num_preds_per_warp = num_preds_per_warp # the number of 
        self.num_threads = 32
        self.banks = 1 # used in creation of writeback buffer (signifies number of physical banks in hardware)
        # ^^^ idk if this will ever be more than 1 but just leave this for now

        # 2D structure: warp -> predicate -> [bits per thread]
        self.reg_file = [
            [[[False] * self.num_threads, [True] * self.num_threads]
              for _ in range(self.num_preds_per_warp)]
            for _ in range(num_warps)
        ]
    
    def read_predicate(self, prf_rd_en: int, prf_rd_wsel: int, prf_rd_psel: int, prf_neg: int):
        "Predicate register file reads by selecting a 1 from 32 warps, 1 from 16 predicates,"
        " and whether it wants the inverted version or not..."

        if (prf_rd_en):
            # print("[PRF] Reading PRF: ", prf_rd_wsel, prf_rd_psel, prf_neg)
            # print(f"[PRF] Got: {self.reg_file[prf_rd_wsel][prf_rd_psel][prf_neg]}")
            return self.reg_file[prf_rd_wsel][prf_rd_psel][prf_neg]
        else: 
            return None
    
    def write_predicate(self, prf_wr_en: int, prf_wr_wsel: int, prf_wr_psel: int, prf_wr_data):
        # Warp granularity (prf_wr_data must be a list of 32 bools representing the predicate value for each thread in the warp)
        # the write will autopopulate the negated version in the table)
        if (prf_wr_en):
                # Convert int to bit array if needed
            if isinstance(prf_wr_data, int):
                bits = [(prf_wr_data >> i) & 1 == 1 for i in range(self.num_threads)]
            else:
                bits = prf_wr_data  # assume already a list of bools

            # Store positive version
            self.reg_file[prf_wr_wsel][prf_wr_psel][0] = bits
            # Store negated version
            self.reg_file[prf_wr_wsel][prf_wr_psel][1] = [not b for b in bits]

    def write_predicate_thread_gran(self, prf_wr_en: int, prf_wr_wsel: int, prf_wr_psel: int, prf_wr_tsel, prf_wr_data):
        # Thread granularity (prf_wr_data must be a single bool representing the predicate value for a single thread)
        # the write will autopopulate the negated version in the table)
        if (prf_wr_en):
                # Convert int to bit array if needed
            if isinstance(prf_wr_data, int):
                bits = [(prf_wr_data >> i) & 1 == 1 for i in range(self.num_threads)]
            else:
                bits = prf_wr_data  # assume already a list of bools

            # Store positive version
            self.reg_file[prf_wr_wsel][prf_wr_psel][0][prf_wr_tsel] = bits[prf_wr_tsel]
            # Store negated version
            self.reg_file[prf_wr_wsel][prf_wr_psel][1][prf_wr_tsel] = not bits[prf_wr_tsel]

