import struct

class Bits():
    def __init__(self, size : int = 32, val = '0', mode : str = 'little'): #mode 0 is little, mode 1 is big
        self.size = size
        self.mode = mode #Endianness 

        if (mode != 'little' or mode != 'big'):
            mode = 'little'

        #Auto convert from int32 or fp32
        if (isinstance(val, int)):
            val = format(val, 'b')
            if (mode == 'big'):
                val = val[::-1]
        elif (isinstance(val, float)):
            [bits] = struct.unpack('!I', struct.pack('!f', val))
            val = f"{bits:032b}"
            

        if (mode == 'little'):
            temp = val[::-1] #puts LSB at 0 and makes it python friendly
            if (len(val) < size):
                diff = size - len(val)
                for i in range(diff):
                    temp = ''.join([temp, "0"])
                val = temp[::-1]

        self.bits = val

    def getBits(self):
        return self.bits
    
    def getSize(self):
        return self.size

    def getInt(self):
        intCon = int(self.bits, 2)
        return intCon

    def getFloats(self):
        intCon = self.getInt()
        return struct.unpack('!f', struct.pack('!I', intCon))[0]

'''
val = '0001'
#val = val[::-1]
myBits = Bits(32, val)
print(myBits.getBits())
'''