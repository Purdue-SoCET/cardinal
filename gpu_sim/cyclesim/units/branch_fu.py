from base import ForwardingIF, LatchIF, Stage, Instruction, ICacheEntry, MemRequest, FetchRequest, DecodeType
from Memory import Mem
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque
from datetime import datetime
from isa_packets import ISA_PACKETS
from bitstring import Bits 
global_cycle = 0


class BranchFU:
    def __init__(self, instructions: Instruction, prf_rd_data, op_1, op_2):
        self.warp_id = instructions.warp
        self.decode_mapping_table = {
            0: "beq",
            1: "bne",
            2: "bge",
            3: "bgeu",
            4: "blt",
            5: "bltu",
        }
        self.opcode = self.decode_mapping_table[instructions.opcode]
        self.prf_rd_data = prf_rd_data
        self.op1 = op_1
        self.op2 = op_2
        self.num_threads = len(op_1)
        self.prf_wr_data = None

    def to_signed(self, val, bits=32):
        if val & (1 << (bits - 1)):
            val -= 1 << bits
        return val

    def alu_decoder(self):
        if self.opcode == "beq":
            results = [self.op1[i] == self.op2[i] for i in range(self.num_threads)]
        elif self.opcode == "bne":
            results = [self.op1[i] != self.op2[i] for i in range(self.num_threads)]
        elif self.opcode == "bge":
            results = [self.to_signed(self.op1[i]) >= self.to_signed(self.op2[i]) for i in range(self.num_threads)]
        elif self.opcode == "bgeu":
            results = [self.op1[i] >= self.op2[i] for i in range(self.num_threads)]
        elif self.opcode == "blt":
            results = [self.to_signed(self.op1[i]) < self.to_signed(self.op2[i]) for i in range(self.num_threads)]
        elif self.opcode == "bltu":
            results = [self.op1[i] < self.op2[i] for i in range(self.num_threads)]
        else:
            raise ValueError(f"Unknown opcode {self.opcode}")
        return results

    def update_pred(self):
        tnt = self.alu_decoder()
        self.prf_wr_data = [
            self.prf_rd_data[i] and tnt[i] for i in range(self.num_threads)
        ]
        return self.prf_wr_data
 
 
