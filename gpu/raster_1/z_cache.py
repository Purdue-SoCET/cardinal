from bits import Bits
from hardware_lib import Table

class Z_cache(Table):
    def __init__(self, size = 12, blockSize = 64, dataSize = 16):
        super().__init__(size, blockSize)
        self.dataSize = dataSize
        self.blockSize = blockSize
        self.valid = [Bits(size = 1)] * size
        self.dirty = [Bits(size = 1)] * size
        self.tag = [Bits()] * size

    def r_mem(self, addr : Bits, index : Bits):
        print("Requesting memory at {}", addr.getBits())
        #self.table[index]

    def w_mem(self, addr : Bits, data : Bits):
        print("Writing {} to memory at {}", data.getBits(), addr.getBits())

    def read(self, addr : Bits):
        index = addr.getBits()[2:6]
        index = Bits(size=4, val = index).getInt()

        if (self.valid[index].getBits == '1'):
            tag = addr.getBits()[6:32]
            c_tag = self.tag[index]

            if (tag != c_tag):
                if (self.dirty[index].getBits() == '1'):
                    self.w_mem(c_tag.getBits() + Bits(size = 4, val = index).getBits() + '00', self.table[index])
                    self.dirty[index] = Bits(size = 1, val = '0')
                    
                self.r_mem(addr, index)
        else:
            self.r_mem(addr, index)
        
        return self.table[index]
    
    def write(self, addr : Bits, data : Bits):
        index = addr.getBits()[2:6]
        index = Bits(size=4, val = index).getInt()

        tag = addr.getBits()[6:32]
        c_tag = self.tag[index]

        if (tag != c_tag or self.valid[index] == 0 or (self.valid[index].getBits() == '1' and self.dirty[index].getBits() == '1')):
            self.w_mem(addr, self.table[index])
        
        self.dirty[index] = Bits(size = 1, val = '1')
        self.tag[index] = Bits(size = 32 - 6, val = addr.getBits()[6:32])
        self.valid[index] = Bits(size = 1, val = '1')
        self.table[index] = Bits(size = self.dataSize, val = data.getBits())

        return
