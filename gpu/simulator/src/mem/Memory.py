# Memory.py — Fully Patched for ICache + MemController correctness
import sys
from pathlib import Path
import atexit
from bitstring import Bits

class Mem:
    def __init__(self, start_pc: int, input_file: str, fmt: str = "bin"):
        self.memory: dict[int, int] = {}
        self.format = fmt
        self.start_pc = int(start_pc)

        p = Path(input_file)
        if not p.exists():
            raise FileNotFoundError(f"Program file not found: {p}")

        addr = self.start_pc
        endianness = "little"

        with p.open("r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                for marker in ("//", "#"):
                    i = raw.find(marker)
                    if i != -1:
                        raw = raw[:i]

                bits = raw.strip().replace("_", "")
                if not bits:
                    continue

                if self.format == "hex":
                    if len(bits) != 8:
                        raise ValueError(f"Line {line_no}: expected 8 hex chars, got {bits!r}")
                    word = int(bits, 16)
                elif self.format == "bin":
                    if len(bits) != 32:
                        raise ValueError(f"Line {line_no}: expected 32 bits, got {bits!r}")
                    word = int(bits, 2)
                else:
                    raise ValueError("Unknown format type (use 'hex' or 'bin')")

                if endianness == "little":
                    b0 = (word >> 0) & 0xFF
                    b1 = (word >> 8) & 0xFF
                    b2 = (word >> 16) & 0xFF
                    b3 = (word >> 24) & 0xFF
                else:
                    b3 = (word >> 0) & 0xFF
                    b2 = (word >> 8) & 0xFF
                    b1 = (word >> 16) & 0xFF
                    b0 = (word >> 24) & 0xFF

                self.memory[addr + 0] = b0
                self.memory[addr + 1] = b1
                self.memory[addr + 2] = b2
                self.memory[addr + 3] = b3
                addr += 4

        atexit.register(self.dump_on_exit)

    def read(self, addr: int, size: int = 4) -> Bits:
        byte_addr = int(addr)
        data = bytes(self.memory.get(byte_addr + i, 0) & 0xFF for i in range(int(size)))
        return Bits(bytes=data)

    def write(self, addr: int, data: Bits, bytes_t: int):
        byte_addr = int(addr)
        b = data.tobytes()[:int(bytes_t)]
        for i, val in enumerate(b):
            self.memory[byte_addr + i] = val & 0xFF

    def dump_on_exit(self):
        try:
            self.dump("memsim.hex")
        except Exception:
            print("[Mem] dump failed")

    def dump(self, path="memsim.hex"):
        if not self.memory:
            return
        min_addr = min(self.memory.keys()) & ~0x3
        max_addr = max(self.memory.keys())
        with open(path, "w", encoding="utf-8") as f:
            for base in range(min_addr, max_addr + 1, 4):
                b0 = self.memory.get(base + 0, 0)
                b1 = self.memory.get(base + 1, 0)
                b2 = self.memory.get(base + 2, 0)
                b3 = self.memory.get(base + 3, 0)
                if (b0 | b1 | b2 | b3) == 0:
                    continue
                word = (b0 & 0xFF) | ((b1 & 0xFF) << 8) | ((b2 & 0xFF) << 16) | ((b3 & 0xFF) << 24)
                f.write(f"{base:#010x} {word:#010x}\n")
