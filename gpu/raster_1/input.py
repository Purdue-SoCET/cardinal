from bits import Bits
from hardware_lib import vertexTable, buffer, translationTable
from base_class import ForwardingIF, LatchIF, Stage
import random as rand

'''
#Can hold worst case 8 triangles in flight (8 * 3 vert = 24)
vertex_table = vertexTable(size = 24, blockSize = 8*12) #12 bytes

#Translation lookup table with 16 slots (for every vertex in buffer) and indexing the size 24 vertex table so 5 bits ok
tl_table = Table(size = 16, dataSize = 5)
'''

class vertexBuffer(Stage):
    def __init__(self, name: str, input_if: ForwardingIF, output_if: ForwardingIF):
        super().__init__(name, input_if, output_if)

        self.dSize = 96
        self.size = 15 #0 index

        #INT16 + INT16 (x, y) | INT32 (vertID addr) | FP32 (z value) = 96
        self.vertex_buffer = buffer(size = self.size, dataSize = self.dSize) 

    def compute(self):
        input_data = self.behind_latch.pop()

        if input_data is not None and input_data['data'] is not None:
            wait = input_data['wait']
            input_data = input_data['data']

            if not isinstance(input_data, Bits):
                raise ValueError("vBuffer -> input not bits")
            
            if input_data.getSize() != self.dSize:
                raise ValueError(f"vBuffer -> input size incorrect should be {self.dSize}")
            
            if wait is False:
                self.vertex_buffer.insert(input_data)
                if self.vertex_buffer.checkOut() is True:
                    self.ahead_latch.push(self.vertex_buffer.getOut())
                    self.vertex_buffer.acked()
        elif input_data is not None:
            wait = input_data['wait']

            if wait is False:
                self.vertex_buffer.shift()

                if self.vertex_buffer.checkOut() is True:
                    self.ahead_latch.push(self.vertex_buffer.getOut())
                    self.vertex_buffer.acked()

class indexBuffer(Stage):
    def __init__(self, name: str, input_if: ForwardingIF, output_if: ForwardingIF):
        super().__init__(name, input_if, output_if)

        self.dSize = 4
        self.size = 31 #0 index

        #index size = 10 bits, pack and send 8 triangle's worth
        self.index_buffer = buffer(size = self.size, dataSize = self.dSize)

    def compute(self):
        input_data = self.behind_latch.pop()

        if input_data is not None and input_data['data'] is not None:
            wait = input_data['wait']
            input_data = input_data['data']

            if not isinstance(input_data, Bits):
                raise ValueError("iBuffer -> input not bits")
            
            if input_data.getSize() != self.dSize:
                raise ValueError(f"iBuffer -> input size incorrect should be {self.dSize}")
            
            if wait is False:
                self.index_buffer.insert(input_data)
                if self.index_buffer.checkOut() is True:
                    self.ahead_latch.push(self.index_buffer.getOut())
                    self.index_buffer.acked()
        elif input_data is not None:
            wait = input_data['wait']

            if wait is False:
                self.index_buffer.shift()

                if self.index_buffer.checkOut() is True:
                    self.ahead_latch.push(self.index_buffer.getOut())
                    self.index_buffer.acked()

class vert_trans_table(Stage):
    def __init__(self, name: str, input_if: ForwardingIF, output_if: ForwardingIF):
        super().__init__(name, input_if, output_if)

        self.TdSize = 5
        self.Tsize = 16

        self.VdSize = 8*12
        self.Vsize = 24

        self.Tcounter = -1
        self.Vcounter = -1

        #Translation lookup table with 16 slots (for every vertex in buffer) and indexing the size 24 vertex table so 5 bits ok
        self.tl_table = translationTable(size = self.Tsize, blockSize = self.TdSize)

        #Can hold worst case 8 triangles in flight (8 * 3 vert = 24)
        self.vx_table = vertexTable(size = self.Vsize, blockSize = self.VdSize) #12 bytes

    def compute(self):
        vStatus = 'ok'
        tStatus = 'ok'

        if (self.Vcounter == self.Vsize - 1):
            self.Vcounter = -1

        input_data = self.behind_latch.pop()

        if input_data is None:
            #self.ahead_latch.push(None)
            return

        Vinput : Bits = input_data['vertex']
        Tinput : Bits = input_data['index']
        satStat : bool = input_data['satStat'] #trans table saturation stat

        if (satStat == True):
            tStatus = 'clean'

        if Tinput is not None and tStatus != 'clean':
            self.Tcounter += 1
            handle = self.vx_table.getHandle()
            if handle == -1:
                tStatus = 'stall' #stall on vertex table being full
            
            if tStatus != 'stall':
                valid = self.tl_table.checkValid(index=Tinput)

                if (valid == 1):
                    idx = self.tl_table.read(index=Tinput.getInt()).getInt()
                    vert : Bits = self.vx_table.read(index=idx)

                    if (((Vinput is not None and Vinput.getBits() == vert.getBits()) or (Vinput is None)) and self.vx_table.checkValid(idx).getBits() == '1'):
                        self.vx_table.increment(self.Vcounter)
                    else:
                        vStatus = 'stall' #stall on new packet detected
                else:
                    self.tl_table.insert(index=Tinput, data=Bits(size=self.TdSize, val=handle))

                    self.Vcounter += 1
                    if self.vx_table.checkValid(self.Vcounter).getBits() == '0':
                        self.vx_table.insert(Vinput, self.Vcounter)
                        self.vx_table.validate(self.Vcounter)
                        self.vx_table.increment(self.Vcounter)
                    else:
                        vStatus = 'stall' #stall on vertex table handle not ready yet

        outLoad = {'vStatus' : vStatus, 'tStatus' : tStatus}
        self.ahead_latch.push(outLoad)



def setup_stage():
    in_latchV = LatchIF(name="vBuffer_inLatch")
    out_latchV = LatchIF(name="vBuffer_outLatch")
    in_latchI = LatchIF(name="iBuffer_inLatch")
    out_latchI = LatchIF(name="iBuffer_outLatch")

    in_latchTLV = LatchIF(name="TLV_inLatch")
    out_latchTLV = LatchIF(name="TLV_outLatch")

    vBuffer = vertexBuffer(name="vBuffer", input_if=in_latchV, output_if=out_latchV)
    iBuffer = indexBuffer(name="iBuffer", input_if=in_latchI, output_if=out_latchI)
    tlv = vert_trans_table(name="TLV", input_if=in_latchTLV, output_if=out_latchTLV)

    return vBuffer, iBuffer, tlv, in_latchV, out_latchV, in_latchI, out_latchI, in_latchTLV, out_latchTLV

def test_system():
    vBuffer, iBuffer, tlv, in_latchV, out_latchV, in_latchI, out_latchI, in_latchTLV, out_latchTLV = setup_stage()

    cycles = 75

    vData = []

    for i in range(16):
        vDat = Bits(size=96, val=rand.randint(0,(2**96) - 1))
        vData.append(vDat)

    iData = []

    for i in range(20 + 1):
        iDat = Bits(size=4, val=rand.randint(0,(2**4) - 1))
        iData.append(iDat)

    for cycle in range(cycles + 1):
        adj_stall = 0
        stall = False
        checkSum = 0
        wait = False
        print(f"Cycle {cycle}:")

        if out_latchV.snoop() is not None:
            print(f"Ahead latch -> vertex: {out_latchV.snoop()}")

            if out_latchI.snoop() is not None:
                print(f"Ahead latch -> index: {out_latchI.snoop().getBits()}")
            else:
                print('Vert waiting for I')
                wait = True
        else:
            print(f"Ahead latch has data: {out_latchV.snoop()}")
         
        if out_latchTLV.snoop() is not None:
            tlv_status = out_latchTLV.pop()
            print(f"Trans Status -> {tlv_status['tStatus']} | Vertex Table Status -> {tlv_status['vStatus']}") 
            if (tlv_status['tStatus'] == 'stall' or tlv_status['vStatus'] == 'stall'):
                stall = True
                adj_stall += 1



        if cycle < 16 + adj_stall and stall != True:
            print(f"Pushing data no.{cycle}")
            in_latchV.push({'wait' : wait, 'data' : vData[cycle - adj_stall]})
            in_latchI.push({'wait' : False, 'data' : iData[cycle - adj_stall]})
        elif cycle < 20 + adj_stall and stall != True: #has to match no.elements in data packet you want to deal with
            in_latchV.push({'wait' : wait, 'data' : None})
            in_latchI.push({'wait' : False, 'data' : iData[cycle - adj_stall]})
        elif cycle < 33 + adj_stall and stall != True: #has to match size of buffer max
            in_latchV.push({'wait' : wait, 'data' : None})
            in_latchI.push({'wait' : False, 'data' : None})
        elif stall == True:
            in_latchV.push({'wait' : True, 'data' : None})
            in_latchI.push({'wait' : True, 'data' : None})
        else:
            in_latchV.push({'wait' : wait, 'data' : None})
            in_latchI.push({'wait' : wait, 'data' : None})

        outI = out_latchI.pop()
        if wait is False:
            outV = out_latchV.pop()
        else:
            outV = None

        if outI is not None:
            print(f"Got out index data on cycle {cycle}")
            checkSum += 1
        if outV is not None:
            print(f"Got out vertex data on cycle {cycle}")

        inLoad = {'vertex' : outV, 'index' : outI, 'satStat' : False}

        if (checkSum == 1):
            in_latchTLV.push(inLoad)
        else:
            inLoad['satStat'] = True
            in_latchTLV.push(inLoad)

        tlv.compute()
        vBuffer.compute()
        iBuffer.compute()
        print()

def main():
    test_system()
    

if __name__ == "__main__":
    main()