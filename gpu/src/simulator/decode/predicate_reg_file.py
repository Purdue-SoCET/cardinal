
from builtins import print
import sys
from pathlib import Path

parent_dir = Path(__file__).resolve().parents[3]

sys.path.append(str(parent_dir))
from simulator.interfaces import ForwardingIF, LatchIF
from simulator.stage import Stage
from simulator.instruction import Instruction
from simulator.mem_types import ICacheEntry, MemRequest, FetchRequest, DecodeType
from simulator.mem.memory import Mem
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque
from datetime import datetime
from bitstring import Bits 

from common.custom_enums_multi import Instr_Type, R_Op, I_Op, F_Op, S_Op, B_Op, U_Op, J_Op, P_Op, H_Op, Op

class PredicateRegFile():
    def __init__(self, num_preds_per_warp: int, num_warps: int):
        self.num_preds_per_warp = num_preds_per_warp # the number of 
        self.num_threads = 32
        self.banks = 1 # used in creation of writeback buffer (signifies number of physical banks in hardware)
        # ^^^ idk if this will ever be more than 1 but just leave this for now

        # 2D structure: warp -> predicate -> [bits per thread]
        self.reg_file = [
            [[[True] * self.num_threads]
              for _ in range(self.num_preds_per_warp)]
            for _ in range(num_warps)
        ]
    
    def read_predicate(self, prf_rd_en: int, prf_rd_wsel: int, prf_rd_psel: int, prf_neg: int):
        "Predicate register file reads by selecting a 1 from 32 warps, 1 from 16 predicates,"
        " and whether it wants the inverted version or not..."

        if (prf_rd_en):
            return self.reg_file[prf_rd_wsel][prf_rd_psel] # no need to select the true/false
        else: 
            return None
    
    def write_predicate(self, prf_wr_en: int, prf_wr_wsel: int, prf_wr_psel: int, prf_wr_data):
        # Warp granularity (prf_wr_data must be a list of 32 bools representing the predicate value for each thread in the warp)
        # the write will autopopulate the negated version in the table)
        print("dest_pred =", prf_wr_psel)
        print("num_preds_per_warp =", self.num_preds_per_warp)
        if (prf_wr_en):
                # Convert int to bit array if needed
            if isinstance(prf_wr_data, int):
                bits = [(prf_wr_data >> i) & 1 == 1 for i in range(self.num_threads)]
            else:
                bits = prf_wr_data  # assume already a list of bools

            # Store one version
            self.reg_file[prf_wr_wsel][prf_wr_psel] = bits

    def write_predicate_thread_gran(self, prf_wr_en: int, prf_wr_wsel: int, prf_wr_psel: int, prf_wr_tsel, prf_wr_data):
        # Thread granularity (prf_wr_data must be a single bool representing the predicate value for a single thread)
        # the write will autopopulate the negated version in the table)
        if (prf_wr_en):
            # Store just one version
            self.reg_file[prf_wr_wsel][prf_wr_psel][prf_wr_tsel] = bool(prf_wr_data.uint)

    def dump(self, file=None):
        """
        Dumps full predicate register file.
        Skips warps that are completely default (all True for positive, all False for neg).
        """

        import sys as _sys
        out = file if file is not None else _sys.stdout

        print(f"\n{'='*80}", file=out)
        print(f"{'PREDICATE REGISTER FILE DUMP':^80}", file=out)
        print(f"{'='*80}", file=out)

        active_warps_found = False

        for w in range(len(self.reg_file)):

            warp_is_default = True

            # Check if warp is default state
            for p in range(self.num_preds_per_warp):
                entry = self.reg_file[w][p]

                # Default = all threads True
                if not all(entry):
                    warp_is_default = False
                    break

            if warp_is_default:
                continue

            active_warps_found = True

            print(f"\n[ Warp {w} ]", file=out)
            print("-" * 80, file=out)

            for p in range(self.num_preds_per_warp):

                entry = self.reg_file[w][p]

                print(f"  P{p:<2}:", file=out)

                for i in range(0, self.num_threads, 8):
                    chunk = entry[i:i+8]
                    formatted = [f"{int(b):>3}" for b in chunk]
                    print(f"    T{i:02d}-T{i+7:02d}: {' '.join(formatted)}", file=out)

                print("", file=out)

        if not active_warps_found:
            print("\n  (Predicate Register File is entirely default)", file=out)

        print(f"{'='*80}\n", file=out)