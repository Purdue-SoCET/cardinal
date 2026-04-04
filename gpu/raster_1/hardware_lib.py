from bits import Bits
from numpy import inf as invalid

def vertexTable():
    def __init__(self, size : int = 12, blockSize : int = 64):
        self.table = [Bits(blockSize)] * size
        self.refCount = [0] * size
        self.valid = [0] * size

    def insert(self, data, index):
        self.table[index] = data

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

def buffer():
    def __init__(self, size : int = 2, dataSize : int = 32):
        self.size = size
        self.currSize = 0
        self.dataSize = dataSize
        self.buffer = []
        self.out = invalid

    def insert(self, data : Bits):
        if (len(data.getBits()) != self.dataSize):
            return -1
        
        if (self.currSize < self.size):
            self.buffer.append(data)
        elif (self.currSize == self.size):
            if (self.out == invalid):
                self.out = self.buffer[self.size - 1]
            else:
                return -2
            
            self.buffer.remove(self.size - 1)
            self.buffer.append(data)

    def acked(self):
        self.out = invalid
