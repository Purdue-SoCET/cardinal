from reg_file import *
from instr import *

class Warp:
    def __init__(self, warpId: int) -> None:
        self.threadIds: list[Bits] = [Bits(int=(i+32*warpId), length=32) for i in range(32)]
        self.reg_files: list[Reg_File] = [Reg_File(64) for i in range(64)]
        self.masks: list[list[int]] = [[0 for i in range(16)] for j in range(32)]

    def eval(self, instr) -> None:
        for t_id in self.threadIds:
            if self.masks[instr.mask_id][t_id]:
                instr.eval(t_id, self.reg_files[t_id])