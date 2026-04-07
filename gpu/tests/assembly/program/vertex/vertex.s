# constants
lli x31, 128
lli x32, 32

lli x33, 0x7f # 1.0
slli x33, x33, 23
# sp setup

# entry
csrr x10, 3 # *argPtr
csrr x11, 0 # tid
csrr x12, 1 # bid
csrr x13, 2 # bdim
mul x12, x12, x13
add x11, x11, x12 # global_tid (i)

# args->a_dist->x squared, args->a_dist->y squared
lw x20, 4(x10) # *a_dist
lw x40, 0(x20) # x
mulf x43, x40, x40 # x^2
lw x41, 4(x20) # y
mulf x44, x41, x41 # y^2
# x^2 < y^2
sltf x42, x43, x44
bne 1, x42, x0, 0 # x^2 < y^2

add x60, x0, x0 # selAxis[0] = 0.0 init
add x61, x0, x0 # selAxis[1] = 0.0 init
addf x60, x0, x33, 1 # PRED selAxis[0] = 1.0
addf x61, x0, x33 # selAxis[1] = 1.0 UNCONDITIONAL
add x62, x0, x0 # selAxis[2] = 0.0

# args->a_dist->x (x40) ,y (x41), z
lw x42, 8(x20) # z
# lcs[0-2]
mulf x7, x61, x42 # selAxis[1] * z
mulf x8, x62, x41 # selAxis[2] * y
subf x50, x7, x8 # lcs[0] 

mulf x7, x62, x40 # selAxis[2] * x
mulf x8, x60, x42 # selAxis[0] * z
subf x51, x7, x8 # lcs[1]

mulf x7, x60, x41 # selAxis[0] * y
mulf x8, x61, x40 # selAxis[1] * x
subf x52, x7, x8 # lcs [2]

# norm/isqrt
mulf x7, x50, x50
mulf x8, x51, x51
mulf x9, x52, x52
addf x7, x7, x8
addf x7, x7, x9
isqrt x12, x7 # inv_lcs_dist

# 1st for loop
mulf x50, x50, x12 # lcs[0,1,2] = lcs[0,1,2] * inv_lcs_dist
mulf x51, x51, x12
mulf x52, x52, x12

addf x53, x0, x40 # lcs[3] = x
addf x54, x0, x41 # lcs[4] = y
addf x55, x0, x42 # lcs[5] = z

# lcs[6,7,8]
mulf x7, x51, x55 # lcs[1] * lcs[5]
mulf x8, x52, x54 # lcs[2] * lcs[4]
subf x56, x7, x8 # lcs[6]

mulf x7, x52, x53
mulf x8, x50, x55
subf x57, x7, x8

mulf x7, x50, x54
mulf x8, x51, x53
subf x58, x7, x8

# new inv_lcs_dist
mulf x7, x53, x53
mulf x8, x54, x54
mulf x9, x55, x55
addf x7, x7, x8
addf x7, x7, x9
isqrt x13, x7

# 2nd loop
mulf x53, x53, x13
mulf x54, x54, x13
mulf x55, x55, x13

# new inv_lcs_dist
mulf x7, x56, x56
mulf x8, x57, x57
mulf x9, x58, x58
addf x7, x7, x8
addf x7, x7, x9
isqrt x14, x7

# 3rd loop
mulf x56, x56, x14
mulf x57, x57, x14
mulf x58, x58, x14

addf x47, x0, x0 # p_tempAxis[0]
addf x48, x0, x0 # p_tempAxis[1]
addf x49, x0, x0 # p_tempAxis[2]

# args->threeDVert
lw x21, 12(x10) # *threeDVert

# sizeof(vertex_t) = 32
slli x22, x11, 5 # i * sizeof(vertex_t)
add x22, x22, x21 # threeDvert + i*20
lw x23, 0(x22) # threeDvert[i].coords.x
lw x24, 4(x22) # threeDvert[i].coords.y
lw x25, 8(x22) # threeDvert[i].coords.z

#Oa
lw x26, 0(x10) # Oa
lw x27, 0(x26) # Oa -> x
lw x28, 4(x26) # Oa -> y
lw x29, 8(x26) # Oa -> z

subf x47, x23, x27 # p_tempAxis[0]
subf x48, x24, x28 # p_tempAxis[1]
subf x49, x25, x29 # p_tempAxis[2]

addf x17, x33, x0 # move 1.0
# clobbering x30 - x38 for rotMat

# rotMat[0-8]
lw x6, 8(x10) # args -> alpha_r
lw x7, 0(x6) # *alpha_r
cos x15, x7 # cos(*alpha_r) # FIX
sin x16, x7 # sin(*alpha_r) # FIX

subf x18, x0, x16 # -sin

# lcsInv[0] = lcs[0] (50)
# lcsInv[3] = lcs[1]
# lcsInv[6] = lcs[2]
# lcsInv[1] = lcs[3]
# lcsInv[4] = lcs[4]
# lcsInv[7] = lcs[5]
# lcsInv[2] = lcs[6]
# lcsInv[5] = lcs[7]
# lcsInv[8] = lcs[8] (58)

addf x34, x0, x0 # p1[0]
addf x35, x0, x0 # p1[1]
addf x36, x0, x0 # p1[2]

# p1[0] = lcsInv[0]*ptempAxis[0] + lcsInv[3] * ptempAxis[1] + lcsInv[6] * ptempAxis[2]
# p1[1] = lcsInv[1]*ptempAxis[0] + lcsInv[4] * ptempAxis[1] + lcsInv[7] * ptempAxis[2]
# p1[2] = lcsInv[2]*ptempAxis[0] + lcsInv[5] * ptempAxis[1] + lcsInv[8] * ptempAxis[2]


mulf x7, x50, x47 # lcsInv[0]*ptempAxis[0]
addf x34, x34, x7 # p1[0] += lcsInv[0]*ptempAxis[0]
mulf x7, x51, x48 # lcsInv[3] * ptempAxis[1]
addf x34, x34, x7
mulf x7, x52, x49
addf x34, x34, x7

mulf x7, x53, x47
mulf x8, x54, x48
mulf x9, x55, x49
addf x7, x7, x8
addf x35, x7, x9

mulf x7, x56, x47
mulf x8, x57, x48
mulf x9, x58, x49
addf x7, x7, x8
addf x36, x7, x9

addf x37, x0, x0 # p2[0]
addf x38, x0, x0 # p2[1]
addf x39, x0, x0 # p2[2]

# p2[0] = rotMat[0] * p1[0] + rotMat[3] * p1[1] + rotMat[6] * p1[2]
# p2[1] = rotMat[1] * p1[0] + rotMat[4] * p1[1] + rotMat[7] * p1[2]
# p2[3] = rotMat[2] * p1[0] + rotMat[5] * p1[1] + rotMat[8] * p1[2]
# cos = rotMat[0,8] = x15
# -sin = rotMat[6] = x18
# sin = rotMat[2] = x16
# 0 = rotMat[1,3,5,7]
# 1 = rotMat[4] = x17
mulf x7, x15, x34
mulf x8, x18, x36
addf x37, x7, x8

mulf x38, x17, x35

mulf x7, x16, x34
mulf x8, x15, x36
addf x39, x7, x8

# p_world = x34, x35, x36 (p1 unused, clobber)

# p_world[0] = lcs[0] * p2[0] + lcs[3] * p2[1] + lcs[6] * p2[2]
# p_world[1] = lcs[1] * p2[0] + lcs[4] * p2[1] + lcs[7] * p2[2]
# p_world[2] = lcs[2] * p2[0] + lcs[5] * p2[1] + lcs[8] * p2[2]

#p_world[0]
mulf x7, x50, x37
mulf x8, x53, x38
mulf x9, x56, x39
addf x7, x7, x8
addf x34, x9, x7

#p_world[1]
mulf x7, x51, x37
mulf x8, x54, x38
mulf x9, x57, x39
addf x7, x7, x8
addf x35, x9, x7

#p_world[2]
mulf x7, x52, x37
mulf x8, x55, x38
mulf x9, x58, x39
addf x7, x7, x8
addf x36, x9, x7

# coords.x/y/z = 23,24,25
# Oa->x/y/z = 27,28,29
#args->threeDVertTrans[i].coords.x/y/z = p_world[0/1/2] + args->Oa->x/y/z
# trans.coords.x/y/z = 37,38,39 (clobber p2)
addf x37, x34, x27
addf x38, x35, x28
addf x39, x36, x29

lw x6, 16(x10) # args->threeDVertTrans
slli x22, x11, 5 # i * sizeof(vertex_t) = 32
add x6, x6, x22 # threeDVertTrans + i * sizeof(vertex_t)

sw x37, 0(x6) # STORE args->threeDVertTrans[i].coords.x
sw x38, 4(x6)
sw x39, 8(x6)

# TODO Check 16 byte or 12 byte struct vector_t.

# args-threeDVert = x21
add x21, x21, x22 # threeDVert + i * sizeof(vertex_t)
# args->threeDVertTrans[i] = x6
# assume padded to 16

lw x7, 16(x21) # threeDVert[i].s
lw x8, 20(x21) # threeDVert[i].t

sw x7, 16(x6) # threeDVertTrans[i].s = threeDVert[i].s
sw x8, 20(x6) # threeDVertTrans[i].t = threeDVert[i].t

# threeD_norm = 37/38/39
lw x5, 20(x10) # args->camera
lw x6, 0(x5) # camera->x
lw x7, 4(x5) # camera->y
lw x8, 8(x5) # camera->z

subf x37, x37, x6
subf x38, x38, x7
subf x39, x39, x8

# q[0/1/2] = x47/8/9

#threeD_norm * args->invTrans

lw x6, 24(x10) # args->invTrans

lw x50, 0(x6) #invTrans[0]
lw x51, 4(x6) #invTrans[1]
lw x52, 8(x6) #invTrans[2]
lw x53, 12(x6) #invTrans[3]
lw x54, 16(x6) #invTrans[4]
lw x55, 20(x6) #invTrans[5]
lw x56, 24(x6) #invTrans[6]
lw x57, 28(x6) #invTrans[7]
addi x6, x6, 4
lw x58, 28(x6) #invTrans[8]

# q[0] = threeD_norm[0] * invTrans[0] + threeD_norm[1] * invTrans[1] + threeD_norm[2] * invTrans[2]
# q[1] = 3dnorm[0/1/2] * invTrans[4/5/6] 
# q[2] = 3dnorm[0/1/2] * invTrans[7/8/9] 

mulf x7, x37, x50
mulf x8, x38, x51
mulf x9, x39, x52
addf x7, x7, x8
addf x47, x7, x9


mulf x7, x37, x53
mulf x8, x38, x54
mulf x9, x39, x55
addf x7, x7, x8
addf x48, x7, x9

mulf x7, x37, x56
mulf x8, x38, x57
mulf x9, x39, x58
addf x7, x7, x8
addf x49, x7, x9

#predicated if block 
# q 47/48/49
sltf x6, x0, x49
bne 1, x6, x0, 0

lw x5, 28(x10), 1 #args->twoDVert
slli x22, x11, 5, 1 # i * sizeof(vertex_t) = 32
add x5, x22, x5, 1 # 2DVert + i*sizeof(vertex_t)
divf x6, x47, x49, 1 # q[0]/q[2]
sw x6, 0(x5), 1 # 2Dvert[i].x

divf x6, x48, x49, 1 # q[1]/q[2]
sw x6, 4(x5), 1 # y

divf x6, x17, x49, 1 # 1.0 / q[2]
sw x6, 8(x5), 1 # z

lw x7, 12(x10), 1 #threeDVert
add x7, x22, x7, 1 #threeDVert[i]

lw x8, 16(x7), 1 # 3Dvert[i].s
lw x9, 20(x7), 1 # 3dvert[i].t

sw x8, 16(x5), 1 #2Dvert[i].s = 3Dvert[i].s
sw x9, 20(x5), 1 #2dvert[i].s = 3dvert[i].s

halt