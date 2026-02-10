from dataclasses import dataclass, field
from typing import Any, List
from bitstring import Bits

@dataclass
class RegisterFile:
    # Hierarchy: Bank(List), Warp(List), Operand(List), Threads(List), Data per thread (int)
    banks: int = 2
    warps: int = 32
    regs_per_warp: int = 64
    threads_per_warp: int = 32
    regs: List[List[List[List[Bits]]]] = field(init=False)

    def __post_init__(self):
        self.regs = [[[[Bits(uint=0, length=32) for _ in range(self.threads_per_warp)] for _ in range(self.regs_per_warp)] for _ in range(self.warps // self.banks)] for _ in range(self.banks)]

    def write_warp_gran(self, warp_id: int, dest_operand: Bits, data: Bits) -> None:
        self.regs[warp_id % self.banks][warp_id // 2][dest_operand.int] = data

    def write_thread_gran(self, warp_id: int, dest_operand: Bits, thread_id: int, data: Bits) -> None:
        self.regs[warp_id % self.banks][warp_id // 2][dest_operand.int][thread_id] = data

    def read_warp_gran(self, warp_id: int, src_operand: Bits) -> Any:
        return self.regs[warp_id % self.banks][warp_id // 2][src_operand.int]
    
    def read_thread_gran(self, warp_id: int, src_operand: Bits, thread_id: int) -> Any:
        return self.regs[warp_id % self.banks][warp_id // 2][src_operand.int][thread_id]

    def dump(self, float_regs=None):
        """
        Prints the full register file content for any active warp.
        If a warp has ANY data, all registers (0-63) are printed.
        If a warp is completely empty, it is skipped.
        """
        if float_regs is None:
            float_regs = []

        print(f"\n{'='*80}")
        print(f"{'REGISTER FILE FULL DUMP':^80}")
        print(f"{'='*80}")

        active_warps_found = False

        for w in range(self.warps):
            # 1. Check if the ENTIRE warp is empty first
            warp_is_empty = True
            for r in range(self.regs_per_warp):
                data = self.read_warp_gran(w, Bits(uint=r, length=32))
                if any(x.uint != 0 for x in data):
                    warp_is_empty = False
                    break
            
            # If the whole warp is 0, skip it entirely
            if warp_is_empty:
                continue

            active_warps_found = True
            print(f"\n[ Warp {w} ]")
            print("-" * 80)

            # 2. Print EVERY register for this warp, even if it's 0
            for r in range(self.regs_per_warp):
                vals = self.read_warp_gran(w, Bits(uint=r, length=32))
                
                # Determine display format (Float vs Int)
                is_float = r in float_regs
                label = "FLOAT" if is_float else "INT"
                
                print(f"  R{r:<2} ({label}):")

                # Print 32 threads in a 4x8 grid for readability
                # Change range(0, 32, 8) if threads_per_warp changes
                for i in range(0, self.threads_per_warp, 8):
                    chunk = vals[i : i + 8]
                    
                    if is_float:
                        # Format as float (e.g., 1.5000)
                        formatted = [f"{v.float:>10.4f}" for v in chunk]
                    else:
                        # Format as integer (e.g., 123)
                        formatted = [f"{v.int:>10}" for v in chunk]
                    
                    # Print the row of 8 threads
                    print(f"    T{i:02d}-T{i+7:02d}: {' '.join(formatted)}")
                
                # Add a small separator between registers for clarity
                print("") 

        if not active_warps_found:
            print("\n  (Register File is entirely empty)")
            
        print(f"{'='*80}\n")
    
### TESTING ###

if __name__ == "__main__":
    regfile = RegisterFile(
        banks = 2,
        warps = 4,
        regs_per_warp = 4,
        threads_per_warp = 2
    )

    # order of args for write (warp granularity):   (warp_id, dest_operand, data)
    # order of args for write (thread granularity): (warp_id, dest_operand, thread_id, data)
    # order of args for read (warp granularity):    (warp_id, src_operand, data)
    # order of args for read (thread granularity):  (warp_id, src_operand, thread_id, data)

    # regfile.write_thread_gran(3, 2, 0, 120394234)
    regfile.write_warp_gran(2, Bits(uint=3, length=32), [Bits(uint=67, length=32), Bits(uint=41, length=32)])
    print(regfile.regs[0][1][3])