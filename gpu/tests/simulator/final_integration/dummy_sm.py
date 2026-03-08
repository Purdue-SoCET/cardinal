#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

class DummyMemory:
    def __init__(self):
        # Sparse memory dictionary: address -> 32-bit word
        self.memory = {}

    def load_program(self, file_path: Path):
        """Reads a file where each line is 'address(hex) data(binary)'."""
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_no, raw in enumerate(f, start=1):
                # Strip out any comments
                for marker in ("//", "#"):
                    idx = raw.find(marker)
                    if idx != -1:
                        raw = raw[:idx]
                
                # Remove whitespace (other than the separator) and underscores
                line = raw.strip().replace("_", "")
                if not line:
                    continue
                
                parts = line.split()
                if len(parts) != 2:
                    print(f"Warning: Skipping line {line_no}. Expected format 'ADDR DATA', got: '{line}'")
                    continue
                
                addr_str, data_str = parts
                
                if len(data_str) != 32:
                    print(f"Warning: Line {line_no}. Expected 32-bit binary data, got {len(data_str)} bits: '{data_str}'")
                    # We will still try to parse it, but it's good to warn you
                
                try:
                    # Parse address as base 16 (or base 0 which auto-detects 0x)
                    addr = int(addr_str, 0)
                    # Parse data as base 2
                    data = int(data_str, 2)
                    
                    # Force word alignment just to be safe
                    addr = addr & ~0x3
                    self.memory[addr] = data & 0xFFFFFFFF
                except ValueError:
                    print(f"Warning: Skipping line {line_no}. Invalid address or binary string.")

    def dump_hex(self, file_path: Path):
        """Dumps the sparse memory to a hex file instantly by skipping empty space."""
        if not self.memory:
            # print("Warning: Memory is empty. Nothing to dump.")
            return
            
        with open(file_path, 'w', encoding='utf-8') as f:
            # ONLY loop through the exact addresses that were written to!
            for base in sorted(self.memory.keys()):
                word = self.memory[base]
                f.write(f"0x{base:08X} 0x{word:08X}\n")
                
def main():
    parser = argparse.ArgumentParser(description="Dummy SM: Memory IO Tester")
    parser.add_argument("input_file", help="Path to the input meminit.hex file")
    parser.add_argument("-o", "--output", default="memsim.hex", help="Path to the output memsim.hex file")
    
    args = parser.parse_args()
    in_path = Path(args.input_file)
    out_path = Path(args.output)
    
    if not in_path.exists():
        print(f"Error: Input file '{in_path}' does not exist.")
        sys.exit(1)
        
    sm_mem = DummyMemory()
    sm_mem.load_program(in_path)
    
    # Optional: You can inject dummy operations here to test specific writes
    # sm_mem.memory[0x10000150] = 0x00000003
    sm_mem.dump_hex(out_path)

if __name__ == "__main__":
    main()