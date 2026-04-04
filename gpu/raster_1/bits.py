import struct

class Bits():
    def __init__(self, size : int = 32, val : str = '0', mode : int = 0): #mode 0 is big, mode 1 is little
        self.size = size
        self.mode = mode #Endianness 
        if (mode == 0):
            temp = val[::-1] #puts LSB at 0 and makes it python friendly
            if (len(val) < size):
                diff = size - len(val)
                for i in range(diff):
                    temp = ''.join([temp, "0"])
                val = temp[::-1]

        self.bits = val

    def getBits(self):
        return self.bits
    
    def getInt(self):
        intCon = int(self.bits, 2)
        return intCon

    def getFloats(self):
        intCon = self.getInt()
        return struct.unpack('!f', struct.pack('!I', intCon))[0]
'''
val = '01000000010010010000111111011011' #some digits of pi
#val = val[::-1]
myBits = Bits(32, val)
print(myBits.getBits())
'''