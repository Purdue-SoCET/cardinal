# branch_fu_ext_test.py — Extended BranchFU execution-mask tests

import sys
from pathlib import Path
parent = Path(__file__).resolve().parent.parent
sys.path.append(str(parent))

from typing import Optional, Dict
from base import LatchIF, ForwardingIF, Instruction, Stage
from units.branch_fu import BranchFU
from units.pred_reg_file import PredicateRegFile


def vec(val):
    """Make a uniform 32-wide warp vector."""
    return [val for _ in range(32)]

def vec_pattern(pattern):
    """Expand small bitmask into 32-wide repeating pattern."""
    full = []
    for lane in range(32):
        full.append(pattern[lane % len(pattern)])
    return full


# ------------------------------------------------------------
# Wrapper Exec Stage
# ------------------------------------------------------------
class ExecStage(Stage):
    def __init__(self, name, behind_latch, ahead_latch):
        super().__init__(name=name, behind_latch=behind_latch, ahead_latch=ahead_latch)

    def compute(self, input_data=None):
        if not self.behind_latch.valid:
            return

        inst = self.behind_latch.pop()

        # Immediately stop further compute() on same cycle
        self.behind_latch.valid = False

        br = BranchFU(
            instructions=inst,
            prf_rd_data=inst.pred,
            op_1=inst.rs1_vals,
            op_2=inst.rs2_vals,
        )

        pred_out = br.update_pred()

        if self.ahead_latch.ready_for_push():
            self.ahead_latch.push({
                "warp": inst.warp,
                "pc": inst.pc,
                "pred_out": pred_out
            })

def drain_latch(l):
    while l.valid:
        l.pop()

def make_inst(op, incoming_pred, op1, op2):
    """Helper to construct branch instruction with provided lanes."""
    mapping = {
        "beq": 0,
        "bne": 1,
        "bge": 2,
        "bgeu": 3,
        "blt": 4,
        "bltu": 5,
    }
    inst = Instruction(
        iid=0, pc=0x0, warp=0, warpGroup=0,
        opcode=mapping[op],
        rs1=0, rs2=0, rd=0,
        packet=None
    )
    inst.pred = incoming_pred[:]     # incoming execution mask
    inst.rs1_vals = op1[:]           # per-lane operand 1
    inst.rs2_vals = op2[:]           # per-lane operand 2
    return inst


# ------------------------------------------------------------
# Test Suite
# ------------------------------------------------------------
def test_branch_fu_execution_masks():

    print("\n========== BRANCH FU — EXECUTION MASK TESTS ==========\n")

    iBranch = LatchIF("Input")
    oBranch = LatchIF("Output")
    exec_stage = ExecStage("ExecBranch", iBranch, oBranch)


    # --------------------------------------------------------
    # TEST 1: Partial incoming mask AND'ed with branch taken
    # --------------------------------------------------------
    print("TEST 1: Incoming mask AND TnT results")

    incoming = vec_pattern([1, 0])      # 101010...
    op1 = vec(5)
    op2 = vec(5)                        # beq → TAKEN
    inst = make_inst("beq", incoming, op1, op2)

    iBranch.push(inst)
    exec_stage.compute()

    out = oBranch.pop()["pred_out"]
    expected = [bool(incoming[i] and True) for i in range(32)]
    assert out == expected
    print("[PASSED] Incoming mask correctly AND'ed with taken result\n")


    # --------------------------------------------------------
    # TEST 2: Nested if:  if(A) then if(B)
    # --------------------------------------------------------
    print("TEST 2: Nested IF → IF (A then B)")

    # First branch A enables half the warp
    A_pred = vec_pattern([1, 1, 0, 0])    # lanes 0–1 active, 2–3 inactive repeating
    A_inst = make_inst("beq", A_pred, vec(3), vec(3))  # always taken

    iBranch.push(A_inst)
    exec_stage.compute()
    A_out = oBranch.pop()["pred_out"]

    # Now branch B only passes lanes where rs1 < rs2
    B_op1 = vec_pattern([1, 9, 1, 9])   # 1<2 → true on 0, 2
    B_op2 = vec_pattern([2, 2, 2, 2])
    B_inst = make_inst("blt", A_out, B_op1, B_op2)

    iBranch.push(B_inst)
    exec_stage.compute()
    B_out = oBranch.pop()["pred_out"]

    # Expected: lanes where both A and B are true
    expected = [(A_pred[i] == 1 and B_op1[i] < B_op2[i]) for i in range(32)]
    assert B_out == expected
    print("[PASSED] Nested IF correctness\n")


    # --------------------------------------------------------
    # TEST 3: Simulating compound AND  (A && B && C)
    # --------------------------------------------------------
    print("TEST 3: Compound AND logic  A && B && C")

    pred_A = vec_pattern([1, 0])                    # activate even lanes
    pred_B = vec_pattern([1, 1, 0, 0])               # 2-on, 2-off
    pred_C = vec_pattern([1, 0, 1, 0])               # checkerboard

    # Step 1: A
    A_inst = make_inst("beq", pred_A, vec(1), vec(1))
    iBranch.push(A_inst); exec_stage.compute()
    A_out = oBranch.pop()["pred_out"]

    # Step 2: A && B
    B_inst = make_inst("beq", A_out, vec_pattern([1,2,3,4]), vec_pattern([1,2,0,4]))
    iBranch.push(B_inst); exec_stage.compute()
    B_out = oBranch.pop()["pred_out"]

    # Step 3: (A && B) && C
    C_inst = make_inst("beq", B_out, pred_C, pred_C)
    iBranch.push(C_inst); exec_stage.compute()
    C_out = oBranch.pop()["pred_out"]

    # Golden model
    expected = [
        bool(pred_A[i] and pred_B[i] and pred_C[i])
        for i in range(32)
    ]

    assert C_out == expected
    print("[PASSED] Compound (A && B && C) predicate logic\n")


    # --------------------------------------------------------
    # TEST 4: Simulated OR logic using mask merges
    # --------------------------------------------------------
    print("TEST 4: OR logic  (A OR B)")

    pred_A = vec_pattern([1, 0, 0, 0])   # lane 0 active every 4
    pred_B = vec_pattern([0, 1, 0, 0])   # lane 1 active every 4

    # A branch taken (beq)
    A_inst = make_inst("beq", pred_A, vec(7), vec(7))
    iBranch.push(A_inst); exec_stage.compute()
    A_mask = oBranch.pop()["pred_out"]

    # B branch taken (beq)
    B_inst = make_inst("beq", pred_B, vec(7), vec(7))
    iBranch.push(B_inst); exec_stage.compute()
    B_mask = oBranch.pop()["pred_out"]

    # OR composition — compiler or warp-scheduler logic would merge
    OR_mask = [A_mask[i] or B_mask[i] for i in range(32)]

    expected = [
        bool(pred_A[i] or pred_B[i])
        for i in range(32)
    ]

    assert OR_mask == expected
    print("[PASSED] OR logic validated\n")


    # --------------------------------------------------------
    # TEST 5: Deep nesting  A → (B && C) → (D OR E)
    # --------------------------------------------------------
    # Flush previous pipeline state
    drain_latch(iBranch)
    drain_latch(oBranch)

    print("TEST 5: Deep conditional structure")

    pred_A = vec_pattern([1,1,0,0])
    pred_B = vec_pattern([1,0,1,0])
    pred_C = vec_pattern([1,1,1,0])
    pred_D = vec_pattern([0,1,0,1])
    pred_E = vec_pattern([1,0,0,1])

    # A
    inst_A = make_inst("beq", pred_A, vec(2), vec(2))
    iBranch.push(inst_A); exec_stage.compute()
    mask_A = oBranch.pop()["pred_out"]

    # A && B
    inst_B = make_inst("beq", mask_A, pred_B, pred_B)
    iBranch.push(inst_B); exec_stage.compute()
    mask_B = oBranch.pop()["pred_out"]

    # (A && B) && C
    inst_C = make_inst("beq", mask_B, pred_C, pred_C)
    iBranch.push(inst_C); exec_stage.compute()
    mask_C = oBranch.pop()["pred_out"]

    # D (taken)
    inst_D = make_inst("beq", mask_C, pred_D, pred_D)
    iBranch.push(inst_D); exec_stage.compute()
    mask_D = oBranch.pop()["pred_out"]

    # E (taken)
    inst_E = make_inst("beq", mask_C, pred_E, pred_E)
    iBranch.push(inst_E); exec_stage.compute()
    mask_E = oBranch.pop()["pred_out"]

    # Final = (A && B && C && D) OR (A && B && C && E)
    OR_final = [(mask_D[i] or mask_E[i]) for i in range(32)]
    print()
    expected = [
        bool(pred_A[i] and pred_B[i] and pred_C[i])
        for i in range(32)
    ]


    print(OR_final)
    print(expected)
    assert OR_final == expected
    print("[PASSED] Deep-nested branching logic\n")

    print("\n========== ALL EXTENDED BRANCH TESTS PASSED ==========\n")


if __name__ == "__main__":
    test_branch_fu_execution_masks()
