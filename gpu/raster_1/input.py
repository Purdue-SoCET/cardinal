from bits import Bits
from hardware_lib import vertexTable, buffer, Table

#Can hold worst case 8 triangles in flight (8 * 3 vert = 24)
vertex_table = vertexTable(size = 24, blockSize = 8*12)

#index size = 10 bits, pack and send 8 triangle's worth
index_buffer = buffer(size = 32, dataSize = 4)

#INT16 + INT16 (x, y) | INT32 (vertID addr) | FP32 (z value) = 96
vertex_buffer = buffer(size = 16, dataSize = 96) 

#Translation lookup table with 11 slots and indexing the size 24 vertex table so 5 bits ok
tl_table = Table(size = 11, dataSize = 5)