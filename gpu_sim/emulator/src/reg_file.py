
from bitstring import Bits 
from functools import singledispatchmethod

# TODO: Implement fixed zero register behavior

class RegFile:
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


class PredicateRegFile(RegFile):
    def __init__(self, size: int=32, thread_per_warp: int=32) -> None:
        self.thread_per_warp = thread_per_warp
        super().__init__(num_regs=size, num_bits_per_reg=thread_per_warp, init_value=0)
        self.write(Bits(uint=0, length=5), Bits(uint=(1 << thread_per_warp) - 1, length=thread_per_warp))  # set p0 to all ones

    def read(self, rd: Bits) -> Bits:
        return self.arr[rd.uint]
    
    def read_thread(self, rd: Bits, thread_id: int) -> bool:
        if(thread_id >= self.thread_per_warp):
            # TODO: Remove this behavior after memory system better defined for non linear thread system
            thread_id = thread_id % self.thread_per_warp

        reg_val = self.arr[rd.uint]
        return (reg_val.uint >> thread_id) & 0x1

    def write_thread(self, rd: Bits, thread_id: int, val: bool) -> None:
        if(thread_id >= self.thread_per_warp):
            # TODO: Remove this behavior after memory system better defined for non linear thread system
            thread_id = thread_id % self.thread_per_warp

        reg_val = self.arr[rd.uint]
        if(val.uint):
            self.arr[rd.uint] = Bits(uint=(reg_val.uint | (1 << thread_id)), length=self.thread_per_warp)
        else:
            self.arr[rd.uint] = Bits(uint=(reg_val.uint & ~(1 << thread_id)), length=self.thread_per_warp)


class CsrRegFile(RegFile):
    # Define CSR mapping TODO: Check with hardware
    csr_map = {
        "thread_id": 0x000,
        "block_id": 0x001,
        "block_dim": 0x002,
        "arg_ptr": 0x003,
    }

    def __init__(self, thread_id: int, block_id: int, arg_ptr: int) -> None:
        super().__init__(num_regs=64, num_bits_per_reg=32, init_value=0)

        self.write(Bits(uint=self.csr_map["thread_id"], length=6), Bits(uint=thread_id, length=32))
        self.write(Bits(uint=self.csr_map["block_id"], length=6), Bits(uint=block_id, length=32))
        self.write(Bits(uint=self.csr_map["arg_ptr"], length=6), Bits(uint=arg_ptr, length=32))

    def read(self, rd: Bits) -> Bits:
        if(rd.uint not in self.csr_map.values()):
            raise RuntimeError(f"CSR register {rd.uint} not defined in mapping")

        return super().read(rd)

    def get_thread_id(self) -> int:
        return self.read(Bits(uint=self.csr_map["thread_id"], length=6)).uint
    
    def get_block_id(self) -> int:
        return self.read(Bits(uint=self.csr_map["block_id"], length=6)).uint

    def get_block_dim(self) -> int:
        return self.read(Bits(uint=self.csr_map["block_dim"], length=6)).uint

    def get_arg_ptr(self) -> int:
        return self.read(Bits(uint=self.csr_map["arg_ptr"], length=6)).uint
    
    def get_global_thread_id(self) -> int:
        return self.get_block_id() * self.get_block_dim() + self.get_thread_id()