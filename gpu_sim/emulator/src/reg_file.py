from bitstring import Bits 

class Reg_File:
    def __init__(self, num_regs: int = 64, num_bits_per_reg: int = 32, init_value: int=0) -> None:
        self.arr: list[Bits] = [Bits(uint=init_value, length=num_bits_per_reg) for i in range(num_regs)]
        self.num_regs = num_regs
        self.num_bits_per_reg = num_bits_per_reg
        
    def read(self, rd: Bits) -> Bits:
        return self.arr[rd.uint]

    def write(self, rd: Bits, val: Bits) -> None:
        if(rd.int == 0):
            return
        self.arr[rd.uint] = val

    @staticmethod
    def _get_local_thread_id_from(global_thread_id: int) -> int:
        return global_thread_id % 32
