from bitstring import Bits 
class Reg_File:
    def __init__(self, size=64) -> None:
        self.arr: list[Bits] = [Bits(int=0, length=32) for i in range(size)]
    
    def read(self, rd: Bits) -> Bits:
        return self.arr[rd.int]

    def write(self, rd: Bits, val: Bits) -> None:
        if(rd.int == 0):
            return
        self.arr[rd.int] = val
