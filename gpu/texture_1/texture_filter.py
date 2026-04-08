from pathlib import Path
import sys
from collections import deque
from bits import Bits
from fixedpoint import FixedPoint
import math

ROOT = Path(__file__).resolve().parent.parent
INT_BITS = 16
FRAC_BITS = 16
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.base_class import Stage, LatchIF, ForwardingIF, simple_instruction
from src.simple_isa import R_Op, I_Op, S_Op


class texture_stage_2(Stage):
    def __init__(self, name: str, input_if: ForwardingIF, output_if: ForwardingIF):
        super().__init__(name, input_if, output_if)
        self.mid_trilinear = 0
        self.input_data = 0
        self.counter = 0
        self.HALF_TEXEL = FixedPoint(0.5, **self.fp_kwargs)


    def compute(self):
        self.input_data = self.behind_latch.pop()

        if self.input_data is None:
            return  # No data to process


        filter_mode = self.input_data["filter"]
        if filter_mode=="nearest":
            #skip everything else and put in buffer
            pass
        else:
            #trilinear does bilinear on each pixel
            pass

        if self.mid_trilinear:
            #do linear interpolation from buffer
            self.mid_trilinear = 0

        elif filter_mode == "trilinear":
            #put data into buffer
            self.mid_trilinear = 1






        fp_kwargs = {'signed': True, 'm': INT_BITS, 'n': FRAC_BITS}
        fp_texargs = {'signed': False, 'm': 32}

        #unnormalizing UV values
        tex_width = FixedPoint(self.input_data["width"], **fp_texargs)
        tex_height = FixedPoint(self.input_data["height"], **fp_texargs)






def setup_stage():
    pass

def test_stage():
    pass


def main():
    test_stage()


if __name__ == "__main__":
    main()