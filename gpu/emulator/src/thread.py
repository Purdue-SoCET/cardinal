from bitstring import Bits
from state import State
from reg_file import *
from instr import *

class Thread:

    def __init__(self, state_data: State, start_pc: int, csr_file: CsrRegFile):
        self.state = state_data
        self.pc = start_pc
        self.cfile = csr_file

    def step_instruction(self) -> bool:
        # Get instruction
        instr_bits = self.state.memory.read(self.pc, 4)
        instr = Instr(I_Op_0.ADDI) # Fake empty instruction parent class, to be set
        instr.decode(instruction=instr_bits,pc=self.pc)

        if instr.op == H_Op.HALT:
            return True # Thread has halted

        instr_ret = instr.eval(self.cfile, self.state)
        if instr_ret != None:
            self.pc = instr_ret
        else:
            self.pc += 4

        return False  # Continue execution

    def run_until_halt(self):
        while(not self.step_instruction()):
            pass

