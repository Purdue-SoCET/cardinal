from src.base_class import *
from src.simple_isa import Op


class simple_stage(Stage):
    def __init__(self, name: str, input_if: ForwardingIF, output_if: ForwardingIF):
        super().__init__(name, input_if, output_if)

    def compute(self):
        input_data = self.get_data()
        if input_data is None:
            return  # No data to process

        # For demonstration, let's assume the input_data is a simple_instruction
        if not isinstance(input_data, simple_instruction):
            raise ValueError("Expected input_data to be of type simple_instruction")

        # Perform a simple operation based on the opcode
        if input_data.opcode == Op.ADD:
            # For simplicity, let's just add two immediate values (imm) from the instruction
            result = input_data.rdat1 + input_data.rdat2  # This is just a placeholder for actual register values
            print(f"{self.name}: Adding {input_data.rdat1} and {input_data.rdat2} to get {result}")
            self.send_output(result)
        else:
            print(f"{self.name}: Unsupported opcode {input_data.opcode}")

def setup_stage():

    # Every stage that contains the core computational logic is 'gated'
    # By a forward and backward latch. These effectively act as the 'clock' for the stage, and also allow for forwarding and stalling.
    # The stage will only compute when the forward latch is valid, and the backward latch is ready to accept new data (compute right now, or stall if not).

    simple_behind_latch = LatchIF(name="SimpleBehindLatch")
    simple_ahead_latch = LatchIF(name="SimpleAheadLatch")

    # instantiate a simple stage
    simple_stage_instance = simple_stage(name="SimpleStage", 
                                         input_if=simple_behind_latch,
                                         output_if=simple_ahead_latch)
    
    # There can be more inputs into the stage ( as you will see in other examples with forwarding interfaces, memoryy structures, etc.), but for this simple example, we will just use the forward and backward latches.
    return simple_stage_instance

    # For demonstration, let's push a simple instruction into the behind latch and see how the stage processes it.
    # For the simulator setup, we pass through an instruction class that accumulates all the necessary information for the instruction as it goes through the pipeline. This is a simplified version of what you might see in a real GPU simulator, where the instruction class would contain much more information (e.g., register values, memory addresses, etc.).

def test_stage():

    simple_stage_instance = setup_stage()

    # each stage will have a compute function that performs the core logic of the stage. In this simple example, we will just perform an addition operation based on the opcode of the instruction.
    # it pops the instruction from the behind latch, performs the computation, and then pushes the result to the ahead latch.

    # lets try calling the compute function without any data in the behind latch. This should result in no computation and no output.
    simple_instruction_instance = simple_instruction(
        pc=Bits(bin='0000000000000000', length=16),  # Just a placeholder PC value
        warp_id=0,  # Placeholder warp ID
        opcode=Op.ADD,  # Let's say we want to perform an ADD operation
        rdat1=Bits(bin='00000001', length=8),  # Placeholder for source register 1 value
        rdat2=Bits(bin='00000010', length=8),  # Placeholder for source register 2 value
        imm=Bits(bin='00000000', length=8)  # Placeholder for immediate value
    )

    

