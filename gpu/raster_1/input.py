from bits import Bits
from hardware_lib import vertexTable, buffer

table = vertexTable(size = 24, blockSize = 8*12)

#index size = 10 bits, pack and send triangle's worth as 3 with 2 padded bit
indexBuffer = buffer(size = 32, dataSize = 10)

#INT16 + INT16 (x, y) | INT32 (vertID addr) | FP32 (z value) = 96
vertexBuffer = buffer(size = 11, dataSize = 96) 