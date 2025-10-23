from reg_file import *
from instr import *

class Warp:
    def __init__(self, warp_id: int, pc: Bits) -> None:
        self.thread_ids: list[Bits] = [Bits(int=(i + 32 * warp_id), length=32) for i in range(32)]
        self.reg_files: list[Reg_File] = [Reg_File(64) for i in range(32)]
        self.masks: list[list[int]] = [[0 for i in range(16)] for j in range(32)]
        self.pc = pc

    def eval(self, instr: Instr, mem=None) -> Bits:
        for t_id in self.thread_ids:
            if self.masks[instr.mask_id][t_id]:
                instr.eval(t_id, self.reg_files[t_id], mem)
        
        ### IN PROGRESS - PC Computation ###
        """ 
        next_pc = Bits(int=self.pc.int + 4, length=32)
        match instr.opcode:
            case I_Op_2.JALR:
                next_pc = Bits(int=self.pc.int + 4, length=32)
        self.pc = next_PC
        return next_PC
        """ 