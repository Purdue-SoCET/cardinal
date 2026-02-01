### ASM file that will initialize 32 stack pointers and push a value onto each stack.
### Every warp always pushes. Values must always be consumed. 
### Test is broken into two segments
### First, one will push onto the stack so that the memdump can verify the values all exist.

#How is the predicated handled in instructions? Not very sure.


csrr x3, x1000 #fictional block id
csrr x4, x1001 #fictional blockDim
csrr x5, x1002 #fictional thread ID
mul x4, x3, x4
add x4, x4, x5
###Register 4 is the thread pointer. Now, every stack will be set at a different location based on the warp id.

# ---- lane and warp IDs
srli  x6, x4, 5            # x6 = warp_id = tid / 32
andi  x7, x4, 31           # x7 = lane_id = tid % 32
slli  x7, x7, 2            # x7 = byte offset within the warp push area (lane*4)

# ---- SP := 0xA0100000 + (warp_id << 20)
# This makes every SW warp stack 1 megabyte(classic definition of 1024 kilobytes of 1024 bytes), which is unlikely to ever become full.
addi  x2, x0, 0            # clear SP
lui   x2, 0xA0             # x2[31:24] = 0xA0        => 0xA0000000
lmi   x2, 0x100            # x2[23:12] = 0x100       => 0xA0100000

slli  x6, x6, 20           # x6 = warp_id * 1MiB(mebi byte lol)
add   x2, x2, x6           # SP now at top of this warp's 1MiB stack

# ---- push: each thread writes one word at SP + lane*4, then SP -= 128
add   x8, x2, x7           # x8 = effective address for this lane
sw    x4, 0(x8)            # store something we can see in dump (here: global tid)
lli x12, 128
sub  x2, x2, x12         # SP = SP - 128  (32 thread * 4B = 128B)

### Now, if you have verified that the above code was correct, we can pop off the stack and ensure the values are all read in,
### by storing to a different address(0xB....)

# The pushed words are at (SP + 128) + lane*4
add   x9, x2, x7         # x9 = SP + lane_off
add  x9, x9, x12        # x9 = SP + lane_off + 128 = address we wrote
lw    x10, 0(x9)         # x10 = popped value for this lane
add  x2, x2, x12        # SP += 128 (restores SP to stack top)

# =====(B region) =====
# Per-warp 1 MiB region starting at 0xB0000000; we only use first 128 B
lui   x11, 0xB0          # x11 = 0xB0000000
lmi   x11, 0x000
lli   x11, 0x000
add   x12, x11, x6       # reuse x6 = warp_id << 20
add   x12, x12, x7       # + lane*4
sw    x10, 0(x12)        # write popped value for memdump