from math import ceil
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

        self.fp_kwargs = {'signed': True, 'm': INT_BITS, 'n': FRAC_BITS}
        self.fp_texargs = {'signed': False, 'm': 32}
        self.HALF_TEXEL = FixedPoint(0.5, **self.fp_kwargs)


    def compute(self):
        if not self.mid_trilinear:
            self.input_data = self.behind_latch.pop()  # Get data from the behind latch
            if self.input_data is None:
                return  # No data to process

        #unnormalizing UV values
        tex_width = FixedPoint(self.input_data["width"], **self.fp_texargs)
        tex_height = FixedPoint(self.input_data["height"], **self.fp_texargs)

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

        Lx = FixedPoint(Lx_float, **self.fp_kwargs)
        Ly = FixedPoint(Ly_float, **self.fp_kwargs)

        phi = Lx if Lx > Ly else Ly

        LOD = self.estimate_lod(phi)

        #clamp lod
        LOD = min(LOD, self.input_data["mip_levels"])
        LOD_frac = FixedPoint(LOD, **self.fp_kwargs)

        #mip level conversions
        filter_mode = self.input_data["filter"]
        if self.mid_trilinear:  # round up lod
            mip_level = math.ceil(LOD)
        elif filter_mode == "trilinear":
            mip_level = math.floor(LOD)
        else:
            mip_level = round(float(LOD))

        # mip width, height, and base address calculations
        base = self.input_data["base"]
        mip_width = tex_width >> int(mip_level)
        mip_height = tex_height >> int(mip_level)

        #clamping
        clamp_mode = self.input_data["clamp"]
        texel_requests = []
        for pixel in unnorm_vals:
            #scale u and v values according to current mip level
            u_scaled = pixel["u"] >> int(mip_level)
            v_scaled = pixel["v"] >> int(mip_level)


            #apply -.5 if using nearest
            if filter_mode != "nearest":
                u_scaled-= self.HALF_TEXEL
                v_scaled-= self.HALF_TEXEL

            #split integer and fractional part of fixed point (memory does not care about the fraction, only filtering)

            i0_u = int(u_scaled)
            i0_v = int(v_scaled)
            frac_u = u_scaled - FixedPoint(i0_u, **self.fp_kwargs)
            frac_v = v_scaled - FixedPoint(i0_v, **self.fp_kwargs)

            #clamp calculations
            mip_w_int = int(mip_width)
            mip_h_int = int(mip_height)

            if clamp_mode == "wrap":
                i0_u_clamped = i0_u % mip_w_int
                i1_u_clamped = (i0_u + 1) % mip_w_int
                i0_v_clamped = i0_v % mip_h_int
                i1_v_clamped = (i0_v + 1) % mip_h_int

            elif clamp_mode == "mirror":
                double_w = 2 * mip_w_int
                double_h = 2 * mip_h_int

                i0_u_mod = i0_u % double_w
                i0_u_clamped = i0_u_mod if i0_u_mod < mip_w_int else (double_w - 1) - i0_u_mod
                i1_u_mod = (i0_u + 1) % double_w
                i1_u_clamped = i1_u_mod if i1_u_mod < mip_w_int else (double_w - 1) - i1_u_mod

                i0_v_mod = i0_v % double_h
                i0_v_clamped = i0_v_mod if i0_v_mod < mip_h_int else (double_h - 1) - i0_v_mod
                i1_v_mod = (i0_v + 1) % double_h
                i1_v_clamped = i1_v_mod if i1_v_mod < mip_h_int else (double_h - 1) - i1_v_mod

            else:  # clamp_to_edge
                max_u, max_v = mip_w_int - 1, mip_h_int - 1
                i0_u_clamped = max(0, min(i0_u, max_u))
                i1_u_clamped = max(0, min(i0_u + 1, max_u))
                i0_v_clamped = max(0, min(i0_v, max_v))
                i1_v_clamped = max(0, min(i0_v + 1, max_v))

            texel_requests.append({
                "texel_x": (i0_u_clamped, i1_u_clamped),
                "texel_v": (i0_v_clamped, i1_v_clamped),
                "weights": (frac_u, frac_v)
            })
        output_packet = {"texels": texel_requests, "mip ratio": LOD_frac, "filter mode": filter_mode,
                         "mip width": mip_w_int, "mip height": mip_h_int, "base address": base}

        if self.mid_trilinear:
            self.mid_trilinear = 0
        elif filter_mode == "trilinear":
            self.mid_trilinear = 1

        return output_packet












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
    # Every stage that contains the core computational logic is 'gated'
    # By a forward and backward latch. These effectively act as the 'clock' for the stage, and also allow for forwarding and stalling.
    # The stage will only compute when the forward latch is valid, and the backward latch is ready to accept new data (compute right now, or stall if not).

    simple_behind_latch = LatchIF(name="SimpleBehindLatch")
    simple_ahead_latch = LatchIF(name="SimpleAheadLatch")

    # instantiate a simple stage
    simple_stage_instance = texture_stage_1(name="tex control stage",
                                         input_if=simple_behind_latch,
                                         output_if=simple_ahead_latch)

    # There can be more inputs into the stage ( as you will see in other examples with forwarding interfaces, memoryy structures, etc.), but for this simple example, we will just use the forward and backward latches.
    return simple_stage_instance, simple_behind_latch, simple_ahead_latch

    # For demonstration, let's push a simple instruction into the behind latch and see how the stage processes it.
    # For the simulator setup, we pass through an instruction class that accumulates all the necessary information for the instruction as it goes through the pipeline. This is a simplified version of what you might see in a real GPU simulator, where the instruction class would contain much more information (e.g., register values, memory addresses, etc.).


def test_stage():
    simple_stage_instance, simple_behind_latch, simple_ahead_latch = setup_stage()

    simple_behind_latch.payload = {""}
    print("hi")


def main():
    test_stage()


if __name__ == "__main__":
    main()