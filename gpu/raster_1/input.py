from bits import Bits
from hardware_lib import vertexTable, buffer

table = vertexTable(size = 12, blockSize = 8*8)
indexBuffer = buffer(size = 32, dataSize = 32)
vertexBuffer = buffer()