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


class texture_stage_1(Stage):
    def __init__(self, name: str, input_if: ForwardingIF, output_if: ForwardingIF):
        super().__init__(name, input_if, output_if)
        self.mid_trilinear = 0
        self.input_data = 0
        self.HALF_TEXEL = FixedPoint(0.5, **self.fp_kwargs)


    def compute(self):
        if not self.mid_trilinear:
            self.input_data = self.behind_latch.pop()  # Get data from the behind latch
            if self.input_data is None:
                return  # No data to process



        fp_kwargs = {'signed': True, 'm': INT_BITS, 'n': FRAC_BITS}
        fp_texargs = {'signed': False, 'm': 32}

        #unnormalizing UV values
        tex_width = FixedPoint(self.input_data["width"], **fp_texargs)
        tex_height = FixedPoint(self.input_data["height"], **fp_texargs)

        unnorm_vals = []
        for u_float, v_float in self.input_data["UVs"]:
            u_fp = FixedPoint(u_float, **self.fp_kwargs)
            v_fp = FixedPoint(v_float, **self.fp_kwargs)

            # Multiply and Resize to model physical wire truncation
            u_unnorm = (u_fp * tex_width).resize(INT_BITS, FRAC_BITS)
            v_unnorm = (v_fp * tex_height).resize(INT_BITS, FRAC_BITS)

            unnorm_vals.append({"u": u_unnorm, "v": v_unnorm})

        #derivative calculations
        dUdx = unnorm_vals[1]["u"] - unnorm_vals[0]["u"]
        dVdx = unnorm_vals[1]["v"] - unnorm_vals[0]["v"]
        dUdy = unnorm_vals[2]["u"] - unnorm_vals[0]["u"]
        dVdy = unnorm_vals[2]["v"] - unnorm_vals[0]["v"]


        #mip map LOD calculation

         #have to figure out the best way to do this, since the fixed point library doesnt support square root
        dx_sq = dUdx ** 2
        dy_sq = dVdx ** 2

        dy2_sq = dUdy ** 2
        dy2_sq_v = dVdy ** 2

        # 3. Sum of squares
        sum_sq_x = dx_sq + dy_sq
        sum_sq_y = dy2_sq + dy2_sq_v

        # 4. The Square Root Bridge
        # Cast to float -> apply math.sqrt -> cast back to S16.16 FixedPoint
        Lx_float = math.sqrt(float(sum_sq_x))
        Ly_float = math.sqrt(float(sum_sq_y))

        Lx = FixedPoint(Lx_float, **fp_kwargs)
        Ly = FixedPoint(Ly_float, **fp_kwargs)

        phi = Lx if Lx > Ly else Ly

        LOD = self.estimate_lod()

        filter_mode = self.input_data["filter"]
        # if filter_mode != "nearest":
        #     U0_unnormalized -= .5
        #     V0_unnormalized -= .5
        #     U1_unnormalized -= .5
        #     V1_unnormalized -= .5
        #     U2_unnormalized -= .5
        #     V2_unnormalized -= .5
        #     U3_unnormalized -= .5
        #     V3_unnormalized -= .5
        #
        #
        #
        # # clamp calculations
        # clamp_mode = self.input_data["clamp"]
        # if clamp_mode == "wrap":
        #     U0_unnormalized = U0_unnormalized % (tex_width)
        #     V0_unnormalized = V0_unnormalized % (tex_height)
        #     U1_unnormalized = U1_unnormalized % (tex_width)
        #     V1_unnormalized = V1_unnormalized % (tex_height)
        #     U2_unnormalized = U2_unnormalized % (tex_width)
        #     V2_unnormalized = V2_unnormalized % (tex_height)
        #     U3_unnormalized = U3_unnormalized % (tex_width)
        #     V3_unnormalized = V3_unnormalized % (tex_height)
        # elif clamp_mode == "mirror":
        #     pass
        # else:  # clamp to edge
        #     pass


        #base mip address calculations


    def estimate_lod(self, phi):
        # 1. Get raw bits
        val = int(phi.bits)
        if val <= 0: return 0  # Log of 0/negative is undefined in this logic

        # 2. Find MSB and Integer Part
        msb = val.bit_length() - 1
        k = msb - self.FRAC_BITS  # FRAC_BITS = 16

        # 3. LUT index (using 4 bits of precision)
        # We ignore the MSB itself (it's always 1) and take the next 4 bits
        idx = (val >> (msb - 4)) & 0xF

        # 4. Lookup (Standard GPU LUT values for log2)
        log2_lut = [0, 9, 18, 26, 34, 42, 50, 58, 65, 72, 79, 86, 93, 99, 105, 112]
        f = log2_lut[idx]  # This is an 8-bit fraction

        # 5. Combine into a new FixedPoint LOD (S16.16)
        # Shift k to integer position, and f to fractional position
        lod_bits = (k << 16) | (f << 8)

        # Initialize FixedPoint from the raw bits
        return FixedPoint.from_bits(lod_bits, signed=True, m=INT_BITS, n=FRAC_BITS)

def setup_stage():
    pass

def test_stage():
    pass


def main():
    test_stage()


if __name__ == "__main__":
    main()