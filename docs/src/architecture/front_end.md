The front end includes 3 key stages: FETCH, DECODE + PREDICATION, ISSUE.

<Insert info about fetch>

Decode and Predicate Management 

Control Flow management in this GPU architecture uses exclusively predicate masks:

Predicate masks are usually used for smaller, shallow nested conditionals which flatten control flow into a single instruction stream. In our implementation, we have a seperate predicate register file, which is organized as a two-dimension SRAM array indexed by the warp ID and predicate ID. The design supports up to 32 warps per SM, and each warp is provisioned 16 predicate registers, each storing a 32-bit per thread mask.  All incoming instructions, in addition to holding data register file bits, also have bits reserved to index into the PRF. For non-branch instructions, the PRF is read in decode and propagated through the stages to conditionally gate architectural side effects, like register writeback and memory commits on a per-thread basis. Masked lanes can still execute micro-operations such as functional units, but are prevented from producing architectural state updates. Similarly, when branch instructions occur, two predicate fields are provided to update the predicate mask with in the PRF: one predicate holds the incoming lane-activity mask, another holds the branch condition result, which is then AND’d to store back the next active mask (similar to: pr1 &= pr2).  

A principal  drawback of this method is its strong reliance on correct and efficient compiler-level predicate assignment. Because divergence management is resolved almost entirely at compiler time, the hardware intentionally forgoes dynamic contingency handling. While this significantly simplifies the control hardware, it correspondingly reduces the system’s ability to adapt to irregular control flow at runtime--this is unexpected to be an issue for most GPU workloads, but we acknowledge that there are cases where a warp may 'use' up all its provisioned warps.

In such a scenario, the compiler is expected to insert a predicate load/store instruction which will a) store the registers for the selected warp into memory. This requires generating a signal in decode to mux between reads from the predicate register OR the data register file, as well as a mux after the writeback buffer to store to the pred or data reg file. This will be single threaded by hardcoding a oonsant '32'b1' value for the predication mask.
