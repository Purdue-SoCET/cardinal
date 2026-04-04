from bits import Bits
from numpy import inf as invalid

class Table():
    def __init__(self, size : int = 12, blockSize : int = 64):
        self.table = [Bits(blockSize)] * size

    def insert(self, data, index):
        self.table[index] = data

    def read(self, index):
        return self.table[index]

class translationLookupTable(Table):
    def __init__(self, size : int = 1, dataSize : int = 4):
        super().__init__(size, dataSize)


class vertexTable(Table):
    def __init__(self, size : int = 12, blockSize : int = 64):
        super().__init__(size, blockSize)
        self.refCount = [0] * size
        self.valid = [0] * size

    def getRefCount(self, index):
        return self.refCount[index]
    
    def validate(self, index):
        self.valid[index] = 1
    
    def invalidate(self, index):
        self.valid[index] = 0

    def increment(self, index):
        self.refCount[index] += 1

    def decrement(self, index):
        self.refCount[index] -= 1

    def checkValid(self, index):
        return self.valid[index]


class buffer():
    def __init__(self, size : int = 2, dataSize : int = 32):
        self.size = size
        self.currSize = 0
        self.dataSize = dataSize
        self.buffer = []
        self.out = invalid

    def insert(self, data : Bits):
        if (data.getSize() != self.dataSize):
            return -1 #Bit width mismatch
        
        if (self.currSize < self.size):
            self.buffer.append(data)
            self.currSize += 1
        elif (self.currSize == self.size):
            if (self.out == invalid):
                self.out = self.buffer.pop(0)
                self.buffer.append(data)
                return 0
            else:
                return -2 #Output has not yet been acknowledged, so nothing doing
        else:
            return -3 #This should not be possible!

        if (self.currSize == self.size):
            self.out = self.buffer[0]
        
        return 0

    def acked(self):
        self.out = invalid

    def checkOut(self):
        if (self.out != invalid):
            return True
        
        return False
    
    def getOut(self):
        return self.out