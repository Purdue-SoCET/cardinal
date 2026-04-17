from bits import Bits
from hardware_lib import vertexTable, buffer, Table
from base_class import ForwardingIF, LatchIF, Stage
'''
#Can hold worst case 8 triangles in flight (8 * 3 vert = 24)
vertex_table = vertexTable(size = 24, blockSize = 8*12)

#Translation lookup table with 11 slots and indexing the size 24 vertex table so 5 bits ok
tl_table = Table(size = 11, dataSize = 5)
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

        if input_data is None:
            return

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

def setup_stage():
    in_latchV = LatchIF(name="vBuffer_inLatch")
    out_latchV = LatchIF(name="vBuffer_outLatch")
    in_latchI = LatchIF(name="iBuffer_inLatch")
    out_latchI = LatchIF(name="iBuffer_outLatch")

    vBuffer = vertexBuffer(name="vBuffer", input_if=in_latchV, output_if=out_latchV)
    iBuffer = indexBuffer(name="iBuffer", input_if=in_latchI, output_if=out_latchI)

    return vBuffer, iBuffer, in_latchV, out_latchV, in_latchI, out_latchI

def test_stage():
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
            in_latchI.push(iData[cycle])

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
    test_stage()
    

if __name__ == "__main__":
    main()