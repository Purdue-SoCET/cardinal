
from pathlib import Path
import sys
from collections import deque
from bitstring import Bits

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.base_class import Stage, LatchIF, ForwardingIF, simple_instruction
from src.simple_isa import R_Op, I_Op, S_Op


class simple_stage(Stage):
    def __init__(self, name: str, input_if: ForwardingIF, output_if: ForwardingIF):
        super().__init__(name, input_if, output_if)

    def compute(self):
        input_data = self.behind_latch.pop()  # Get data from the behind latch
        if input_data is None:
            return  # No data to process
        
        # For demonstration, let's assume the input_data is a simple_instruction
        if not isinstance(input_data, simple_instruction):
            raise ValueError("Expected input_data to be of type simple_instruction")

        # Perform a simple operation based on the opcode
        if input_data.opcode == R_Op.ADD:
            # For simplicity, let's just add two immediate values (imm) from the instruction
            result = input_data.rdat1.int + input_data.rdat2.int  # This is just a placeholder for actual register values
            print(f"{self.name}: Adding {input_data.rdat1.int} and {input_data.rdat2.int} to get {result}")
            input_data.wdat = Bits(int=result, length=8)  # Store the result back in wdat (just for demonstration)
            self.ahead_latch.push(input_data)  # Push the result to the ahead latch
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
    return simple_stage_instance, simple_behind_latch, simple_ahead_latch

    # For demonstration, let's push a simple instruction into the behind latch and see how the stage processes it.
    # For the simulator setup, we pass through an instruction class that accumulates all the necessary information for the instruction as it goes through the pipeline. This is a simplified version of what you might see in a real GPU simulator, where the instruction class would contain much more information (e.g., register values, memory addresses, etc.).

def test_stage():

    simple_stage_instance, simple_behind_latch, simple_ahead_latch = setup_stage()

    # each stage will have a compute function that performs the core logic of the stage. In this simple example, we will just perform an addition operation based on the opcode of the instruction.
    # it pops the instruction from the behind latch, performs the computation, and then pushes the result to the ahead latch.

    # lets try calling the compute function without any data in the behind latch. This should result in no computation and no output.
    simple_instruction_instance = simple_instruction(
        pc=Bits(bin='0000000000000000', length=16),  # Just a placeholder PC value
        warp_id=0,  # Placeholder warp ID
        opcode=R_Op.ADD,  # Let's say we want to perform an ADD operation
        rdat1=Bits(bin='00000001', length=8),  # Placeholder for source register 1 value
        rdat2=Bits(bin='00000010', length=8),  # Placeholder for source register 2 value
        imm=Bits(bin='00000000', length=8)  # Placeholder for immediate value
    )
    
    # To process, run compute for a defined N number of cycles. Let's try running compute without pushing the instruction first to see that it does nothing.
    
    num_cycles = 10

    for cycle in range(num_cycles):
        print(f"Cycle {cycle}:")
        print(f"Ahead latch has data: {simple_ahead_latch.payload}")

        if cycle == 5:
            print("Pushing instruction into behind latch")
            ok = simple_behind_latch.push(simple_instruction_instance)
            print(f"Behind latch push success: {ok}")

        if cycle == 8:
            print("Popping instruction from ahead latch")
            data = simple_ahead_latch.pop()

        simple_stage_instance.compute()
        print()
        
        
def main():
    test_stage()
    

if __name__ == "__main__":
    main()