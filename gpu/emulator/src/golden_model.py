#!/usr/bin/env python3
"""Golden (reference) emulator for generating expected memory dumps from assembly.

This implements Option A: parse assembly into a small IR and execute the IR directly.

Directly executes by parsing the assembly into a small IR and interpreting it. This is more work to implement than (emit a binary and run on an existing RISC-V emulator), but it allows us to support the full assembly syntax used in the repo's test files without needing to reimplement assembler features like labels, org directives, or the pseudo-lli opcode.

This script is intentionally single-threaded (one T_ID) to bootstrap correctness.

Output dump format:
    One non-zero 32-bit word per line:
        0xAAAAAAAA 0xWWWWWWWW

"""

from __future__ import annotations

import argparse
import math
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


U32_MASK = 0xFFFF_FFFF


# Global Memory Map (Teal Card / project convention)
# Note: end addresses in the table are word-aligned; for byte-addressing, the end byte is +3.
MMIO_START = 0x0000_0000
MMIO_END = 0x0000_0023  # 36B: 0x00..0x23

INSTR_START = 0x0000_0024
INSTR_END = 0x000F_FFFF

ARGS_START = 0x0010_0000
ARGS_END = 0x00FF_FFFF

HEAP_START = 0x1000_0000 # this is where the mem dump should start. If you try to store in another memory space, it will be silently ignored.
HEAP_END = 0xF0FF_FFFF

STACK_START = 0xF100_0000
STACK_END = 0xFFFF_FFFF


class MemoryAccessError(RuntimeError):
    pass


def _in_range(addr: int, start: int, end: int) -> bool:
    return start <= addr <= end


def _classify_range(addr: int, size: int) -> str:
    """Return the memory space name for a byte access, or raise if unmapped."""
    a0 = u32(addr)
    a1 = u32(addr + size - 1)
    # Require access to stay within one space.
    for name, lo, hi in (
        ("mmio", MMIO_START, MMIO_END),
        ("instr", INSTR_START, INSTR_END),
        ("args", ARGS_START, ARGS_END),
        ("heap", HEAP_START, HEAP_END),
        ("stack", STACK_START, STACK_END),
    ):
        if _in_range(a0, lo, hi) and _in_range(a1, lo, hi):
            return name
    raise MemoryAccessError(f"Unmapped memory access: addr={a0:#010x} size={size}")


def u32(x: int) -> int:
    return int(x) & U32_MASK


def sign_extend(value: int, bits: int) -> int:
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)


def f32_from_u32(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", u32(bits)))[0]


def u32_from_f32(value: float) -> int:
    # Force IEEE754 float32 rounding
    return struct.unpack("<I", struct.pack("<f", float(value)))[0]


def write_dump(
    path: str,
    mem_bytes: Dict[int, int],
    dump_ranges: Optional[List[Tuple[int, int]]] = None,
    *,
    written_words: Optional[Set[int]] = None,
    dump_stored_zeros: bool = False,
) -> None:
    """Write canonical dump from byte-addressed memory.

    Emits one word per line.

    By default, skips all-zero words to keep dumps small.
    If dump_stored_zeros=True, then an all-zero word is emitted if its address
    was written by a store during execution (tracked via written_words).
    """
    bases = {addr & ~0x3 for addr in mem_bytes.keys()}
    if dump_stored_zeros and written_words is not None:
        bases |= set(written_words)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for base in sorted(bases):
            if dump_ranges is not None:
                in_any = any(lo <= base <= hi and lo <= (base + 3) <= hi for (lo, hi) in dump_ranges)
                if not in_any:
                    continue
            b0 = mem_bytes.get(base + 0, 0) & 0xFF
            b1 = mem_bytes.get(base + 1, 0) & 0xFF
            b2 = mem_bytes.get(base + 2, 0) & 0xFF
            b3 = mem_bytes.get(base + 3, 0) & 0xFF
            if (b0 | b1 | b2 | b3) == 0:
                if not (dump_stored_zeros and written_words is not None and base in written_words):
                    continue
            word = b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)
            f.write(f"{base:#010x} {word & U32_MASK:#010x}\n")


@dataclass(frozen=True)
class IRInstr:
    addr: int
    op: str
    args: Tuple[object, ...]
    pred: int = 0
    start: int = 0
    end: int = 1


def _strip_comment(line: str) -> str:
    for marker in ("#", ";"):
        i = line.find(marker)
        if i != -1:
            line = line[:i]
    return line.strip()


def _parse_int(token: str) -> int:
    token = token.strip()
    if token.lower().startswith("0x"):
        return int(token, 16)
    if token.lower().startswith("0b"):
        return int(token, 2)
    return int(token)


def _parse_reg(token: str) -> int:
    token = token.strip().lower()
    if not token.startswith("x"):
        raise ValueError(f"Expected register like x0..x63, got {token!r}")
    n = int(token[1:])
    if not (0 <= n <= 63):
        raise ValueError(f"Register out of range: {token!r}")
    return n


def _parse_pred(token: str) -> int:
    token = token.strip().lower()
    if token.startswith("p"):
        n = int(token[1:])
    else:
        n = int(token)
    if not (0 <= n <= 31):
        raise ValueError(f"Predicate out of range: {token!r}")
    return n


_MEM_RE = re.compile(r"^\s*([-+]?\d+|0x[0-9a-fA-F]+|0b[01]+)\s*\(\s*(x\d+)\s*\)\s*$")


def _parse_mem_operand(token: str) -> Tuple[int, int]:
    m = _MEM_RE.match(token)
    if not m:
        raise ValueError(f"Invalid memory operand {token!r}; expected imm(xN)")
    imm = _parse_int(m.group(1))
    rs1 = _parse_reg(m.group(2))
    return imm, rs1


def _split_operands(operand_str: str) -> List[str]:
    # Primary split is commas; if no commas, allow whitespace-separated operands.
    parts = [p.strip() for p in operand_str.split(",") if p.strip()]
    if len(parts) <= 1 and operand_str.strip():
        parts = [p.strip() for p in operand_str.split() if p.strip()]
    return parts


def _parse_optional_meta(operands: List[str], required_ops: int, allow_pred: bool) -> Tuple[int, int, int, List[str]]:
    """Parse optional trailing [predicate], [start], [end].

    Many of the repo's assembly files include a literal token 'pred' as a separator;
    this is ignored here.
    """
    # Remove any literal 'pred' tokens anywhere in the tail.
    operands = [o for o in operands if o.strip().lower() != "pred"]

    pred = 0
    start = 0
    end = 1

    # end bit
    if len(operands) > required_ops and operands[-1] in {"0", "1"}:
        end = int(operands.pop())
    # start bit
    if len(operands) > required_ops and operands[-1] in {"0", "1"}:
        start = int(operands.pop())
    # predicate
    if allow_pred and len(operands) > required_ops:
        last = operands[-1].strip().lower()
        if last.startswith("p") or last.isdigit():
            pred = _parse_pred(operands.pop())

    return pred, start, end, operands


def parse_asm_to_ir(path: Path) -> Tuple[Dict[int, IRInstr], Dict[str, int]]:
    """Parse a subset of assembly into IR instructions.

    Supports:
    - labels: `label:`
    - org directives: `org 0x1000` or `org(0x1000)`
    - optional trailing meta: `..., pN, start, end` (and ignores literal `pred`)
    """
    raw_lines = path.read_text(encoding="utf-8").splitlines()

    # First pass: labels + instruction skeleton addresses
    labels: Dict[str, int] = {}
    pc = 0
    pending: List[Tuple[int, str, List[str]]] = []

    for raw in raw_lines:
        line = _strip_comment(raw)
        if not line:
            continue

        if ":" in line:
            label, rest = line.split(":", 1)
            label = label.strip()
            if label:
                labels[label] = pc
            line = rest.strip()
            if not line:
                continue

        if line.lower().startswith("org"):
            # org 0x1000 or org(0x1000)
            m = re.search(r"org\s*\(?\s*([^\)\s]+)\s*\)?", line, flags=re.IGNORECASE)
            if not m:
                raise ValueError(f"Bad org directive: {raw!r}")
            pc = _parse_int(m.group(1))
            continue

        parts = line.split(None, 1)
        op = parts[0].lower()
        operand_str = parts[1] if len(parts) > 1 else ""
        operands = _split_operands(operand_str)

        # Pseudo support: allow `lli rd, IMM32` to mean "load full 32-bit literal".
        # The real ISA's U-type immediate field is only 12 bits; large constants must be
        # built with a sequence. Many tests use the pseudo for convenience.
        # this is incorrect behavior in the actual emulator, but temporarily supported here
        if op == "lli" and len(operands) >= 2:
            try:
                imm_val = _parse_int(operands[1])
            except ValueError:
                imm_val = None

            if imm_val is not None:
                imm_u32 = u32(imm_val)
                if imm_u32 > 0xFFF:
                    rd_tok = operands[0]
                    tail = operands[2:]  # predicate/start/end (and optional literal 'pred')
                    hi8 = (imm_u32 >> 24) & 0xFF
                    mid12 = (imm_u32 >> 12) & 0xFFF
                    lo12 = imm_u32 & 0xFFF

                    pending.append((pc, "lui", [rd_tok, hex(hi8)] + tail))
                    pc += 4
                    pending.append((pc, "lmi", [rd_tok, hex(mid12)] + tail))
                    pc += 4
                    pending.append((pc, "lli", [rd_tok, hex(lo12)] + tail))
                    pc += 4
                    continue

        pending.append((pc, op, operands))
        pc += 4

    # Second pass: finalize IR instructions (resolve labels into immediates)
    program: Dict[int, IRInstr] = {}
    for addr, op, operands in pending:
        # Determine required operands count + whether pred field exists for this op.
        # According to Teal Card v2:
        # - pred field exists for R/I/F/S/B/U/C types
        # - no pred field for J/P/H types (but assembly may include it; we ignore)
        allow_pred = op not in {"jal", "jalr", "jpnz", "prr", "prw", "halt"}

        if op in {"add", "sub", "mul", "div", "and", "or", "xor", "slt", "sltu", "addf", "subf", "mulf", "divf", "sll", "srl", "sra"}:
            required = 3
        elif op in {"addi", "xori", "ori", "slti", "sltiu", "slli", "srli", "srai"}:
            required = 3
        elif op in {"lw", "lh", "lb"}:
            # Supports both forms:
            #   lw rd, imm(rs1)        -> 2 operands
            #   lw rd, rs1, imm        -> 3 operands
            required = 2 if (len(operands) >= 2 and "(" in operands[1]) else 3
        elif op == "jalr":
            # Supports both forms:
            #   jalr rd, imm(rs1)      -> 2 operands
            #   jalr rd, rs1, imm      -> 3 operands
            required = 2 if (len(operands) >= 2 and "(" in operands[1]) else 3
        elif op in {"sw", "sh", "sb"}:
            # Supports both forms:
            #   sw rs2, imm(rs1)       -> 2 operands
            #   sw rs2, rs1, imm       -> 3 operands
            required = 2 if (len(operands) >= 2 and "(" in operands[1]) else 3
        elif op in {"beq", "bne", "bge", "bgeu", "blt", "bltu", "beqf", "bnef", "bgef", "bltf"}:
            required = 3
        elif op in {"auipc", "lli", "lmi", "lui"}:
            required = 2
        elif op in {"csrr"}:
            required = 2
        elif op in {"isqrt", "sin", "cos", "itof", "ftoi"}:
            required = 2
        elif op in {"jal"}:
            required = 2
        elif op in {"jpnz"}:
            required = 2
        elif op in {"prr", "prw"}:
            required = 2
        elif op in {"halt"}:
            required = 0
        else:
            raise NotImplementedError(f"Unknown/unsupported opcode in IR parser: {op}")

        pred, start, end, operands = _parse_optional_meta(list(operands), required, allow_pred=allow_pred)

        # Normalize/parse operands into typed args
        args: List[object] = []

        if op in {"add", "sub", "mul", "div", "and", "or", "xor", "slt", "sltu", "addf", "subf", "mulf", "divf", "sll", "srl", "sra"}:
            rd = _parse_reg(operands[0])
            rs1 = _parse_reg(operands[1])
            rs2 = _parse_reg(operands[2])
            args = [rd, rs1, rs2]

        elif op in {"addi", "xori", "ori", "slti", "sltiu", "slli", "srli", "srai"}:
            rd = _parse_reg(operands[0])
            rs1 = _parse_reg(operands[1])
            imm = _parse_int(operands[2])
            args = [rd, rs1, imm]

        elif op in {"lw", "lh", "lb"}:
            rd = _parse_reg(operands[0])
            if len(operands) == 2 and "(" in operands[1]:
                imm, rs1 = _parse_mem_operand(operands[1])
            elif len(operands) == 2:
                # Allow shorthand: lw rd, rs1  => lw rd, rs1, 0
                rs1 = _parse_reg(operands[1])
                imm = 0
            else:
                # Alternate syntax: lw rd, rs1, imm
                rs1 = _parse_reg(operands[1])
                imm = _parse_int(operands[2])
            args = [rd, rs1, imm]

        elif op == "jalr":
            # jalr rd, imm(rs1)
            rd = _parse_reg(operands[0])
            if len(operands) == 2 and "(" in operands[1]:
                imm, rs1 = _parse_mem_operand(operands[1])
            elif len(operands) == 2:
                rs1 = _parse_reg(operands[1])
                imm = 0
            else:
                rs1 = _parse_reg(operands[1])
                imm = _parse_int(operands[2])
            args = [rd, rs1, imm]

        elif op in {"sw", "sh", "sb"}:
            rs2 = _parse_reg(operands[0])
            if len(operands) == 2 and "(" in operands[1]:
                imm, rs1 = _parse_mem_operand(operands[1])
            elif len(operands) == 2:
                # Allow shorthand: sw rs2, rs1  => sw rs2, rs1, 0
                rs1 = _parse_reg(operands[1])
                imm = 0
            else:
                # Alternate syntax: sw rs2, rs1, imm
                rs1 = _parse_reg(operands[1])
                imm = _parse_int(operands[2])
            args = [rs2, rs1, imm]

        elif op in {"beq", "bne", "bge", "bgeu", "blt", "bltu", "beqf", "bnef", "bgef", "bltf"}:
            pred_dest = _parse_pred(operands[0])
            rs1 = _parse_reg(operands[1])
            rs2 = _parse_reg(operands[2])
            args = [pred_dest, rs1, rs2]

        elif op in {"auipc", "lli", "lmi", "lui"}:
            rd = _parse_reg(operands[0])
            imm = _parse_int(operands[1])
            args = [rd, imm]

        elif op == "csrr":
            rd = _parse_reg(operands[0])
            csr_tok = operands[1].strip().lower()
            if csr_tok.startswith("x"):
                csr = int(csr_tok[1:])
            else:
                csr = _parse_int(csr_tok)
            args = [rd, csr]

        elif op in {"isqrt", "sin", "cos", "itof", "ftoi"}:
            # F-type: rd, rs1
            rd = _parse_reg(operands[0])
            rs1 = _parse_reg(operands[1])
            args = [rd, rs1]

        elif op == "jal":
            rd = _parse_reg(operands[0])
            target = operands[1]
            if isinstance(target, str) and target in labels:
                imm = labels[target] - addr
            else:
                imm = _parse_int(str(target))
            args = [rd, imm]
            # Teal Card: no pred field; ignore parsed pred if user provided it
            pred = 0

        elif op == "jpnz":
            # Teal Card: jpnz rs1, imm  (rs1 holds predicate index in low 5 bits)
            p = operands[0].strip().lower()
            if p.startswith("p"):
                pred_idx = _parse_pred(p)
            else:
                # allow xN; use low 5 bits of reg number
                pred_idx = _parse_reg(p) & 0x1F
            target = operands[1]
            if isinstance(target, str) and target in labels:
                imm = labels[target] - addr
            else:
                imm = _parse_int(str(target))
            args = [pred_idx, imm]
            pred = 0

        elif op == "prr":
            # Teal Card semantics are a bit quirky. For the golden model, accept:
            #   prr pN, xD   => xD = PR[N]
            pred_idx = _parse_pred(operands[0])
            dst = _parse_reg(operands[1])
            args = [pred_idx, dst]
            pred = 0

        elif op == "prw":
            #   prw pN, xS   => PR[N] = (xS != 0)
            pred_idx = _parse_pred(operands[0])
            src = _parse_reg(operands[1])
            args = [pred_idx, src]
            pred = 0

        elif op == "halt":
            args = []
            pred = 0

        program[addr] = IRInstr(addr=addr, op=op, args=tuple(args), pred=pred, start=start, end=end)

    return program, labels


class RefMachine:
    def __init__(
        self,
        program: Dict[int, IRInstr],
        start_pc: int,
        thread_id: int = 0,
        *,
        mem: Optional[Dict[int, int]] = None,
        written_words: Optional[Set[int]] = None,
        allow_oob_reads: bool = False,
        allow_oob_writes: bool = False,
        allow_instr_writes: bool = False,
        model_mmio: bool = True,
    ) -> None:
        self.program = program
        self.pc = u32(start_pc)
        self.regs = [0] * 64
        self.preds = [0] * 32
        self.preds[0] = 1  # PR[0] treated as always-true
        self.thread_id = int(thread_id)
        self.csrs: Dict[int, int] = {1000: self.thread_id}

        self.allow_oob_reads = bool(allow_oob_reads)
        self.allow_oob_writes = bool(allow_oob_writes)
        self.allow_instr_writes = bool(allow_instr_writes)
        self.model_mmio = bool(model_mmio)

        # Byte-addressed memory (can be shared across threads)
        self.mem: Dict[int, int] = mem if mem is not None else {}
        # Word-aligned addresses that have been written by any store.
        # Used to optionally include stored-zero words in dumps.
        self.written_words: Set[int] = written_words if written_words is not None else set()

    def _mark_written_words(self, addr: int, size: int) -> None:
        a0 = u32(addr)
        a1 = u32(addr + size - 1)
        base0 = a0 & ~0x3
        base1 = a1 & ~0x3
        base = base0
        while True:
            self.written_words.add(base)
            if base == base1:
                break
            base = u32(base + 4)

    def mem_read_u8(self, addr: int) -> int:
        a = u32(addr)
        try:
            space = _classify_range(a, 1)
        except MemoryAccessError:
            if self.allow_oob_reads:
                return 0
            raise

        if space == "mmio" and self.model_mmio:
            return 0
        return int(self.mem.get(a, 0)) & 0xFF

    def mem_read_u16(self, addr: int) -> int:
        a = u32(addr)
        return self.mem_read_u8(a) | (self.mem_read_u8(a + 1) << 8)

    def mem_read_u32(self, addr: int) -> int:
        a = u32(addr)
        return (
            self.mem_read_u8(a)
            | (self.mem_read_u8(a + 1) << 8)
            | (self.mem_read_u8(a + 2) << 16)
            | (self.mem_read_u8(a + 3) << 24)
        ) & U32_MASK

    def mem_write(self, addr: int, value: int, size: int) -> None:
        a = u32(addr)
        v = u32(value)
        try:
            space = _classify_range(a, size)
        except MemoryAccessError:
            if self.allow_oob_writes:
                return
            raise

        if space == "mmio":
            # MMIO writes are side-effects; for dump purposes we do not store them.
            return
        if space == "instr" and not self.allow_instr_writes:
            raise MemoryAccessError(f"Write to instruction memory is not allowed: addr={a:#010x} size={size}")

        self._mark_written_words(a, size)

        for i in range(size):
            self.mem[a + i] = (v >> (8 * i)) & 0xFF

    def step(self, trace: bool = False) -> bool:
        """Execute one IR instruction at current PC. Returns True if HALT."""
        instr = self.program.get(self.pc)
        if instr is None:
            raise RuntimeError(f"No instruction at PC={self.pc:#010x}")

        trace_prefix = f"T{self.thread_id} " if trace else ""

        # Predication: pred=0 means unpredicated (always execute).
        if instr.pred != 0 and self.preds[instr.pred] == 0:
            if trace:
                print(f"{trace_prefix}PC={self.pc:#010x} SKIP pred=p{instr.pred} {instr.op} {instr.args}")
            self.pc = u32(self.pc + 4)
            return False

        if trace:
            print(f"{trace_prefix}PC={self.pc:#010x} {instr.op} {instr.args} pred=p{instr.pred}")

        op = instr.op
        a = instr.args

        if op == "halt":
            return True

        if op in {"add", "sub", "mul", "div", "and", "or", "xor", "slt", "sltu", "sll", "srl", "sra"}:
            rd, rs1, rs2 = (int(a[0]), int(a[1]), int(a[2]))
            v1 = u32(self.regs[rs1])
            v2 = u32(self.regs[rs2])
            if op == "add":
                out = u32(v1 + v2)
            elif op == "sub":
                out = u32(v1 - v2)
            elif op == "mul":
                out = u32(v1 * v2)
            elif op == "div":
                out = 0 if v2 == 0 else u32(int(sign_extend(v1, 32)) // int(sign_extend(v2, 32)))
            elif op == "and":
                out = u32(v1 & v2)
            elif op == "or":
                out = u32(v1 | v2)
            elif op == "xor":
                out = u32(v1 ^ v2)
            elif op == "slt":
                out = 1 if sign_extend(v1, 32) < sign_extend(v2, 32) else 0
            elif op == "sltu":
                out = 1 if v1 < v2 else 0
            elif op == "sll":
                out = u32(v1 << (v2 & 0x1F))
            elif op == "srl":
                out = u32(v1 >> (v2 & 0x1F))
            else:  # sra
                out = u32((sign_extend(v1, 32) >> (v2 & 0x1F)) & U32_MASK)
            if rd != 0:
                self.regs[rd] = out
            self.pc = u32(self.pc + 4)
            return False

        if op in {"addf", "subf", "mulf", "divf"}:
            rd, rs1, rs2 = (int(a[0]), int(a[1]), int(a[2]))
            f1 = f32_from_u32(u32(self.regs[rs1]))
            f2 = f32_from_u32(u32(self.regs[rs2]))
            if op == "addf":
                out_bits = u32_from_f32(f1 + f2)
            elif op == "subf":
                out_bits = u32_from_f32(f1 - f2)
            elif op == "mulf":
                out_bits = u32_from_f32(f1 * f2)
            else:
                out_bits = u32_from_f32(f1 / f2)
            if rd != 0:
                self.regs[rd] = out_bits
            self.pc = u32(self.pc + 4)
            return False

        if op in {"isqrt", "sin", "cos", "itof", "ftoi"}:
            rd, rs1 = (int(a[0]), int(a[1]))
            if op == "itof":
                # Integer to float32 bits; use signed int semantics.
                i = int(sign_extend(u32(self.regs[rs1]), 32))
                out_bits = u32_from_f32(float(i))
            elif op == "ftoi":
                # Float32 bits to integer; truncate toward zero.
                f = f32_from_u32(u32(self.regs[rs1]))
                out_bits = u32(int(f))
            else:
                x = f32_from_u32(u32(self.regs[rs1]))
                if op == "isqrt":
                    if x <= 0.0:
                        y = float("inf")
                    else:
                        y = 1.0 / math.sqrt(x)
                elif op == "sin":
                    y = math.sin(x)
                else:  # cos
                    y = math.cos(x)
                out_bits = u32_from_f32(y)
            if rd != 0:
                self.regs[rd] = out_bits
            self.pc = u32(self.pc + 4)
            return False

        if op in {"addi", "xori", "ori", "slti", "sltiu", "slli", "srli", "srai"}:
            rd, rs1, imm = (int(a[0]), int(a[1]), int(a[2]))
            imm6 = sign_extend(imm & 0x3F, 6)
            v1 = u32(self.regs[rs1])
            if op == "addi":
                out = u32(v1 + imm6)
            elif op == "xori":
                out = u32(v1 ^ u32(imm6))
            elif op == "ori":
                out = u32(v1 | u32(imm6))
            elif op == "slti":
                out = 1 if sign_extend(v1, 32) < imm6 else 0
            elif op == "sltiu":
                out = 1 if v1 < u32(imm6) else 0
            elif op == "slli":
                out = u32(v1 << (imm6 & 0x1F))
            elif op == "srli":
                out = u32(v1 >> (imm6 & 0x1F))
            else:
                out = u32((sign_extend(v1, 32) >> (imm6 & 0x1F)) & U32_MASK)
            if rd != 0:
                self.regs[rd] = out
            self.pc = u32(self.pc + 4)
            return False

        if op in {"lw", "lh", "lb"}:
            rd, rs1, imm = (int(a[0]), int(a[1]), int(a[2]))
            imm6 = sign_extend(imm & 0x3F, 6)
            addr = u32(self.regs[rs1] + imm6)
            if op == "lw":
                val = self.mem_read_u32(addr)
            elif op == "lh":
                val = u32(sign_extend(self.mem_read_u16(addr), 16))
            else:
                val = u32(sign_extend(self.mem_read_u8(addr), 8))
            if rd != 0:
                self.regs[rd] = val
            self.pc = u32(self.pc + 4)
            return False

        if op in {"sw", "sh", "sb"}:
            rs2, rs1, imm = (int(a[0]), int(a[1]), int(a[2]))
            imm6 = sign_extend(imm & 0x3F, 6)
            addr = u32(self.regs[rs1] + imm6)
            val = u32(self.regs[rs2])
            if op == "sw":
                self.mem_write(addr, val, 4)
            elif op == "sh":
                self.mem_write(addr, val & 0xFFFF, 2)
            else:
                self.mem_write(addr, val & 0xFF, 1)
            self.pc = u32(self.pc + 4)
            return False

        if op in {"beq", "bne", "bge", "bgeu", "blt", "bltu"}:
            pred_dest, rs1, rs2 = (int(a[0]), int(a[1]), int(a[2]))
            v1 = u32(self.regs[rs1])
            v2 = u32(self.regs[rs2])
            if op == "beq":
                res = 1 if v1 == v2 else 0
            elif op == "bne":
                res = 1 if v1 != v2 else 0
            elif op == "bge":
                res = 1 if sign_extend(v1, 32) >= sign_extend(v2, 32) else 0
            elif op == "bgeu":
                res = 1 if v1 >= v2 else 0
            elif op == "blt":
                res = 1 if sign_extend(v1, 32) < sign_extend(v2, 32) else 0
            else:
                res = 1 if v1 < v2 else 0
            if pred_dest != 0:
                self.preds[pred_dest] = res
            self.pc = u32(self.pc + 4)
            return False

        if op in {"auipc", "lli", "lmi", "lui"}:
            rd, imm = (int(a[0]), int(a[1]))
            imm12 = imm & 0xFFF
            if op == "auipc":
                out = u32(self.pc + (imm12 << 12))
            elif op == "lli":
                # R[rd] = {R[rd][31:12], imm[11:0]}
                out = u32((self.regs[rd] & 0xFFFFF000) | imm12)
            elif op == "lmi":
                # R[rd] = {R[rd][31:24], imm[11:0], R[rd][11:0]}
                out = u32((self.regs[rd] & 0xFF000FFF) | (imm12 << 12))
            else:  # lui
                # R[rd] = {imm[7:0], R[rd][23:0]}
                out = u32(((imm12 & 0xFF) << 24) | (self.regs[rd] & 0x00FFFFFF))
            if rd != 0:
                self.regs[rd] = out
            self.pc = u32(self.pc + 4)
            return False

        if op == "csrr":
            rd, csr = (int(a[0]), int(a[1]))
            val = u32(self.csrs.get(csr, 0))
            if rd != 0:
                self.regs[rd] = val
            self.pc = u32(self.pc + 4)
            return False

        if op == "jal":
            rd, imm = (int(a[0]), int(a[1]))
            ra = u32(self.pc + 4)
            if rd != 0:
                self.regs[rd] = ra
            self.pc = u32(self.pc + int(imm))
            return False

        if op == "jalr":
            rd, rs1, imm = (int(a[0]), int(a[1]), int(a[2]))
            imm6 = sign_extend(imm & 0x3F, 6)
            ra = u32(self.pc + 4)
            target = u32(self.regs[rs1] + imm6)
            if rd != 0:
                self.regs[rd] = ra
            self.pc = target
            return False

        if op == "prr":
            pred_idx, dst = (int(a[0]), int(a[1]))
            if dst != 0:
                self.regs[dst] = 1 if self.preds[pred_idx] != 0 else 0
            self.pc = u32(self.pc + 4)
            return False

        if op == "prw":
            pred_idx, src = (int(a[0]), int(a[1]))
            if pred_idx != 0:
                self.preds[pred_idx] = 1 if u32(self.regs[src]) != 0 else 0
            self.pc = u32(self.pc + 4)
            return False

        if op == "jpnz":
            pred_idx, imm = (int(a[0]), int(a[1]))
            if self.preds[pred_idx] != 0:
                self.pc = u32(self.pc + int(imm))
            else:
                self.pc = u32(self.pc + 4)
            return False

        raise NotImplementedError(f"Instruction not implemented in IR executor: {op}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asm", required=True, help="Input assembly .s file")
    parser.add_argument("--start-pc", default="0x0", help="Start PC (byte address)")
    parser.add_argument("--thread-id", type=int, default=0, help="Thread id used for CSRR 1000 (single-thread mode)")
    parser.add_argument(
        "--threads",
        type=int,
        default=1,
        help="Number of threads to execute (default: 1)",
    )
    parser.add_argument(
        "--thread-id-base",
        type=int,
        default=0,
        help="Base thread id when running --threads > 1 (thread ids are base..base+threads-1)",
    )
    parser.add_argument("--max-steps", type=int, default=100000, help="Max executed steps before stopping")
    parser.add_argument("--out", required=True, help="Output expected dump path")
    parser.add_argument("--trace", action="store_true", help="Print instruction trace")
    parser.add_argument(
        "--dump-space",
        default="data",
        choices=["data", "instr", "all"],
        help="Which address space(s) to include in the dump (default: data)",
    )
    parser.add_argument("--dump-mmio", action="store_true", help="Include MMIO range in the dump (usually not useful)")
    parser.add_argument(
        "--dump-stored-zeros",
        action="store_true",
        help="Include 0x00000000 words if they were written by a store (still skips untouched zeros)",
    )
    parser.add_argument("--allow-oob-reads", action="store_true", help="Treat out-of-range reads as 0 instead of error")
    parser.add_argument(
        "--allow-oob-writes",
        action="store_true",
        help="Ignore out-of-range/unmapped writes instead of error (not recommended)",
    )
    parser.add_argument("--allow-instr-writes", action="store_true", help="Allow stores into instruction space (not recommended)")
    args = parser.parse_args()

    asm_path = Path(args.asm).resolve()
    if not asm_path.exists():
        raise FileNotFoundError(asm_path)

    program, _labels = parse_asm_to_ir(asm_path)

    # If user didn't set a start PC explicitly, default is 0x0.
    # Many programs also use `org` directives; ensure start PC points at an instruction.
    start_pc = int(str(args.start_pc), 0)
    if start_pc not in program and program:
        # Fall back to the lowest instruction address.
        start_pc = min(program.keys())

    threads = int(args.threads)
    if threads < 1:
        raise ValueError("--threads must be >= 1")

    # Shared state across all threads (SIMT-style global memory).
    shared_mem: Dict[int, int] = {}
    shared_written_words: Set[int] = set()

    # Execute each thread independently (sequentially) but writing into shared memory.
    # This is sufficient for current golden tests (no atomics/barriers).
    if threads == 1:
        thread_ids = [int(args.thread_id)]
    else:
        base = int(args.thread_id_base)
        thread_ids = list(range(base, base + threads))

    for tid in thread_ids:
        m = RefMachine(
            program=program,
            start_pc=start_pc,
            thread_id=tid,
            mem=shared_mem,
            written_words=shared_written_words,
            allow_oob_reads=args.allow_oob_reads,
            allow_oob_writes=args.allow_oob_writes,
            allow_instr_writes=args.allow_instr_writes,
        )

        for _step in range(args.max_steps):
            halted = m.step(trace=args.trace)
            # x0 is hardwired zero
            m.regs[0] = 0
            if halted:
                break
        else:
            raise RuntimeError(
                f"Thread {tid} did not HALT within max-steps={args.max_steps}. Last PC={m.pc:#010x}"
            )

    dump_ranges: Optional[List[Tuple[int, int]]]
    if args.dump_space == "all":
        dump_ranges = [(INSTR_START, INSTR_END), (ARGS_START, ARGS_END), (HEAP_START, HEAP_END), (STACK_START, STACK_END)]
    elif args.dump_space == "instr":
        dump_ranges = [(INSTR_START, INSTR_END)]
    else:
        dump_ranges = [(ARGS_START, ARGS_END), (HEAP_START, HEAP_END), (STACK_START, STACK_END)]
    if args.dump_mmio:
        dump_ranges = (dump_ranges or []) + [(MMIO_START, MMIO_END)]

    write_dump(
        args.out,
        shared_mem,
        dump_ranges=dump_ranges,
        written_words=shared_written_words,
        dump_stored_zeros=args.dump_stored_zeros,
    )
    if args.trace:
        print(f"Wrote expected dump: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
