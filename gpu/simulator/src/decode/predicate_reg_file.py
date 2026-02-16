
import sys
from pathlib import Path

parent_dir = Path(__file__).resolve().parents[3]

sys.path.append(str(parent_dir))
from simulator.base_class import ForwardingIF, LatchIF, Stage, Instruction, ICacheEntry, MemRequest, FetchRequest, DecodeType
from simulator.src.mem.Memory import Mem
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque
from datetime import datetime
from bitstring import Bits 

from common.custom_enums_multi import Instr_Type, R_Op, I_Op, F_Op, S_Op, B_Op, U_Op, J_Op, P_Op, H_Op
from common.custom_enums import Op

class PredicateRegFile():
    def __init__(self, num_preds_per_warp: int, num_warps: int):
        num_cols = num_preds_per_warp *2 # the number of 
        self.num_threads = 32

        # 2D structure: warp -> predicate -> [bits per thread]
        self.reg_file = [
            [[[False] * self.num_threads, [False] * self.num_threads]
              for _ in range(num_cols)]
            for _ in range(num_warps)
        ]
    
    def read_predicate(self, prf_rd_en: int, prf_rd_wsel: int, prf_rd_psel: int, prf_neg: int):
        "Predicate register file reads by selecting a 1 from 32 warps, 1 from 16 predicates,"
        " and whether it wants the inverted version or not..."

        if (prf_rd_en):
            print("[PRF] Reading PRF: ", prf_rd_wsel, prf_rd_psel, prf_neg)
            print(f"[PRF] Got: {self.reg_file[prf_rd_wsel][prf_rd_psel][prf_neg]}")
            return self.reg_file[prf_rd_wsel][prf_rd_psel][prf_neg]
        else: 
            return None
    
    def write_predicate(self, prf_wr_en: int, prf_wr_wsel: int, prf_wr_psel: int, prf_wr_data):
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

