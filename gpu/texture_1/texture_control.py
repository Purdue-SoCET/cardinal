from pathlib import Path
import sys
from collections import deque
from bits import Bits

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.base_class import Stage, LatchIF, ForwardingIF, simple_instruction
from src.simple_isa import R_Op, I_Op, S_Op


class texture_stage(Stage):
    def __init__(self, name: str, input_if: ForwardingIF, output_if: ForwardingIF):
        super().__init__(name, input_if, output_if)
        self.mid_trilinear = 0
        self.input_data = 0

    def compute(self):
        if not self.mid_trilinear:
            self.input_data = self.behind_latch.pop()  # Get data from the behind latch
            if self.input_data is None:
                return  # No data to process

        UVs = self.input_data["UVs"]
        U0, V0 = UVs[0]
        U1, V1 = UVs[1]
        U2, V2 = UVs[2]
        U3, V3 = UVs[3]

        #derivative calculations
        dUdx = U1 - U0
        dVdx = V1 - V0
        dUdy = U2 - U0
        dVdy = V2 - V0

        #mip map LOD calculation
        


def setup_stage():
    pass

def test_stage():
    pass


def main():
    test_stage()


if __name__ == "__main__":
    main()