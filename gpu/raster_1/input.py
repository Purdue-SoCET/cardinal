from bits import Bits
from hardware_lib import vertexTable, buffer, Table
from base_class import ForwardingIF, LatchIF, Stage

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
        self.size = 16

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
            status = input_data['wait']

            self.vertex_buffer.shift()

            if status is False:
                if self.vertex_buffer.checkOut() is True:
                    self.ahead_latch.push(self.vertex_buffer.getOut())
                    self.vertex_buffer.acked()
            '''if self.vertex_buffer.checkOut() is True:
                self.ahead_latch.push(self.vertex_buffer.getOut())
                self.vertex_buffer.acked()'''

class indexBuffer(Stage):
    def __init__(self, name: str, input_if: ForwardingIF, output_if: ForwardingIF):
        super().__init__(name, input_if, output_if)

        self.dSize = 4
        self.size = 32

        #index size = 10 bits, pack and send 8 triangle's worth
        self.index_buffer = buffer(size = self.size, dataSize = self.dSize)

    def compute(self):
        input_data = self.behind_latch.pop()

        if input_data is None:
            return

        if not isinstance(input_data, Bits):
            raise ValueError("iBuffer -> input not bits")
        
        if input_data.getSize() != self.dSize:
            raise ValueError(f"iBuffer -> input size incorrect should be {self.dSize}")
        
        self.index_buffer.insert(input_data)

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
        self.tl_table = Table(size = self.Tsize, dataSize = self.TdSize)

        #Can hold worst case 8 triangles in flight (8 * 3 vert = 24)
        self.vx_table = vertexTable(size = self.Vsize, blockSize = self.VdSize) #12 bytes

    def compute(self):
        vStatus = 'ok'
        tStatus = 'ok'

        if (self.Tcounter == self.Tsize - 1):
            tStatus = 'clean'

        if (self.Vcounter == self.Vsize - 1):
            self.Vcounter = -1

        input_data = self.behind_latch.pop()

        if input_data is None:
            return

        Vinput = input_data['vertex']
        Tinput = input_data['index']

        if Vinput is not None:
            self.Vcounter += 1
            if self.vx_table.checkValid(self.Vcounter).getBits() == '0':
                self.vx_table.insert(Vinput, self.Vcounter)
                self.vx_table.validate(self.Vcounter)
                self.vx_table.increment(self.Vcounter)
            else:
                vStatus = 'stall'

        if Tinput is not None and tStatus != 'clean':
            self.Tcounter += 1
            handle = self.vx_table.getHandle()
            if handle == -1:
                tStatus = 'stall'
            else:
                self.tl_table.insert(index=Tinput, data=Bits(size=self.TdSize, val=handle))



def setup_stage():
    in_latchV = LatchIF(name="vBuffer_inLatch")
    out_latchV = LatchIF(name="vBuffer_outLatch")
    in_latchI = LatchIF(name="iBuffer_inLatch")
    out_latchI = LatchIF(name="iBuffer_outLatch")

    vBuffer = vertexBuffer(name="vBuffer", input_if=in_latchV, output_if=out_latchV)
    iBuffer = indexBuffer(name="iBuffer", input_if=in_latchI, output_if=out_latchI)

    return vBuffer, iBuffer, in_latchV, out_latchV, in_latchI, out_latchI

def test_system():
    vBuffer, iBuffer, in_latchV, out_latchV, in_latchI, out_latchI = setup_stage()

    cycles = 35

    vDat = Bits(size=96, val='10101010101010101010101010101010101111')
    vData = [vDat] * 17

    iDat = Bits(size=4, val=2)
    iData = [iDat] * 33

    for cycle in range(cycles):
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
         
        if cycle < 16:
            print(f"Pushing data no.{cycle}")
            in_latchV.push({'wait' : wait, 'data' : vData[cycle]})
            in_latchI.push(iData[cycle])
        elif cycle < 33:
            in_latchV.push({'wait' : wait, 'data' : None})
            in_latchI.push(iData[cycle])
        elif cycle < 40:
            in_latchV.push({'wait' : wait, 'data' : None})

        outI = out_latchI.pop()
        if wait is False:
            outV = out_latchV.pop()
        else:
            outV = None

        if outI is not None:
            print(f"Got out index data on cycle {cycle}")
        if outV is not None:
            print(f"Got out vertex data on cycle {cycle}")

        vBuffer.compute()
        iBuffer.compute()
        print()

def main():
    test_system()
    

if __name__ == "__main__":
    main()