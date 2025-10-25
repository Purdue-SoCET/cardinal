#write into memsim.hex as hash table
import atexit
from pathlib import Path
from bitstring import Bits

class Mem: 
    def __init__(self, start_pc: int, input_file: str) -> None:
        self.memory: dict[int, int] = {}

        endianness = "little"

        p = Path(input_file)
        if not p.exists():
            raise FileNotFoundError(f"Program file not found: {p}")

        with p.open("r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                # clean line: remove comments/whitespace/underscores
                for marker in ("//", "#"):
                    i = raw.find(marker)
                    if i != -1:
                        raw = raw[:i]
                bits = raw.strip().replace("_", "")
                if not bits:
                    continue
                if len(bits) != 32 or any(c not in "01" for c in bits):
                    raise ValueError(f"Line {line_no}: expected 32 bits, got {bits!r}")

                word = int(bits, 2) & 0xFFFF_FFFF

                # split into 4 bytes per chosen endianness
                if endianness == "little":
                    b0 = (word >> 0)  & 0xFF
                    b1 = (word >> 8)  & 0xFF
                    b2 = (word >> 16) & 0xFF
                    b3 = (word >> 24) & 0xFF
                else:  # big-endian
                    b3 = (word >> 0)  & 0xFF
                    b2 = (word >> 8)  & 0xFF
                    b1 = (word >> 16) & 0xFF
                    b0 = (word >> 24) & 0xFF

                # store 4 consecutive bytes
                self.memory[addr + 0] = b0
                self.memory[addr + 1] = b1
                self.memory[addr + 2] = b2
                self.memory[addr + 3] = b3

                addr += 4  # next word starts 4 bytes later
        atexit.register(self.dump_on_exit)

    def read(self, addr: int, bytes: int) -> int:
        val = 0

        for i in range(bytes):
            b = self.memory[addr + 1] & 0xFF
            val |= b << (8 * i)
        return val

    def write(self, addr: int, data: int, bytes: int) -> None:
        for i in range(bytes):
            self.memory[addr + i] = (data >> (8 * i)) & 0xFF
    def dump_on_exit(self) -> None:
        try:
            self.dump("memsim.hex")
        except Exception:
            print("oopsie")
            pass
    
    # CAN CHANGE THIS SHIT LATER IF WE WANT TO PRINT OUT MORE INFO
    def dump(self, path: str = "memsim.hex") -> None:
        """
        Dump memory one 32-bit word per line.
        Groups consecutive bytes [addr, addr+1, addr+2, addr+3] into one word.
        Skips words that are entirely zero (uninitialized).
        """
        with open(path, "w", encoding="utf-8") as f:
            # round down to nearest word boundary
            min_addr = min(self.memory.keys(), default=0) & ~0x3
            max_addr = max(self.memory.keys(), default=0)
            for base in range(min_addr, max_addr + 1, 4):
                # collect 4 bytes for this word
                b0 = self.memory.get(base + 0, 0)
                b1 = self.memory.get(base + 1, 0)
                b2 = self.memory.get(base + 2, 0)
                b3 = self.memory.get(base + 3, 0)
                if (b0 | b1 | b2 | b3) == 0:
                    continue  # skip all-zero words

                word = b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)

                f.write(f"{base:#010x} {word:#010x}\n")

    #dump into memsim.hex
        #copy meminit.hex into memsim