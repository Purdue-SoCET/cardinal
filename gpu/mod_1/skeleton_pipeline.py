# test_pipeline_skeleton.py
from pathlib import Path
import sys
from collections import deque
from bitstring import Bits

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.base_class import Stage, LatchIF, simple_instruction


# ============================================================
# Config
# ============================================================

MAX_CYCLES = 20


# ============================================================
# Small helpers
# ============================================================

def wordbits(n: int) -> Bits:
    return Bits(int=n, length=32)


def regbits(n: int) -> Bits:
    return Bits(uint=n, length=6)


def bits_to_int(x):
    if x is None:
        return 0
    if isinstance(x, Bits):
        return x.int
    return int(x)


def reg_num(x):
    return None if x is None else x.uint


def instr_str(instr: simple_instruction) -> str:
    if instr is None:
        return "None"

    opcode_name = getattr(instr.opcode, "name", "NONE") if instr.opcode is not None else "NONE"
    return (
        f"{opcode_name}"
        f"(pc={bits_to_int(instr.pc)}, "
        f"rd={reg_num(instr.rd)}, rs1={reg_num(instr.rs1)}, "
        f"rs2={reg_num(instr.rs2)}, imm={bits_to_int(instr.imm)})"
    )


# ============================================================
# Generic instruction builder
# Students can change this however they want.
# ============================================================

def make_instruction(pc=0, opcode=None, rd=None, rs1=None, rs2=None, imm=0):
    return simple_instruction(
        pc=wordbits(pc),
        warp_id=0,
        opcode=opcode,
        rd=regbits(rd) if rd is not None else None,
        rs1=regbits(rs1) if rs1 is not None else None,
        rs2=regbits(rs2) if rs2 is not None else None,
        imm=wordbits(imm),
    )


# ============================================================
# Empty generic stage
# Students should put their own logic in process_instruction()
# ============================================================

class GenericStage(Stage):
    def __init__(self, name, behind_latch=None, ahead_latch=None):
        super().__init__(name=name, behind_latch=behind_latch, ahead_latch=ahead_latch)
        self.holding = None

    def process_instruction(self, instr: simple_instruction, cycle: int):
        """
        TODO:
        Add custom stage logic here.

        Examples:
        - modify instruction fields
        - attach debug info
        - simulate ALU work
        - simulate memory behavior
        - do nothing and just pass the instruction through
        """
        return instr

    def compute(self, cycle):
        if self.holding is None and self.behind_latch is not None:
            self.holding = self.behind_latch.pop()
            if self.holding is not None:
                self.holding.mark_stage_enter(self.name, cycle)

        instr = self.holding
        if instr is None:
            print(f"{self.name}: idle")
            return

        instr = self.process_instruction(instr, cycle)

        if self.ahead_latch is None:
            instr.mark_stage_exit(self.name, cycle)
            instr.mark_writeback(cycle)
            print(f"{self.name}: completed {instr_str(instr)}")
            self.holding = None
            return

        ok = self.ahead_latch.push(instr)
        if not ok:
            print(f"{self.name}: stall (ahead latch blocked) holding {instr_str(instr)}")
            return

        instr.mark_stage_exit(self.name, cycle)
        print(f"{self.name}: forwarded {instr_str(instr)}")
        self.holding = None


# ============================================================
# Program setup
# Start empty. Students add their own instructions.
# ============================================================

def build_program():
    """
    TODO:
    Add instructions here.
    """
    return deque([
        # Example:
        # make_instruction(pc=0, imm=10),
        # make_instruction(pc=4, imm=20),
    ])


# ============================================================
# Pipeline setup
# Start with empty generic stages.
# Students can rename, add, remove, or subclass them.
# ============================================================

def build_pipeline():
    input_latch = LatchIF(name="INPUT")
    latch_1 = LatchIF(name="L1")
    latch_2 = LatchIF(name="L2")

    stage_a = GenericStage(
        name="StageA",
        behind_latch=input_latch,
        ahead_latch=latch_1,
    )

    stage_b = GenericStage(
        name="StageB",
        behind_latch=latch_1,
        ahead_latch=latch_2,
    )

    stage_c = GenericStage(
        name="StageC",
        behind_latch=latch_2,
        ahead_latch=None,
    )

    return {
        "input_latch": input_latch,
        "latch_1": latch_1,
        "latch_2": latch_2,
        "stage_a": stage_a,
        "stage_b": stage_b,
        "stage_c": stage_c,
    }


# ============================================================
# Debug printing
# ============================================================

def dump_latch(name, latch):
    if latch.valid:
        print(f"  {name}: {instr_str(latch.payload)}")
    else:
        print(f"  {name}: empty")


def dump_state(cycle, pipeline):
    print(f"\n================ CYCLE {cycle} ================")
    dump_latch("INPUT", pipeline["input_latch"])
    dump_latch("L1", pipeline["latch_1"])
    dump_latch("L2", pipeline["latch_2"])


# ============================================================
# Main experiment loop
# ============================================================

def run_experiment():
    program = build_program()
    pipeline = build_pipeline()

    input_latch = pipeline["input_latch"]
    stage_a = pipeline["stage_a"]
    stage_b = pipeline["stage_b"]
    stage_c = pipeline["stage_c"]

    def feed_input():
        if program and input_latch.ready_for_push():
            instr = program.popleft()
            input_latch.push(instr)
            print(f"FEEDER: inserted {instr_str(instr)}")

    for cycle in range(MAX_CYCLES):
        dump_state(cycle, pipeline)

        # Run downstream -> upstream
        stage_c.compute(cycle)
        stage_b.compute(cycle)
        stage_a.compute(cycle)
        feed_input()

        done = (
            not program
            and not pipeline["input_latch"].valid
            and not pipeline["latch_1"].valid
            and not pipeline["latch_2"].valid
            and stage_a.holding is None
            and stage_b.holding is None
            and stage_c.holding is None
        )
        if done:
            print(f"\nPipeline drained at cycle {cycle}.")
            break

    print("\n================ COMPLETED ================")
    print("Experiment finished.")


if __name__ == "__main__":
    run_experiment()