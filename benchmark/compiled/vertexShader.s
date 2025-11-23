       section data
       global cos
       type cos func
       global ftoi
       type ftoi func
       global itof
       type itof func
       global sin
       type sin func
       global isqrt
       type isqrt func
       global threadIdx
       type threadIdx func
       global blockDim
       type blockDim func
       global blockIdx
       type blockIdx func
       section data
       section code
       global kernel_vertexShader
       type kernel_vertexShader func
 kernel_vertexShader:
       lui, x11, 255
       lmi, x11, 4093
       lli, x11, 2672
       add x2, x2, x11
       lui, x11, 0
       lmi, x11, 0
       lli, x11, 128
       add x11, x2, x11
       sw x1, 0(x11)
       sw x8, 0(x2)
       lui, x11, 0
       lmi, x11, 0
       lli, x11, 256
       add x8, x2, x11
       sw x9, 0(x8)
 kernel_vertexShader_block0:
       jal x0, kernel_vertexShader_block1
 kernel_vertexShader_block1:
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 512
       add x11, x8, x11
       sw x12, 0(x11)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 512
       add x11, x8, x11
       lw x9, 0(x11)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       sw x9, 0(x11)
       csrr x11, 2
       csrr x10, 3
       csrr x9, 1
       mul x10, x11, x10
       add x9, x10, x9
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       sw x9, 0(x11)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       lui, x10, 0
       lmi, x10, 0
       lli, x10, 1023
       blt 1, x10, x9, 0
       bge 2, x10, x9, 0
       jal x0, kernel_vertexShader_block3
 kernel_vertexShader_block2:
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       lui, x10, 0
       lmi, x10, 0
       lli, x10, 1023
       beq 1, x10, x9, 0
       bne 2, x10, x9, 0
       jal x0, kernel_vertexShader_block6
 kernel_vertexShader_block3:
       jal x0, kernel_vertexShader_epilog
 kernel_vertexShader_block5:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4036
       add x10, x8, x9
       lui, x9, 0
       lmi, x9, 0
       lli, x9, 0
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4036
       add x9, x8, x9
       addi x9, x9, 4
       lui, x10, 0
       lmi, x10, 0
       lli, x10, 0
       sw x10, 0(x9)
       addi x9, x9, 4
       lui, x10, 0
       lmi, x10, 0
       lli, x10, 0
       sw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4036
       add x11, x8, x9
       addi x10, x0, 1
       addi x9, x0, 4
       mul x9, x10, x9
       add x10, x11, x9
       lui, x9, 63
       lmi, x9, 2048
       lli, x9, 0
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4036
       add x11, x8, x9
       addi x10, x0, 1
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x13, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 4
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x11, x0, 3
       mul x9, x11, x9
       addi x11, x9, 2
       addi x9, x0, 4
       mul x9, x11, x9
       add x9, x10, x9
       lw x12, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4036
       add x11, x8, x9
       addi x10, x0, 2
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 4
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x14, x0, 3
       mul x9, x14, x9
       addi x14, x9, 1
       addi x9, x0, 4
       mul x9, x14, x9
       add x9, x10, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4048
       add x15, x8, x10
       addi x14, x0, 0
       addi x10, x0, 4
       mul x10, x14, x10
       add x14, x15, x10
       mulf x10, x13, x12
       mulf x9, x11, x9
       subf x9, x10, x9
       sw x9, 0(x14)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4036
       add x11, x8, x9
       addi x10, x0, 2
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x13, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 4
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x11, x0, 3
       mul x11, x11, x9
       addi x9, x0, 4
       mul x9, x11, x9
       add x9, x10, x9
       lw x12, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4036
       add x11, x8, x9
       addi x10, x0, 0
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 4
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x14, x0, 3
       mul x9, x14, x9
       addi x14, x9, 2
       addi x9, x0, 4
       mul x9, x14, x9
       add x9, x10, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4048
       add x15, x8, x10
       addi x14, x0, 1
       addi x10, x0, 4
       mul x10, x14, x10
       add x14, x15, x10
       mulf x10, x13, x12
       mulf x9, x11, x9
       subf x9, x10, x9
       sw x9, 0(x14)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4036
       add x11, x8, x9
       addi x10, x0, 0
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x13, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 4
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x11, x0, 3
       mul x9, x11, x9
       addi x11, x9, 1
       addi x9, x0, 4
       mul x9, x11, x9
       add x9, x10, x9
       lw x12, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4036
       add x11, x8, x9
       addi x10, x0, 1
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 4
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x14, x0, 3
       mul x14, x14, x9
       addi x9, x0, 4
       mul x9, x14, x9
       add x9, x10, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4048
       add x15, x8, x10
       addi x14, x0, 2
       addi x10, x0, 4
       mul x10, x14, x10
       add x14, x15, x10
       mulf x10, x13, x12
       mulf x9, x11, x9
       subf x9, x10, x9
       sw x9, 0(x14)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 0
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x13, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 0
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x12, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 1
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x14, x8, x9
       addi x11, x0, 1
       addi x9, x0, 4
       mul x9, x11, x9
       add x9, x14, x9
       lw x9, 0(x9)
       lui, x11, 255
       lmi, x11, 4095
       lli, x11, 4048
       add x15, x8, x11
       addi x14, x0, 2
       addi x11, x0, 4
       mul x11, x14, x11
       add x11, x15, x11
       lw x11, 0(x11)
       mulf x12, x13, x12
       mulf x9, x10, x9
       addf x10, x12, x9
       jal x0, kernel_vertexShader_splitted_block_1
 kernel_vertexShader_block6:
       jal x0, kernel_vertexShader_epilog
 kernel_vertexShader_block8:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4028
       add x9, x8, x9
       lw x9, 0(x9)
       addi x10, x0, 3
       blt 0, x9, x10
       jal x0, kernel_vertexShader_block9
 kernel_vertexShader_block9:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4028
       add x9, x8, x9
       lw x11, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4028
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4048
       add x12, x8, x10
       addi x10, x0, 4
       mul x9, x9, x10
       add x9, x12, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4032
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x12, 255
       lmi, x12, 4095
       lli, x12, 4048
       add x13, x8, x12
       addi x12, x0, 4
       mul x11, x11, x12
       add x11, x13, x11
       mulf x9, x10, x9
       sw x9, 0(x11)
       jal x0, kernel_vertexShader_block11
 kernel_vertexShader_block10:
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 4
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x11, x0, 3
       mul x11, x11, x9
       addi x9, x0, 4
       mul x9, x11, x9
       add x9, x10, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4048
       add x12, x8, x10
       addi x11, x0, 3
       addi x10, x0, 4
       mul x10, x11, x10
       add x10, x12, x10
       sw x9, 0(x10)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 4
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x11, x0, 3
       mul x9, x11, x9
       addi x11, x9, 1
       addi x9, x0, 4
       mul x9, x11, x9
       add x9, x10, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4048
       add x12, x8, x10
       addi x11, x0, 4
       addi x10, x0, 4
       mul x10, x11, x10
       add x10, x12, x10
       sw x9, 0(x10)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 4
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x11, x0, 3
       mul x9, x11, x9
       addi x11, x9, 2
       addi x9, x0, 4
       mul x9, x11, x9
       add x9, x10, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4048
       add x12, x8, x10
       addi x11, x0, 5
       addi x10, x0, 4
       mul x10, x11, x10
       add x10, x12, x10
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 1
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x12, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 5
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x11, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x13, x8, x9
       addi x10, x0, 2
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x13, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x14, x8, x9
       addi x13, x0, 4
       addi x9, x0, 4
       mul x9, x13, x9
       add x9, x14, x9
       lw x9, 0(x9)
       lui, x13, 255
       lmi, x13, 4095
       lli, x13, 4048
       add x15, x8, x13
       addi x14, x0, 6
       addi x13, x0, 4
       mul x13, x14, x13
       add x13, x15, x13
       mulf x11, x12, x11
       mulf x9, x10, x9
       subf x9, x11, x9
       sw x9, 0(x13)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 2
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x12, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 3
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x11, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x13, x8, x9
       addi x10, x0, 0
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x13, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x14, x8, x9
       addi x13, x0, 5
       addi x9, x0, 4
       mul x9, x13, x9
       add x9, x14, x9
       lw x9, 0(x9)
       lui, x13, 255
       lmi, x13, 4095
       lli, x13, 4048
       add x15, x8, x13
       addi x14, x0, 7
       addi x13, x0, 4
       mul x13, x14, x13
       add x13, x15, x13
       mulf x11, x12, x11
       mulf x9, x10, x9
       subf x9, x11, x9
       sw x9, 0(x13)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 0
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x12, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 4
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x11, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x13, x8, x9
       addi x10, x0, 1
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x13, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x14, x8, x9
       addi x13, x0, 3
       addi x9, x0, 4
       mul x9, x13, x9
       add x9, x14, x9
       lw x9, 0(x9)
       lui, x13, 255
       lmi, x13, 4095
       lli, x13, 4048
       add x15, x8, x13
       addi x14, x0, 8
       addi x13, x0, 4
       mul x13, x14, x13
       add x13, x15, x13
       mulf x11, x12, x11
       mulf x9, x10, x9
       subf x9, x11, x9
       sw x9, 0(x13)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 3
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x14, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 3
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x13, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 4
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x12, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 4
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x11, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x15, x8, x9
       addi x10, x0, 5
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x15, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x16, x8, x9
       addi x15, x0, 5
       addi x9, x0, 4
       mul x9, x15, x9
       add x9, x16, x9
       lw x9, 0(x9)
       mulf x13, x14, x13
       mulf x11, x12, x11
       addf x11, x13, x11
       mulf x9, x10, x9
       addf x9, x11, x9
       isqrt x9, x9
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4032
       add x10, x8, x10
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_splitted_block_2
 kernel_vertexShader_block11:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4028
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4028
       add x10, x8, x10
       addi x9, x9, 1
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4028
       add x9, x8, x9
       lw x9, 0(x9)
       jpnz p0, kernel_vertexShader_block10
       jal x0, kernel_vertexShader_block8
 kernel_vertexShader_block12:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4024
       add x9, x8, x9
       lw x9, 0(x9)
       addi x10, x0, 6
       blt 0, x9, x10
       jal x0, kernel_vertexShader_block13
 kernel_vertexShader_block13:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4024
       add x9, x8, x9
       lw x11, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4024
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4048
       add x12, x8, x10
       addi x10, x0, 4
       mul x9, x9, x10
       add x9, x12, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4032
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x12, 255
       lmi, x12, 4095
       lli, x12, 4048
       add x13, x8, x12
       addi x12, x0, 4
       mul x11, x11, x12
       add x11, x13, x11
       mulf x9, x10, x9
       sw x9, 0(x11)
       jal x0, kernel_vertexShader_block15
 kernel_vertexShader_block14:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 6
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x14, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 6
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x13, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 7
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x12, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x11, x8, x9
       addi x10, x0, 7
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x11, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x15, x8, x9
       addi x10, x0, 8
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x15, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x16, x8, x9
       addi x15, x0, 8
       addi x9, x0, 4
       mul x9, x15, x9
       add x9, x16, x9
       lw x9, 0(x9)
       mulf x13, x14, x13
       mulf x11, x12, x11
       addf x11, x13, x11
       mulf x9, x10, x9
       addf x9, x11, x9
       isqrt x9, x9
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4032
       add x10, x8, x10
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4020
       add x10, x8, x9
       addi x9, x0, 6
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block16
 kernel_vertexShader_block15:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4024
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4024
       add x10, x8, x10
       addi x9, x9, 1
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4024
       add x9, x8, x9
       lw x9, 0(x9)
       jpnz p0, kernel_vertexShader_block14
       jal x0, kernel_vertexShader_block12
 kernel_vertexShader_block16:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4020
       add x9, x8, x9
       lw x9, 0(x9)
       addi x10, x0, 9
       blt 0, x9, x10
       jal x0, kernel_vertexShader_block17
 kernel_vertexShader_block17:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4020
       add x9, x8, x9
       lw x11, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4020
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4048
       add x12, x8, x10
       addi x10, x0, 4
       mul x9, x9, x10
       add x9, x12, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4032
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x12, 255
       lmi, x12, 4095
       lli, x12, 4048
       add x13, x8, x12
       addi x12, x0, 4
       mul x11, x11, x12
       add x11, x13, x11
       mulf x9, x10, x9
       sw x9, 0(x11)
       jal x0, kernel_vertexShader_block19
 kernel_vertexShader_block18:
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 12
       lw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x12, x0, 3
       mul x12, x12, x9
       addi x9, x0, 4
       mul x9, x12, x9
       add x9, x11, x9
       lw x12, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 0
       lw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x13, x0, 3
       mul x13, x13, x9
       addi x9, x0, 4
       mul x9, x13, x9
       add x9, x11, x9
       lw x9, 0(x9)
       lui, x11, 255
       lmi, x11, 4095
       lli, x11, 4008
       add x11, x8, x11
       subf x9, x12, x9
       sw x9, 0(x11)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 12
       lw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x12, x0, 3
       mul x9, x12, x9
       addi x12, x9, 1
       addi x9, x0, 4
       mul x9, x12, x9
       add x9, x11, x9
       lw x12, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 0
       lw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x13, x0, 3
       mul x9, x13, x9
       addi x13, x9, 1
       addi x9, x0, 4
       mul x9, x13, x9
       add x9, x11, x9
       lw x9, 0(x9)
       lui, x11, 255
       lmi, x11, 4095
       lli, x11, 4008
       add x11, x8, x11
       addi x13, x11, 4
       subf x9, x12, x9
       sw x9, 0(x13)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 12
       lw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x12, x0, 3
       mul x9, x12, x9
       addi x12, x9, 2
       addi x9, x0, 4
       mul x9, x12, x9
       add x9, x11, x9
       lw x12, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 0
       lw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x14, x0, 3
       mul x9, x14, x9
       addi x14, x9, 2
       addi x9, x0, 4
       mul x9, x14, x9
       add x9, x11, x9
       lw x11, 0(x9)
       addi x9, x13, 4
       subf x11, x12, x11
       sw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 8
       lw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x12, x0, 4
       mul x9, x9, x12
       add x9, x11, x9
       lw x9, 0(x9)
       cos x9, x9
       lui, x11, 255
       lmi, x11, 4095
       lli, x11, 3972
       add x11, x8, x11
       sw x9, 0(x11)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3972
       add x9, x8, x9
       addi x12, x9, 4
       addi x9, x0, 0
       itof x9, x9
       sw x9, 0(x12)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 8
       lw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x13, x0, 4
       mul x9, x9, x13
       add x9, x11, x9
       lw x9, 0(x9)
       sin x9, x9
       addi x11, x12, 4
       sw x9, 0(x11)
       addi x9, x11, 4
       addi x11, x0, 0
       itof x11, x11
       sw x11, 0(x9)
       addi x9, x9, 4
       addi x11, x0, 1
       itof x11, x11
       sw x11, 0(x9)
       addi x13, x9, 4
       addi x9, x0, 0
       itof x9, x9
       sw x9, 0(x13)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 8
       lw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x12, x0, 4
       mul x9, x9, x12
       add x9, x11, x9
       lw x9, 0(x9)
       sin x12, x9
       addi x9, x13, 4
       global float32_neg
       jal x1, float32_neg
       sw x10, 0(x9)
       addi x11, x9, 4
       addi x9, x0, 0
       itof x9, x9
       sw x9, 0(x11)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 8
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x12, x0, 4
       mul x9, x9, x12
       add x9, x10, x9
       lw x9, 0(x9)
       cos x9, x9
       addi x10, x11, 4
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3932
       add x10, x8, x9
       addi x9, x0, 0
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block20
 kernel_vertexShader_block19:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4020
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4020
       add x10, x8, x10
       addi x9, x9, 1
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4020
       add x9, x8, x9
       lw x9, 0(x9)
       jpnz p0, kernel_vertexShader_block18
       jal x0, kernel_vertexShader_block16
 kernel_vertexShader_block20:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3932
       add x9, x8, x9
       lw x9, 0(x9)
       addi x10, x0, 3
       blt 0, x9, x10
       jal x0, kernel_vertexShader_block21
 kernel_vertexShader_block21:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3928
       add x10, x8, x9
       addi x9, x0, 0
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block24
 kernel_vertexShader_block22:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3916
       add x10, x8, x9
       addi x9, x0, 0
       itof x9, x9
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3916
       add x9, x8, x9
       addi x9, x9, 4
       addi x10, x0, 0
       itof x10, x10
       sw x10, 0(x9)
       addi x9, x9, 4
       addi x10, x0, 0
       itof x10, x10
       sw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3912
       add x10, x8, x9
       addi x9, x0, 0
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block28
 kernel_vertexShader_block23:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3932
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3932
       add x10, x8, x10
       addi x9, x9, 1
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3932
       add x9, x8, x9
       lw x9, 0(x9)
       jpnz p0, kernel_vertexShader_block22
       jal x0, kernel_vertexShader_block20
 kernel_vertexShader_block24:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3928
       add x9, x8, x9
       lw x9, 0(x9)
       addi x10, x0, 3
       blt 0, x9, x10
       jal x0, kernel_vertexShader_block25
 kernel_vertexShader_block25:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3928
       add x9, x8, x9
       lw x12, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3932
       add x9, x8, x9
       lw x11, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3932
       add x9, x8, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3928
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x13, 255
       lmi, x13, 4095
       lli, x13, 4048
       add x14, x8, x13
       addi x13, x0, 3
       mul x10, x10, x13
       add x10, x10, x9
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x14, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3936
       add x13, x8, x10
       addi x10, x0, 3
       mul x10, x12, x10
       add x11, x10, x11
       addi x10, x0, 4
       mul x10, x11, x10
       add x10, x13, x10
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block27
 kernel_vertexShader_block26:
       jal x0, kernel_vertexShader_block23
 kernel_vertexShader_block27:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3928
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3928
       add x10, x8, x10
       addi x9, x9, 1
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3928
       add x9, x8, x9
       lw x9, 0(x9)
       jpnz p0, kernel_vertexShader_block26
       jal x0, kernel_vertexShader_block24
 kernel_vertexShader_block28:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3912
       add x9, x8, x9
       lw x9, 0(x9)
       addi x10, x0, 3
       blt 0, x9, x10
       jal x0, kernel_vertexShader_block29
 kernel_vertexShader_block29:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3908
       add x10, x8, x9
       addi x9, x0, 0
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block32
 kernel_vertexShader_block30:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3896
       add x10, x8, x9
       addi x9, x0, 0
       itof x9, x9
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3896
       add x9, x8, x9
       addi x9, x9, 4
       addi x10, x0, 0
       itof x10, x10
       sw x10, 0(x9)
       addi x9, x9, 4
       addi x10, x0, 0
       itof x10, x10
       sw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3892
       add x10, x8, x9
       addi x9, x0, 0
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block36
 kernel_vertexShader_block31:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3912
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3912
       add x10, x8, x10
       addi x9, x9, 1
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3912
       add x9, x8, x9
       lw x9, 0(x9)
       jpnz p0, kernel_vertexShader_block30
       jal x0, kernel_vertexShader_block28
 kernel_vertexShader_block32:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3908
       add x9, x8, x9
       lw x9, 0(x9)
       addi x10, x0, 3
       blt 0, x9, x10
       jal x0, kernel_vertexShader_block33
 kernel_vertexShader_block33:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3912
       add x9, x8, x9
       lw x13, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3908
       add x9, x8, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3912
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x11, 255
       lmi, x11, 4095
       lli, x11, 3936
       add x12, x8, x11
       addi x11, x0, 3
       mul x10, x10, x11
       add x10, x10, x9
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x12, x9
       lw x12, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3908
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4008
       add x11, x8, x10
       addi x10, x0, 4
       mul x9, x9, x10
       add x9, x11, x9
       lw x11, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3916
       add x10, x8, x9
       addi x9, x0, 4
       mul x9, x13, x9
       add x10, x10, x9
       lw x9, 0(x10)
       mulf x11, x12, x11
       addf x9, x9, x11
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block35
 kernel_vertexShader_block34:
       jal x0, kernel_vertexShader_block31
 kernel_vertexShader_block35:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3908
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3908
       add x10, x8, x10
       addi x9, x9, 1
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3908
       add x9, x8, x9
       lw x9, 0(x9)
       jpnz p0, kernel_vertexShader_block34
       jal x0, kernel_vertexShader_block32
 kernel_vertexShader_block36:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3892
       add x9, x8, x9
       lw x9, 0(x9)
       addi x10, x0, 3
       blt 0, x9, x10
       jal x0, kernel_vertexShader_block37
 kernel_vertexShader_block37:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3888
       add x10, x8, x9
       addi x9, x0, 0
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block40
 kernel_vertexShader_block38:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3876
       add x10, x8, x9
       addi x9, x0, 0
       itof x9, x9
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3876
       add x9, x8, x9
       addi x9, x9, 4
       addi x10, x0, 0
       itof x10, x10
       sw x10, 0(x9)
       addi x9, x9, 4
       addi x10, x0, 0
       itof x10, x10
       sw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3872
       add x10, x8, x9
       addi x9, x0, 0
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block44
 kernel_vertexShader_block39:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3892
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3892
       add x10, x8, x10
       addi x9, x9, 1
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3892
       add x9, x8, x9
       lw x9, 0(x9)
       jpnz p0, kernel_vertexShader_block38
       jal x0, kernel_vertexShader_block36
 kernel_vertexShader_block40:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3888
       add x9, x8, x9
       lw x9, 0(x9)
       addi x10, x0, 3
       blt 0, x9, x10
       jal x0, kernel_vertexShader_block41
 kernel_vertexShader_block41:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3892
       add x9, x8, x9
       lw x13, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3888
       add x9, x8, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3892
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x11, 255
       lmi, x11, 4095
       lli, x11, 3972
       add x12, x8, x11
       addi x11, x0, 3
       mul x10, x10, x11
       add x10, x10, x9
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x12, x9
       lw x12, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3888
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3916
       add x11, x8, x10
       addi x10, x0, 4
       mul x9, x9, x10
       add x9, x11, x9
       lw x11, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3896
       add x10, x8, x9
       addi x9, x0, 4
       mul x9, x13, x9
       add x10, x10, x9
       lw x9, 0(x10)
       mulf x11, x12, x11
       addf x9, x9, x11
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block43
 kernel_vertexShader_block42:
       jal x0, kernel_vertexShader_block39
 kernel_vertexShader_block43:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3888
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3888
       add x10, x8, x10
       addi x9, x9, 1
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3888
       add x9, x8, x9
       lw x9, 0(x9)
       jpnz p0, kernel_vertexShader_block42
       jal x0, kernel_vertexShader_block40
 kernel_vertexShader_block44:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3872
       add x9, x8, x9
       lw x9, 0(x9)
       addi x10, x0, 3
       blt 0, x9, x10
       jal x0, kernel_vertexShader_block45
 kernel_vertexShader_block45:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3868
       add x10, x8, x9
       addi x9, x0, 0
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block48
 kernel_vertexShader_block46:
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 16
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x11, x0, 3
       mul x11, x11, x9
       addi x9, x0, 4
       mul x9, x11, x9
       add x9, x10, x9
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 20
       lw x9, 0(x9)
       addi x12, x0, 0
       addi x11, x0, 4
       mul x11, x12, x11
       add x9, x9, x11
       lw x9, 0(x9)
       lui, x11, 255
       lmi, x11, 4095
       lli, x11, 3856
       add x11, x8, x11
       subf x9, x10, x9
       sw x9, 0(x11)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 16
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x11, x0, 3
       mul x9, x11, x9
       addi x11, x9, 1
       addi x9, x0, 4
       mul x9, x11, x9
       add x9, x10, x9
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 20
       lw x9, 0(x9)
       addi x12, x0, 1
       addi x11, x0, 4
       mul x11, x12, x11
       add x9, x9, x11
       lw x9, 0(x9)
       lui, x11, 255
       lmi, x11, 4095
       lli, x11, 3856
       add x11, x8, x11
       addi x12, x11, 4
       subf x9, x10, x9
       sw x9, 0(x12)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 16
       lw x10, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x9, 0(x11)
       addi x11, x0, 3
       mul x9, x11, x9
       addi x11, x9, 2
       addi x9, x0, 4
       mul x9, x11, x9
       add x9, x10, x9
       lw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 20
       lw x9, 0(x9)
       addi x13, x0, 2
       addi x10, x0, 4
       mul x10, x13, x10
       add x9, x9, x10
       lw x10, 0(x9)
       addi x9, x12, 4
       subf x10, x11, x10
       sw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3844
       add x10, x8, x9
       addi x9, x0, 0
       itof x9, x9
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3844
       add x9, x8, x9
       addi x9, x9, 4
       addi x10, x0, 0
       itof x10, x10
       sw x10, 0(x9)
       addi x9, x9, 4
       addi x10, x0, 0
       itof x10, x10
       sw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3840
       add x10, x8, x9
       addi x9, x0, 0
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block52
 kernel_vertexShader_block47:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3872
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3872
       add x10, x8, x10
       addi x9, x9, 1
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3872
       add x9, x8, x9
       lw x9, 0(x9)
       jpnz p0, kernel_vertexShader_block46
       jal x0, kernel_vertexShader_block44
 kernel_vertexShader_block48:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3868
       add x9, x8, x9
       lw x9, 0(x9)
       addi x10, x0, 3
       blt 0, x9, x10
       jal x0, kernel_vertexShader_block49
 kernel_vertexShader_block49:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3872
       add x9, x8, x9
       lw x13, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3868
       add x9, x8, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3872
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x11, 255
       lmi, x11, 4095
       lli, x11, 4048
       add x12, x8, x11
       addi x11, x0, 3
       mul x10, x10, x11
       add x10, x10, x9
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x12, x9
       lw x12, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3868
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3896
       add x11, x8, x10
       addi x10, x0, 4
       mul x9, x9, x10
       add x9, x11, x9
       lw x11, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3876
       add x10, x8, x9
       addi x9, x0, 4
       mul x9, x13, x9
       add x10, x10, x9
       lw x9, 0(x10)
       mulf x11, x12, x11
       addf x9, x9, x11
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block51
 kernel_vertexShader_block50:
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 16
       lw x15, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x14, 0(x11)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3872
       add x9, x8, x9
       lw x13, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3872
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3876
       add x11, x8, x10
       addi x10, x0, 4
       mul x9, x9, x10
       add x9, x11, x9
       lw x12, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 0
       lw x11, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x10, 0(x11)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3872
       add x9, x8, x9
       lw x9, 0(x9)
       addi x16, x0, 3
       mul x10, x16, x10
       add x10, x10, x9
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x9, 0(x9)
       addi x10, x0, 3
       mul x10, x14, x10
       add x11, x10, x13
       addi x10, x0, 4
       mul x10, x11, x10
       add x10, x15, x10
       addf x9, x12, x9
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block47
 kernel_vertexShader_block51:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3868
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3868
       add x10, x8, x10
       addi x9, x9, 1
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3868
       add x9, x8, x9
       lw x9, 0(x9)
       jpnz p0, kernel_vertexShader_block50
       jal x0, kernel_vertexShader_block48
 kernel_vertexShader_block52:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3840
       add x9, x8, x9
       lw x9, 0(x9)
       addi x10, x0, 3
       blt 0, x9, x10
       jal x0, kernel_vertexShader_block53
 kernel_vertexShader_block53:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3836
       add x10, x8, x9
       addi x9, x0, 0
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block56
 kernel_vertexShader_block54:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3844
       add x11, x8, x9
       addi x10, x0, 2
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x9, 0(x9)
       lui, x10, 0
       lmi, x10, 0
       lli, x10, 0
       blt 1, x9, x10, 0
       bge 2, x9, x10, 0
       jal x0, kernel_vertexShader_block61
 kernel_vertexShader_block55:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3840
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3840
       add x10, x8, x10
       addi x9, x9, 1
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3840
       add x9, x8, x9
       lw x9, 0(x9)
       jpnz p0, kernel_vertexShader_block54
       jal x0, kernel_vertexShader_block52
 kernel_vertexShader_block56:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3836
       add x9, x8, x9
       lw x9, 0(x9)
       addi x10, x0, 3
       blt 0, x9, x10
       jal x0, kernel_vertexShader_block57
 kernel_vertexShader_block57:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3840
       add x9, x8, x9
       lw x13, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3836
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3856
       add x11, x8, x10
       addi x10, x0, 4
       mul x9, x9, x10
       add x9, x11, x9
       lw x12, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 24
       lw x11, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3836
       add x9, x8, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3840
       add x9, x8, x9
       lw x9, 0(x9)
       addi x14, x0, 3
       mul x10, x10, x14
       add x10, x10, x9
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x11, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3844
       add x10, x8, x9
       addi x9, x0, 4
       mul x9, x13, x9
       add x10, x10, x9
       lw x9, 0(x10)
       mulf x11, x12, x11
       addf x9, x9, x11
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block59
 kernel_vertexShader_block58:
       jal x0, kernel_vertexShader_block55
 kernel_vertexShader_block59:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3836
       add x9, x8, x9
       lw x9, 0(x9)
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3836
       add x10, x8, x10
       addi x9, x9, 1
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3836
       add x9, x8, x9
       lw x9, 0(x9)
       jpnz p0, kernel_vertexShader_block58
       jal x0, kernel_vertexShader_block56
 kernel_vertexShader_block60:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3844
       add x11, x8, x9
       addi x10, x0, 2
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x11, x9
       lw x9, 0(x9)
       lui, x10, 0
       lmi, x10, 0
       lli, x10, 0
       beq 1, x9, x10, 0
       bne 2, x9, x10, 0
       jal x0, kernel_vertexShader_block64
 kernel_vertexShader_block61:
       jal x0, kernel_vertexShader_epilog
 kernel_vertexShader_block63:
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 28
       lw x12, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x11, 0(x11)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3844
       add x13, x8, x9
       addi x10, x0, 0
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x13, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3844
       add x14, x8, x9
       addi x13, x0, 2
       addi x9, x0, 4
       mul x9, x13, x9
       add x9, x14, x9
       lw x9, 0(x9)
       addi x13, x0, 3
       mul x13, x13, x11
       addi x11, x0, 4
       mul x11, x13, x11
       add x11, x12, x11
       divf x9, x10, x9
       sw x9, 0(x11)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 28
       lw x12, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x11, 0(x11)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3844
       add x13, x8, x9
       addi x10, x0, 1
       addi x9, x0, 4
       mul x9, x10, x9
       add x9, x13, x9
       lw x10, 0(x9)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 3844
       add x14, x8, x9
       addi x13, x0, 2
       addi x9, x0, 4
       mul x9, x13, x9
       add x9, x14, x9
       lw x9, 0(x9)
       addi x13, x0, 3
       mul x11, x13, x11
       addi x13, x11, 1
       addi x11, x0, 4
       mul x11, x13, x11
       add x11, x12, x11
       divf x9, x10, x9
       sw x9, 0(x11)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 384
       add x11, x8, x11
       lw x9, 0(x11)
       addi x9, x9, 28
       lw x12, 0(x9)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 256
       add x11, x8, x11
       lw x11, 0(x11)
       addi x9, x0, 1
       itof x9, x9
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 3844
       add x14, x8, x10
       addi x13, x0, 2
       addi x10, x0, 4
       mul x10, x13, x10
       add x10, x14, x10
       lw x10, 0(x10)
       addi x13, x0, 3
       mul x11, x13, x11
       addi x13, x11, 2
       addi x11, x0, 4
       mul x11, x13, x11
       add x11, x12, x11
       divf x9, x9, x10
       sw x9, 0(x11)
       jal x0, kernel_vertexShader_epilog
 kernel_vertexShader_block64:
       jal x0, kernel_vertexShader_epilog
 kernel_vertexShader_splitted_block_1:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4048
       add x13, x8, x9
       addi x12, x0, 2
       addi x9, x0, 4
       mul x9, x12, x9
       add x9, x13, x9
       lw x9, 0(x9)
       mulf x9, x11, x9
       addf x9, x10, x9
       isqrt x9, x9
       lui, x10, 255
       lmi, x10, 4095
       lli, x10, 4032
       add x10, x8, x10
       sw x9, 0(x10)
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4028
       add x10, x8, x9
       addi x9, x0, 0
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block8
 kernel_vertexShader_splitted_block_2:
       lui, x9, 255
       lmi, x9, 4095
       lli, x9, 4024
       add x10, x8, x9
       addi x9, x0, 3
       sw x9, 0(x10)
       jal x0, kernel_vertexShader_block12
 kernel_vertexShader_epilog:
       lw x9, 0(x8)
       lui, x11, 0
       lmi, x11, 0
       lli, x11, 128
       add x11, x2, x11
       lw x1, 0(x11)
       lw x8, 0(x2)
       lui, x11, 0
       lmi, x11, 2
       lli, x11, 1424
       add x2, x2, x11
       jalr x0,x1, 0
       .align 4
