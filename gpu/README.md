# Cx01 Simulator Playground Setup

This playground is meant to help you understand the structure and behavior of the Cardinal GPU microarchitecture simulator in a smaller, easier-to-debug environment.

It is designed to teach five main ideas:

1. How to decompose computational logic into well-defined classes and modules  
   Examples include instructions, stage classes, register files, predicate files, latches, forwarding interfaces, and memory.

2. How to model and simulate cycle-accurate execution flow  
   This includes per-cycle updates, stage ordering, pipeline progression, stalls, and state transitions.

3. How to verify correctness using logging, tracing, and simple test cases  
   This includes register dumps, latch contents, instruction traces, per-cycle prints, and final-state checks.

4. How to integrate new features in a clean and maintainable way  
   This includes extending instruction formats, adding new pipeline behavior, adding predicate support, and isolating feature-specific changes.

5. How to experiment safely within the playground before modifying the full simulator  
   This includes prototyping instructions, testing scheduling ideas, validating assumptions, and understanding control flow before working in the full simulator.

The framework provided here is a simplified playground version of the intended structure in the full simulator. It is strongly recommended to use this environment to test your understanding and ideas before working directly with the full GPU simulator.

---

## Core Concepts in This Playground

The setup here mirrors the main architectural ideas used in the larger simulator.

### 1. `simple_instruction`
This is the object that moves through the pipeline. It stores the decoded instruction information, source and destination registers, operand data, memory-related fields, predicate information, and tracing metadata such as stage entry/exit cycles.

### 2. `Stage`
Each stage holds the main computational logic for one part of the pipeline. A stage reads input, performs some operation, and then tries to pass the result forward.

### 3. `LatchIF`
Latches model the pipeline boundaries between stages. They are the main data path. An instruction moves from stage to stage by being pushed into and popped from latches.

### 4. `ForwardingIF`
Forwarding interfaces are used for sideband control and backpressure. They are not the main instruction path. In this playground they are mainly used to model stalling and to block an upstream stage when a downstream stage is busy.

### 5. Register File and Predicate File
The register file stores architectural register values. In the predicated version, the predicate file stores per-thread active masks that determine which lanes are allowed to write back.

---

## Why the Test Cases Are Structured This Way

The test cases are not random examples. Each one is meant to demonstrate one specific piece of simulator behavior, and together they show how the pipeline works under normal execution, stalls, hazards, memory latency, and predication.

The goal is to move from the simplest possible case to more realistic behavior:

- first, show one instruction moving through a single stage
- then, show instructions progressing through multiple stages
- then, show stalls and dependencies
- finally, show predication and lane-masked writeback

This makes it easier to understand *why* each piece of the simulator exists.

---

## Test Cases Covered

## 1. Single-Stage Instruction Flow

### What it tests
A single instruction is pushed into the input latch of one stage, processed, and then pushed into the output latch.

### Why it matters
This is the smallest possible working example of pipeline behavior. It shows:

- how a latch holds input data
- how a stage pops from its behind latch
- how computation is performed
- how the result is pushed into the ahead latch

### What to look for
You should see:

- no activity when the input latch is empty
- valid activity once an instruction is inserted
- the output latch receiving the processed instruction

This test is useful for understanding the basic contract between a stage and its input/output latches.

---

## 2. Multi-Stage Pipeline Progression

### What it tests
Instructions move through multiple stages such as:

- Issue
- Execute
- Memory
- Writeback

The stages are evaluated once per cycle in reverse pipeline order so that each instruction advances by one stage per cycle.

### Why it matters
This demonstrates actual cycle-by-cycle pipeline progression. It shows that a result produced in one stage during a cycle is not consumed by the next stage until a later cycle.

### What to look for
You should see:

- instructions entering the pipeline one at a time
- latch contents changing from cycle to cycle
- instructions progressing stage by stage rather than skipping ahead

This test teaches the basic timing model of the simulator.

---

## 3. Structural Stall from a Busy Downstream Stage

### What it tests
A downstream stage, typically Memory, is intentionally kept busy for multiple cycles. While that stage holds an instruction, it prevents the upstream stage from sending another instruction forward.

### Why it matters
This demonstrates structural hazards and backpressure. It explains why forwarding and wait signals are needed in addition to latches.

A latch models the main instruction path. A forwarding interface models the extra control path that says, effectively, "do not send me more work right now."

### What to look for
You should see:

- an instruction reach the busy stage
- the busy stage hold that instruction for several cycles
- the upstream stage remain blocked because the next latch cannot accept data
- the held instruction continue once the downstream stage becomes available

This makes the purpose of backpressure concrete.

---

## 4. RAW Dependency Stall

### What it tests
A later instruction depends on a register value that is being produced by an earlier instruction. The later instruction must wait until the earlier one completes writeback.

Example pattern:

- instruction A writes `R2`
- instruction B reads `R2`
- instruction B stalls until `R2` is no longer busy

### Why it matters
This demonstrates scoreboarding and dependency tracking. Without this behavior, dependent instructions could read stale data.

### What to look for
You should see:

- the producing instruction mark a destination register busy
- the dependent instruction stall in Issue
- the busy bit clear in Writeback
- the dependent instruction issue only after the producer completes

This test shows how correctness is preserved in the presence of data hazards.

---

## 5. Memory Latency Test

### What it tests
A load instruction goes through the Memory stage and is delayed for several cycles before the data is returned.

### Why it matters
Memory is often slower than ALU execution. This test models that difference and shows how memory latency affects pipeline progression.

### What to look for
You should see:

- a load instruction enter Memory
- the Memory stage report that it is busy for multiple cycles
- the load write back only after the programmed latency expires

This test helps connect the simulator behavior to realistic architectural timing.

---

## 6. Independent Instruction Behind a Long-Latency Operation

### What it tests
An instruction that is not data-dependent on a load still gets delayed because the pipeline resource behind it is busy.

Example pattern:

- load enters Memory and stalls there
- independent ALU instruction reaches Execute
- Execute cannot forward because Memory is still occupied

### Why it matters
This shows the difference between:

- **data hazards**, where an instruction must wait because it needs a value
- **structural hazards**, where an instruction must wait because the hardware resource path is blocked

### What to look for
You should see:

- the instruction is logically ready to execute
- but it still cannot advance because the downstream path is full

This test helps distinguish different types of stalls.

---

## 7. Predicated Writeback with All Lanes Active

### What it tests
A predicated instruction tagged with a predicate register whose mask enables every lane.

Example:

- `ADD.P0 R1 = R10 + R11`
- `P0 = [True, True, True, True, True, True, True, True]`

### Why it matters
This serves as the baseline predication case. It shows that predicated execution reduces to normal execution when all lanes are active.

### What to look for
You should see:

- all lanes participate
- all lanes write back
- the destination register changes in every lane

This confirms that the predication mechanism works in the simplest case.

---

## 8. Predicated Writeback with Alternating Active Lanes

### What it tests
A predicated instruction uses a mask such as "even lanes only."

Example:

- `ADD.P1 R2 = R10 + R11`
- `P1 = [True, False, True, False, True, False, True, False]`

### Why it matters
This demonstrates the core purpose of predication: all lanes may conceptually execute the instruction, but only the active lanes commit the result.

### What to look for
You should see:

- active lanes receive updated values
- inactive lanes keep their old values
- the final destination register shows a mixture of changed and unchanged lanes

This is one of the clearest demonstrations of SIMT-style masked execution.

---

## 9. Predicated Load with Partial-Lane Writeback

### What it tests
A load instruction is predicated so that only some threads are allowed to write the loaded values back.

Example:

- `LD.P2 R3 = MEM[R20 + 0]`
- `P2 = [False, False, False, False, True, True, True, True]`

### Why it matters
This combines two important features:

- memory latency
- predicated, lane-masked writeback

It shows that predication is not just for ALU operations. It also applies to memory results.

### What to look for
You should see:

- the load stall in Memory for several cycles
- only the active lanes update the destination register
- inactive lanes retain their previous value

This test is especially useful because it combines control masking with memory behavior.

---

## 10. Predicated Dependent Instruction

### What it tests
A predicated ALU instruction depends on a register produced by a predicated load.

Example pattern:

- predicated load writes `R3`
- predicated add uses `R3`
- add stalls until `R3` is ready
- only the predicate-enabled lanes write back

### Why it matters
This combines several ideas at once:

- dependency tracking
- memory latency
- predication
- selective writeback

It is one of the most complete demonstrations in the playground.

### What to look for
You should see:

- the dependent instruction waiting in Issue
- the producer completing writeback first
- the dependent instruction issuing later
- only the active predicate lanes updating the destination register

This test shows how the different simulator mechanisms work together instead of in isolation.

---

## How to Read the Output

The printed traces are meant to answer a few questions every cycle:

1. What is currently sitting in each latch?
2. Which registers are marked busy?
3. Which instruction is being held by a stage?
4. Is the pipeline advancing, stalling, or draining?
5. In the predicated case, which lanes are actually writing back?

When debugging, focus on these in order:

- latch contents
- busy register list
- per-stage messages
- final register and memory state

If those line up, the pipeline behavior is probably correct.

---
## Playground Skeleton File

A blank pipeline skeleton is included so you can experiment without needing to understand the full simulator first.

This file is intentionally minimal. It gives you:

- a generic `simple_instruction` object
- a generic `Stage` wrapper
- latches between stages
- a simple cycle loop
- placeholder functions where you can add your own logic

The skeleton does **not** assume a specific instruction set, execution rule, or stage behavior. That is intentional. The goal is to let you build your own understanding by filling in the missing pieces yourself.

### What you are expected to customize

You can modify any of the following depending on what you want to test:

- `build_program()`  
  Add instructions or leave it empty and insert them manually.

- `process_instruction()` inside a stage  
  Add your own computation, tagging, timing behavior, or transformations.

- `build_pipeline()`  
  Rename stages, add more stages, remove stages, or replace generic stages with your own subclasses.

- the main experiment loop  
  Change how instructions are fed in, how long the simulation runs, or how completion is checked.

### Good first experiments

If you are not sure where to start, try one of these:

1. Make one stage simply pass an instruction through unchanged.  
2. Make one stage modify a field such as `imm` or attach a debug tag.  
3. Add a stage that stalls an instruction for a few cycles before forwarding it.  
4. Add print statements to track where an instruction goes each cycle.  
5. Create your own subclass of `GenericStage` and define new behavior in `process_instruction()`.
