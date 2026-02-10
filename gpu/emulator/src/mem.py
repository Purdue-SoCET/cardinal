#write into memsim.hex as hash table
from pathlib import Path
import atexit
from pathlib import Path
from bitstring import Bits

class Mem: 
    def __init__(self, start_pc: int, input_file: str, mem_format: str) -> None:
        self.memory: dict[int, int] = {}

        self.endianness = "little"
        addr = start_pc

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
                bits = raw.strip().replace("_", "").upper()
                if not bits:
                    continue
                if (mem_format == "hex"):
                    if len(bits) != 8 or any(c not in "0123456789ABCDEF" for c in bits):
                        raise ValueError(f"Line {line_no}: expected 8 hex, got {bits!r}")
                    word = int(bits, 16) & 0xFFFF_FFFF
                
                elif (mem_format == "bin"):
                    if len(bits) != 32 or any(c not in "01" for c in bits):
                        raise ValueError(f"Line {line_no}: expected 32 bits, got {bits!r}")
                    word = int(bits, 2) & 0xFFFF_FFFF
                # else: 
                #     word = int(bits, 2) & 0xFFFF_FFFF
                # split into 4 bytes per chosen endianness
                if self.endianness == "little":
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

    def read(self, addr: int, bytes: int) -> Bits:
        val = 0

        for i in range(bytes): #reads LSB first
            b = self.memory[addr + i] & 0xFF #endianness
            val |= b << (8 * i)

        print(f"* Read from address {addr:#010x} for {bytes} bytes: {val:#010x}")
        return Bits(uint=val, length=8 * bytes)

    def write(self, addr: Bits, data: Bits, bytes_t: int) -> None:
        print(f"\tWrite to address {addr:#010x} for {bytes_t} bytes: {data.uint:#010x}")
        for i in range(bytes_t):
            self.memory[addr + i] =  (data.uint >> (8 * i)) & 0xFF

        
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
        word_bases = {addr & ~0x3 for addr in self.memory.keys()}

        with open(path, "w", encoding="utf-8") as f:
            for base in sorted(word_bases):
                # collect 4 bytes for this word
                b0 = self.memory.get(base + 0, 0) & 0xFF
                b1 = self.memory.get(base + 1, 0) & 0xFF
                b2 = self.memory.get(base + 2, 0) & 0xFF
                b3 = self.memory.get(base + 3, 0) & 0xFF
                if (b0 | b1 | b2 | b3) == 0:
                    continue  # skip all-zero words

                if self.endianness == 'little':
                    # Little Endian: Addr+0 is LSB
                    word = b0 | (b1 << 8) | (b2 << 16) | (b3 << 24)
                else:
                    # Big Endian: Addr+0 is MSB
                    word = (b0 << 24) | (b1 << 16) | (b2 << 8) | b3

                f.write(f"{base:#010x} {word:#010x}\n")

    #dump into memsim.hex
        #copy meminit.hex into memsim