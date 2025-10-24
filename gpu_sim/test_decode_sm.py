from base_class import StageInterface, PipelineStage, SM
import importlib
import argparse
import logging
import struct
import sys
from dataclasses import dataclass
from typing import Optional
from unicodedata import name


class DecodeStage(PipelineStage):
    def __init__(self, parent_core):
        super().__init__("Decode", parent_core)
        self.flush_flag = False
        self.halt = False

    def process(self, inst):
        if not inst:
            return None

        # Interpret instruction as a 32-bit integer and extract the low 7-bit opcode.
        raw = int(inst.get("raw", 0)) & 0xFFFFFFFF
        opcode_upper = raw & 0x7  # bits 6-3
        opcode_lower = (raw >> 3) & 0xF  # bits 2-0
        opcode_r0_dict = {
            "000": "add",
            "001": "sub",
            "010": "mul",
            "011": "div",
            "100": "and",
            "101": "or",
            "110": "xor",
            "111": "slt",
        }
        opcode_r1_dict = {
            "000": "sltu",
            "001": "addf",
            "010": "subf",
            "011": "mulf",
            "100": "divf",
            "101": "sll",
            "110": "srl",
            "111": "sra",
        }
        opcode_i0_dict = {
            "000": "addi",
            "001": "subi",
            "101": "ori",
            "111": "slti",
        }
        opcode_i1_dict = {
            "000": "sltiu",
            "001": "srli",
            "101": "srai",
        }
        opcode_i2_dict = {
            "000": "lw",
            "001": "st",
            "010": "lb",
            "011": "jalr"
        }

        def sign_extend(value: int, bits: int) -> int:
            sign_bit = 1 << (bits - 1)
            return (value & (sign_bit - 1)) - (value & sign_bit)

        # Field extraction according to the provided ISA layout
        opcode7 = raw & 0x7F
        rd = (raw >> 7) & 0x3F
        rs1 = (raw >> 13) & 0x3F
        # bits [24:19] used either as rs2 (6 bits) or imm field depending on type
        mid6 = (raw >> 19) & 0x3F
        pred = (raw >> 25) & 0x1F
        packet_start = bool((raw >> 30) & 0x1)
        packet_end = bool((raw >> 31) & 0x1)

        high4 = (opcode7 >> 3) & 0xF
        low3 = opcode7 & 0x7

        # Build opcode -> mnemonic map from the provided table (subset implemented)
        opcode_map = {
            # R-type (high4 = 0b0000)
            0b0000000: "add",
            0b0000001: "sub",
            0b0000010: "mul",
            0b0000011: "div",
            0b0000100: "and",
            0b0000101: "or",
            0b0000110: "xor",
            0b0000111: "slt",
            # R-type / FP and shifts (high4 = 0b0001)
            0b0001000: "sltu",  # 0001 000 -> 8
            0b0001001: "addf",
            0b0001010: "subf",
            0b0001011: "mulf",
            0b0001100: "divf",
            0b0001101: "sll",
            0b0001110: "srl",
            0b0001111: "sra",
            # I-type (0010, 0011)
            0b0010000: "addi",
            0b0010001: "subi",
            0b0010101: "ori",
            0b0010111: "slti",
            0b0011000: "sltiu",  # 0011 000 -> 24
            0b0011110: "srli",
            0b0011111: "srai",
            0b0100000: "lw",    # 0100 000 -> 32
            0b0100001: "lh",
            0b0100010: "lb",
            0b0100011: "jalr",
            # F-type (0101)
            0b0101000: "isqrt",
            0b0101001: "sin",
            0b0101010: "cos",
            0b0101011: "itof",
            0b0101100: "ftoi",
            # S-type (0110)
            0b0110000: "sw",
            0b0110001: "sh",
            0b0110010: "sb",
            # B-type (1000)
            0b1000000: "beq",
            0b1000001: "bne",
            0b1000010: "bge",
            0b1000011: "bgeu",
            0b1000100: "blt",
            0b1000101: "bltu",
            # U-type (1010)
            0b1010000: "auipc",
            0b1010001: "lli",
            0b1010010: "lmi",
            0b1010100: "lui",
            # C-type (1011)
            0b1011000: "csrr",
            0b1011001: "csrw",
            # J-type (1100)
            0b1100000: "jal",
            # P-type (1101)
            0b1101000: "jpnz",
            # H-type: halt is all ones (0b1111111 -> 127)
            0b1111111: "halt",
        }

        mnemonic = opcode_map.get(opcode7, "nop")

        # Interpret fields according to determined instruction class (best-effort)
        decoded: dict = {
            "raw": raw,
            "opcode7": opcode7,
            "mnemonic": mnemonic,
            "predication": pred,
            "packet_start": packet_start,
            "packet_end": packet_end,
        }

        # Classify by high4 nibble
        if high4 in (0x0, 0x1):
            # R-type family (register-register)
            decoded.update({"type": "R", "rd": rd, "rs1": rs1, "rs2": mid6})
        elif high4 in (0x2, 0x3, 0x4):
            # I-type family (immediates and loads/jalr)
            imm6 = sign_extend(mid6, 6)
            decoded.update({"type": "I", "rd": rd, "rs1": rs1, "imm": imm6})
        elif high4 == 0x5:
            # F-type / unary ops: rd, rs1
            decoded.update({"type": "F", "rd": rd, "rs1": rs1})
        elif high4 in (0x6, 0x7):
            # S-type family (store / memory write)
            decoded.update({"type": "S", "imm": mid6, "rs1": rs1, "rs2": rd})
        elif high4 == 0x8:
            # B-type (branch): preddest in rd field
            decoded.update({"type": "B", "pred_dest": rd, "rs1": rs1, "rs2": mid6})
        elif high4 == 0xA:
            # U-type: 12-bit immediate occupies bits [24:13]
            imm12 = (raw >> 13) & 0xFFF
            decoded.update({"type": "U", "rd": rd, "imm12": sign_extend(imm12, 12)})
        elif high4 == 0xB:
            # C-type: CSR op
            decoded.update({"type": "C", "rd": rd, "csr": (raw >> 13) & 0x3FF})
        elif high4 == 0xC:
            # J-type: jal
            imm12 = (raw >> 13) & 0xFFF
            decoded.update({"type": "J", "rd": rd, "imm12": sign_extend(imm12, 12)})
        elif high4 == 0xD:
            # P-type: predicated jump
            decoded.update({"type": "P", "rs1": rs1, "rs2": mid6})
        elif opcode7 == 0x7F:
            decoded.update({"type": "H", "mnemonic": "halt"})
        else:
            decoded.update({"type": "UNKNOWN"})

        # Attach the original instruction for reference
        decoded["orig_inst"] = inst

        return {"decoded": True, "decoded_fields": decoded}

    def flush(self):
        """Flush the stage and its interfaces."""
        if self.input_if:
            self.input_if.flush()
        if self.output_if:
            self.output_if.flush()
        self.flush_flag = True

    def debug_state(self):
        return {
            "name": self.name,
            "flush_flag": self.flush_flag,
            "halt": self.halt,
        }
    
class DummyFetch(PipelineStage):
    def __init__(self, parent_core):
        super().__init__("DummyFetch", parent_core)
        self.inst_queue = []

    def load_instructions(self, instructions):
        self.inst_queue.extend(instructions) ## add to whatever queue you have

    def process(self, inst):
        print("PASSTHROUGH: Fetching instruction: {}\n", format(inst))
        return inst

class DummyExec(PipelineStage):
    def __init__(self, parent_core):
        super().__init__("DummyExec", parent_core)
        self.inst_queue = []

    def load_instructions(self, instructions):
        self.inst_queue.extend(instructions) ## add to whatever queue you have

    def process(self, inst):
        print("PASSTHROUGH: Executing instruction: {}\n", format(inst))
        return inst
        return None
    
class SM_Test(SM):
    def __init__(self):
        
        fetch = DummyFetch(self)
        decode = DecodeStage(self)
        execute = DummyExec(self)

        stage_defs = {
            "fetch": fetch,
            "decode": decode,
            "execute": execute
        }
        connections = {
            ("fetch", "decode"),
            ("decode", "execute")
        }
        feedbacks = [] # an empty set for now. assume a linear flow.
        super().__init__(stage_defs=stage_defs, connections=connections)


def make_raw(op7: int, rd: int = 1, rs1: int = 2, mid6: int = 3, pred: int = 0, packet_start: bool = False, packet_end: bool = False) -> int:
    """Construct a 32-bit instruction word according to the DecodeStage layout:
    bits [6:0]   = opcode7
    bits [12:7]  = rd (6)
    bits [18:13] = rs1 (6)
    bits [24:19] = mid6 (6)
    bits [29:25] = pred (5)
    bit  [30]    = packet_start
    bit  [31]    = packet_end
    """
    raw = (
        (int(packet_end) << 31)
        | (int(packet_start) << 30)
        | ((pred & 0x1F) << 25)
        | ((mid6 & 0x3F) << 19)
        | ((rs1 & 0x3F) << 13)
        | ((rd & 0x3F) << 7)
        | (op7 & 0x7F)
    )
    return raw


if __name__ == "__main__":
    sm = SM_Test()
    instructions = [
        {"pc": 0x100, "raw": make_raw(0x00, rd=1, rs1=2, mid6=3)},    # add (R-type)
        {"pc": 0x104, "raw": make_raw(0x10, rd=5, rs1=6, mid6=0)},    # addi (I-type)
        {"pc": 0x108, "raw": make_raw(0x20, rd=2, rs1=3, mid6=4)},    # lw  (I-type / load)
        {"pc": 0x10C, "raw": make_raw(0x30, rd=2, rs1=3, mid6=4)},    # sw  (S-type)
        {"pc": 0x110, "raw": make_raw(0x40, rd=0, rs1=1, mid6=2, pred=1, packet_start=True)},  # beq (B-type) with packet start
        {"pc": 0x114, "raw": make_raw(0x7F, rd=0, rs1=0, mid6=0)},    # halt (H-type)
    ]

    for inst in instructions:
        iface = sm.get_interface("if_fetch_decode")
        iface.send(inst)
        sm.cycle()
        sm.print_pipeline_state()