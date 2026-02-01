from reg_file import *
from instr import *
from bitstring import Bits
from mem import *

class Warp:
    def __init__(self, warp_id: int, pc: Bits, csr: dict) -> None:
        self.reg_files = [Reg_File(num_regs=64, num_bits_per_reg=32) for i in range(32)]
        self.pc = pc
        self.csr_file = csr # contains thread IDs and block IDs
        self.halt_status = False
        self.warp_id = warp_id

    def eval(self, instr: Instr, pred_reg_file: Predicate_Reg_File, mem: Mem, csr) -> Bits: #eventually change thread_id to Bits/csr_file
        for global_thread_id in self.csr_file["tid"]: 
            local_thread_id = global_thread_id % 32
            if pred_reg_file.read(local_thread_id).uint == 1:
                match instr.op:
                    case I_Op_2.JALR | P_Op.JPNZ | J_Op.JAL:
                        instr.eval(global_thread_id=local_thread_id, t_reg=self.reg_files[local_thread_id], mem=mem, pred_reg_file=pred_reg_file, csr=csr)
                        self.pc = instr.pc
                        return self
                    case H_Op.HALT:
                        self.halt_status = True
                        return self
                    case _:
                        instr.eval(global_thread_id=local_thread_id, t_reg=self.reg_files[local_thread_id], mem=mem, pred_reg_file=pred_reg_file, csr=csr)
            else:
                pred_reg_file.write(global_thread_id, Bits(uint=1, length=1)) #assume predication only skips one instruction
        self.pc = Bits(int=self.pc.int + 4, length=32) #potential problem of jumps incrementing by an extra 4? 
        return self