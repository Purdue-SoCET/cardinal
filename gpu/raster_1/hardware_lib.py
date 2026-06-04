from bits import Bits

class Table():
    def __init__(self, size : int = 12, blockSize : int = 64):
        self.table = [Bits(blockSize)] * size

    def insert(self, data, index):
        if isinstance(index, int):
            self.table[index] = data
        elif isinstance(index, Bits):
            self.table[index.getInt()] = data

    def read(self, index):
        return self.table[index]

#NEED SPECIAL TRANS TABLE CLASS NEED VALID BIT!!

class translationTable(Table):
    def __init__(self, size : int = 12, blockSize : int = 64):
        super().__init__(size, blockSize)
        self.valid = [Bits(size = 1)] * size

    def checkValid(self, index : Bits):
        idx = index.getInt()
        valid : Bits = self.valid[idx]

        return valid.getInt()
    
    def insert(self, data, index : Bits):
        super().insert(data, index)
        self.valid[index.getInt()] = Bits(size=1, val='1')

    

class vertexTable(Table):
    def __init__(self, size : int = 12, blockSize : int = 64):
        super().__init__(size, blockSize)
        self.refCount = [Bits(size = 5)] * size
        self.valid = [Bits(size = 1)] * size

    def getHandle(self): #FOR TRANS TABLE ONLY!!
        for idx, v in enumerate(self.valid):
            if v.getBits() == '0':
                return idx
            
        return -1

    def getRefCount(self, index):
        return self.refCount[index]
    
    def validate(self, index):
        self.valid[index] = Bits(size=1, val=1)
    
    def invalidate(self, index):
        self.valid[index] = Bits(size=1)

    def increment(self, index):
        self.refCount[index] = Bits(size=5, val=self.refCount[index].getInt() + 1)

    def decrement(self, index):
        self.refCount[index] = Bits(size=5, val=self.refCount[index].getInt() - 1)

    def checkValid(self, index):
        return self.valid[index]


class buffer():
    def __init__(self, size : int = 2, dataSize : int = 32):
        self.size = size
        self.currSize = 0
        self.dataSize = dataSize
        self.buffer = []
        self.out = None

    def insert(self, data : Bits):
        if (data.getSize() != self.dataSize):
            return -1 #Bit width mismatch
        
        if (self.currSize < self.size):
            self.buffer.append(data)
            self.currSize += 1
        elif (self.currSize == self.size):
            if (self.out == None):
                self.out = self.buffer.pop(0)
                self.buffer.append(data) #append and pop together so no change in currSize.
                return 0
            else:
                return -2 #Output has not yet been acknowledged, so nothing doing
        else:
            return -3 #This should not be possible!

        if (self.currSize == self.size):
            self.out = self.buffer[0]
        
        return 0

    def shift(self):
        if (self.out == None and len(self.buffer) != 0 and self.currSize == self.size):
            self.out = self.buffer.pop(0)
            self.buffer.append(None)
            return 0
        elif (self.currSize != self.size):
            self.currSize += 1
            self.buffer.append(None)

        return 1

    def acked(self):
        self.out = None

    def checkOut(self):
        if (self.out != None):
            return True
        
        return False
    
    def getOut(self):
        return self.out