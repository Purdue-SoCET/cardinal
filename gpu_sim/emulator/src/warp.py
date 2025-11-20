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

    def eval(self, instr: Instr, pred_reg_file: Predicate_Reg_File, mem: Mem, csr) -> Bits: #eventually change thread_id to Bits/csr_file
        match instr.op:
            case I_Op_2.JALR | P_Op.JPNZ | J_Op.JAL:
                instr.eval(global_thread_id = 0, t_reg=self.reg_files[0], pred_reg_file=pred_reg_file, mem=None, csr=None)
                self.pc = instr.pc
                return None
            case H_Op.HALT:
                self.halt_status = True
                return True
        # print(csr)
        # print(instr.op)
        for global_thread_id in self.csr_file["tid"]: 
            local_thread_id = global_thread_id % 32
            # print(f"tid={local_thread_id}")
            if pred_reg_file.read(local_thread_id).uint == 1:
                halt = instr.eval(global_thread_id=local_thread_id, t_reg=self.reg_files[local_thread_id], mem=mem, pred_reg_file=pred_reg_file, csr=csr)
                if(halt):
                    print("halted")
                    self.halt_status = True
                    return True
            else:
                print("predicate false")
        self.pc = Bits(int=self.pc.int + 4, length=32)
        return None