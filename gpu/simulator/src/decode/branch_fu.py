from common.custom_enums_multi import B_Op, P_Op
from simulator.src.base_class import Instruction

class BranchFU(FunctionalSubUnit):
    def __init__(self, instructions: Instruction, prf_rd_data, op_1, op_2):
        super.__init__(num=0) # only one branch unit
        self.warp_id = instructions.warp
        self.decode_mapping_table = {
            0: "beq",
            1: "bne",
        }
        self.opcode = B_Op | P_Op
        self.prf_rd_data = prf_rd_data
        self.op1 = op_1
        self.op2 = op_2
        self.num_threads = len(op_1)
        self.prf_wr_data = None

    def to_signed(self, val, bits=32):
        if val & (1 << (bits - 1)):
            val -= 1 << bits
        return val

    def alu_decoder(self):
        if self.opcode == B_Op.BEQ:
            results = [self.op1[i] == self.op2[i] for i in range(self.num_threads)]
        elif self.opcode == B_Op.BNE:
            results = [self.op1[i] != self.op2[i] for i in range(self.num_threads)]
        elif self.opcode == P_Op.JPNZ:
            results = [self.op[i] != 0 for i in range(self.num_threads)]
            raise ValueError(f"Unknown opcode {self.opcode}")
        return results

    def update_pred(self):
        tnt = self.alu_decoder()
        self.prf_wr_data = [
            self.prf_rd_data[i] and tnt[i] for i in range(self.num_threads)
        ]
        return self.prf_wr_data
 
 