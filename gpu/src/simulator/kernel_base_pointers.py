from bitstring import Bits

class KernelBasePointers:
    def __init__(self, max_kernels_per_SM):
        self.max_kernels_per_SM = max_kernels_per_SM

        self.regs = [Bits(uint=0, length=32)]*self.max_kernels_per_SM

    def read(self, kernel_id):
        return self.regs[kernel_id]
    
    def write(self, kernel_id, ptr: Bits):
        self.regs[kernel_id] = ptr