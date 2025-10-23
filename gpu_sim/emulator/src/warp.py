from reg_file import *
from instr import *

class Warp:
    def __init__(self, warp_id: int, pc: Bits) -> None:
        self.reg_files = [Reg_File(64) for i in range(32)]
        self.pred_reg_file = Predicate_Reg_File()
        self.pc = pc
        self.csr_file = CSR_File(warp_id) # contains thread IDs and block IDs

    def eval(self, instr: Instr, mem=None) -> Bits:
        for t_id in self.csr_file.thread_ids:
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