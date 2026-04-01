# Cx01 Simulator PLayground Setup


This is a guide to understand the Cardinal GPU microarchitcture simulator setup, namely:    

1. How to decompose computational logic into well-defined classes and modules
(e.g., instructions, stage classes, register files and memory)
2. How to model and simulate cycle-accurate execution flow
(e.g., per-cycle updates, pipeline progression, state transitions)
3. How to verify correctness using logging, tracing, and simple test cases
(e.g., register dumps, instruction traces, sanity checks)
4. How to integrate new features in a clean and maintainable way
(e.g., extending classes, isolating changes, avoiding tight coupling)
5. How to experiment safely within the playground before modifying the full simulator
(e.g., prototyping instructions, testing scheduling ideas, validating assumptions)

The framework provided here is a simplified playground version of the (prospective) structure in the full simulator. It is strongly recommended to use this environment to test your understanding and ideas before working directly with the full GPU simulator (its a LOT!).

