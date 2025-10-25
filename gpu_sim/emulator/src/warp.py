from reg_file import *
from instr import *
from bitstring import Bits
from csr_file import *

class Warp:
    def __init__(self, warp_id: int, pc: Bits, csr: dict) -> None:
        self.reg_files = [Reg_File(num_regs=64, num_bits_per_reg=32) for i in range(32)]
        self.pc = pc
        self.csr_file = csr # contains thread IDs and block IDs

    # def eval(self, instr: Instr, pred_reg_file: Predicate_Reg_File, mem: Mem) -> Bits:
    #     for global_thread_id in self.csr_file["tid"]:
    #         self.CSR_File = CSR_File(warp_id=warp_id, block_id=warp_id) # NOTE: CHANGE!!!

    def eval(self, instr: Instr, pred_reg_file: Predicate_Reg_File) -> Bits:
        # iterating through every thread is unncessesary, since threads will always share the same PC within a warp.
        # for global_thread_id in self.CSR_File.global_thread_ids: 
        #     if pred_reg_file.read(global_thread_id).int == 1:
        #         next_pc = instr.eval(global_thread_id, self.reg_files[Reg_File._get_local_thread_id_from(global_thread_id)], mem)
        match instr.op:
            case I_Op_2.JALR | P_Op.JPNZ | J_Op.JAL:
                instr.eval(1, self.reg_files)
                self.pc = instr.pc
            case _:
                self.pc = Bits(int=self.pc.int + 4, length=32)
        return pred_reg_file