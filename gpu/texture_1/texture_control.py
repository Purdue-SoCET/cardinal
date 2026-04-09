from math import ceil
from pathlib import Path
import sys
from collections import deque
from typing import Any

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


class texture_stage(Stage):
    def __init__(self, name: str, input_if: LatchIF, output_if: LatchIF, mem_in_if: LatchIF,
                 mem_out_if: LatchIF):
        super().__init__(name, input_if, output_if)
        self.mem_behind_latch = mem_in_if
        self.mem_ahead_latch = mem_out_if
        self.mid_trilinear = 0
        self.input_data = 0

        self.fp_kwargs = {'signed': True, 'm': INT_BITS, 'n': FRAC_BITS}
        self.fp_texargs = {'signed': False, 'm': 32}
        self.HALF_TEXEL = FixedPoint(0.5, **self.fp_kwargs)



        #input buffer stuff
        self.input_buffer = [{"quads": [[(0, 0), (0, 0), (0, 0), (0, 0)], [(0, 0), (0, 0), (0, 0), (0, 0)],
                                        [(0, 0), (0, 0), (0, 0), (0, 0)], [(0, 0), (0, 0), (0, 0), (0, 0)]],
                              "filter mode": "", "clamp mode": "", "tex id": 0, "stale": 1},
                             {"quads": [[(0, 0), (0, 0), (0, 0), (0, 0)], [(0, 0), (0, 0), (0, 0), (0, 0)],
                                        [(0, 0), (0, 0), (0, 0), (0, 0)], [(0, 0), (0, 0), (0, 0), (0, 0)]],
                              "filter mode": "", "clamp mode": "", "tex id": 0, "stale": 1}
                             ]
        self.next_free = 0

        #current buffer quad select
        self.current_quad = 0
        self.current_row = 0

        #header file
        self.headers = [{"width" : 0, "height": 0, "base": 0, "mip levels": 0} for _ in range(128)]

        #buffer to represent latency
        self.address_stage_latency = []

    def compute(self):




        #memory runs (this method doesn't do any of that
        #run cycle of address generation portion of TMU (pre memory)
        if self.mem_behind_latch.read:
            pass
            #progress latency buffer forward by one and run front end calculations
            self._latency_step()
            #buffer progress
            self._progress_front()

            #front end calculation progress


        #last, check if next 8 quads can be sent to the start buffer

        pass

    def _pop_if_ready(self):

        pass

    def _latency_step(self):
        # Create a temporary list to hold items that are still waiting
        updated_latency = []

        for item in self.address_stage_latency:
            item[1] -= 1  # Decrement latency

            if item[1] == 0:
                # Latency is 0, push to latch (do NOT add to updated list)
                self.mem_behind_latch.push(item[0])
            else:
                # Latency > 0, keep it for the next cycle
                updated_latency.append(item)

        # Replace the old list with the updated one
        self.address_stage_latency = updated_latency


    def _progress_front(self):
        # check if next data is stale. If yes, return. Else read into method and compute
        if (self.input_buffer[self.current_row]["stale"]):
            return

        filter_mode = self.input_buffer[self.current_row]["filter mode"]
        current_quad = self.input_buffer[self.current_row]["quads"][self.current_quad]
        clamp_mode = self.input_buffer[self.current_row]["clamp mode"]
        header = self.headers[self.input_buffer[self.current_row]["tex id"]]



        #unnormalizing UV values
        tex_width = FixedPoint(header["width"], **self.fp_texargs)
        tex_height = FixedPoint(header["height"], **self.fp_texargs)

        unnorm_vals = []
        for u_float, v_float in current_quad:
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

        # 1. Absolute Values (Hardware cost: 0 gates, just strip/flip the sign bit)
        abs_dUdx = abs(dUdx)
        abs_dVdx = abs(dVdx)
        abs_dUdy = abs(dUdy)
        abs_dVdy = abs(dVdy)

        # 2. Maximums (Hardware cost: simple comparators and multiplexers)
        # Find the maximum footprint in the X direction
        Lx = abs_dUdx if abs_dUdx > abs_dVdx else abs_dVdx

        # Find the maximum footprint in the Y direction
        Ly = abs_dUdy if abs_dUdy > abs_dVdy else abs_dVdy

        # 3. Final Phi
        # The ideal LOD is based on whichever direction is stretched the most
        phi = Lx if Lx > Ly else Ly

        LOD = self.estimate_lod(phi)

        #clamp lod
        LOD = min(LOD, header["mip_levels"])
        LOD_frac = FixedPoint(LOD, **self.fp_kwargs)

        #mip level conversions
        if self.mid_trilinear:  # round up lod
            mip_level = math.ceil(LOD)
        elif filter_mode == "trilinear":
            mip_level = math.floor(LOD)
        else:
            mip_level = round(float(LOD))

        # mip width, height, and base address calculations
        base = header["base"]
        mip_width = tex_width >> int(mip_level)
        mip_height = tex_height >> int(mip_level)

        #clamping
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
        self.address_stage_latency.append([output_packet,9])
        if filter_mode == "trilinear" and not self.mid_trilinear:
            self.mid_trilinear = 1
        else:
            self.mid_trilinear = 0
            self.current_quad += 1
            if self.current_quad == 4:
                self.input_buffer[self.current_row]["stale"] = 1
                self.current_quad = 0
                self.current_row = not self.current_row



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
    simple_stage_instance = texture_stage(name="tex control stage",
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