from dataclasses import dataclass, field
from typing import Any, List

@dataclass
class RegisterFile:
    # Hierarchy: Bank(List), Warp(List), Operand(List), Threads(List), Data per thread (int)
    banks: int = 2
    warps: int = 32
    regs_per_warp: int = 64
    threads_per_warp: int = 32
    regs: List[List[List[List[int]]]] = field(init=False)

    def __post_init__(self):
        self.regs = [[[[0 for _ in range(self.threads_per_warp)] for _ in range(self.regs_per_warp)] for _ in range(self.warps // self.banks)] for _ in range(self.banks)]

    def write_warp_gran(self, warp_id: int, dest_operand: int, data: int) -> None:
        self.regs[warp_id % self.banks][warp_id // 2][dest_operand] = data

    def write_thread_gran(self, warp_id: int, dest_operand: int, thread_id: int, data: int) -> None:
        self.regs[warp_id % self.banks][warp_id // 2][dest_operand][thread_id] = data

    def read_warp_gran(self, warp_id: int, src_operand: int) -> Any:
        return self.regs[warp_id % self.banks][warp_id // 2][src_operand]
    
    def read_thread_gran(self, warp_id: int, src_operand: int, thread_id: int) -> Any:
        return self.regs[warp_id % self.banks][warp_id // 2][src_operand][thread_id]
    
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

    regfile.write_thread_gran(3, 2, 0, 120394234)
    regfile.write_warp_gran(2, 3, [67, 41])
    print(regfile.regs)