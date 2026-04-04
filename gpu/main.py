# Import the necessary libraries

# Import the modules you're testing 


""" 
IN this, we are building a simple GPU implementation.
This baby GPU is a super duper simple GPU that can only do one thing: add two numbers together in a pipeline (coughcoughece337lab4). It has a single register that can hold a number, and it can only perform one operation: add a number in the register to another number and store the result back in the register. Additionally, we store and load values from a baby memory as well.

Like any GPU, we need instructions to tell it what to do. We will define a simple 16 bit instruction set for our baby GPU, defined below:

mv rs1, rs2: Move the value from register rs2 to register rs1.
[15:12] opcode: 4 bits to specify the operation (e.g., add, move, load, store)
[11:8] rs1: 4 bits to specify the destination register (0-15)
[7:4] rs2: 4 bits to specify the source register (0-15)
[3:0] imm: 4 bits to specify an immediate value (0-15)

add rs1, rs2: Add the value in register rs2 to the value in register rs1 and store the result in register rs1.

"""

def build_baby_gpu():

    "This baby GPU is a super duper simple GPU that can only do one thing: add two numbers together in a pipeline (coughcoughece337lab4)It has a single register that can hold a number, and it can only perform one operation: add a number in the register to another number and store the result back in the register."
    
    # Based the above description, 