"""
FusedMul and AddSub Unit Tests

FusedMul
    1.1  Reset / no metastability
    1.2  Single FP32 multiply, same sign
    1.3  Single FP32 multiply, different sign
    1.4  FP32 × 0 = 0
    1.5  FP32 overflow → inf
    2.1  Single INT32 multiply
    2.2  Single INT32 multiply, different sign
    2.3  INT32 × 0 = 0
    2.4  INT32 overflow → lower 32 bits
    3.1  ULP error check (100 random FP32)
    4.1  Burst FP32
    4.2  Burst INT32
    4.3  Burst mode switching (FP ↔ INT)
    5.1  Mixed burst with stall

AddSub
    1.1  Reset / no metastability
    1.2  Single FP32 add & sub, same sign
    1.3  Single FP32 add & sub, different sign
    1.6  FP32 op with 0
    1.7  FP32 overflow → inf
    2.1  Single INT32 add & sub, same sign
    2.2  Single INT32 add & sub, different sign
    2.5  INT32 op with 0
    2.6  INT32 overflow → lower 32 bits
    3.1  ULP error check (100 random FP32)
    4.1  Burst FP32 (add & sub)
    4.2  Burst INT32 (add & sub)
    4.3  Burst mode switching (FP ↔ INT)
    4.4  Mixed burst with stall
"""

import math
import random
import struct
import sys
from pathlib import Path

from bitstring import Bits
from gpu.common.custom_enums_multi import R_Op, I_Op
from simulator.latch_forward_stage import Instruction
from simulator.execute.stage import ExecuteStage, FunctionalUnitConfig

sys.path.insert(0, str(Path(__file__).parent))
from ex_stage_test import (
    PipelineTestHarness,
    create_instruction,
    create_predicate,
    print_test_header,
    Colors,
)


"FP down to 32 bits"
def _fp32(v: float) -> float:
    FP32_MAX = 3.4028235e+38
    if math.isinf(v) or math.isnan(v):
        return v
    if v > FP32_MAX:
        return math.inf
    if v < -FP32_MAX:
        return -math.inf
    return struct.unpack(">f", struct.pack(">f", v))[0]


"measuer ulp"
def _ulp32(v: float) -> float:
    if v == 0.0:
        return struct.unpack(">f", struct.pack(">I", 1))[0]
    packed = struct.pack(">f", abs(v))
    bits = struct.unpack(">I", packed)[0]
    return abs(struct.unpack(">f", struct.pack(">I", (bits + 1) & 0xFFFFFFFF))[0] - abs(v))


def _within_half_ulp(got: float, ref: float) -> bool:
    if math.isinf(ref) or math.isnan(ref):
        return True 
    ulp = _ulp32(ref) if ref != 0.0 else 1e-45
    return abs(got - ref) <= 0.5 * ulp + 1e-45



def _get_fsu(harness, fsu_name):
    """Retrieve an FSU object by name from the execute stage."""
    for fu in harness.ex_stage.functional_units.values():
        if fsu_name in fu.subunits:
            return fu.subunits[fsu_name]
    raise KeyError(f"FSU '{fsu_name}' not found in execute stage")


 
# MUL BLOCK
 """1.1 — Reset: pipeline empty, ready_out True, EX/WB latch empty."""
def test_fusedmul_1_1_reset(harness):
    print_test_header("FusedMul 1.1 — Reset")

    results = []
    for type_name in ("int", "float"):
        fsu_name = f"FusedMul_{type_name}_0"
        try:
            fsu = _get_fsu(harness, fsu_name)
            results.append((f"FusedMul {type_name}: pipeline empty on reset",
                            all(s is None for s in fsu.pipeline.queue)))
            results.append((f"FusedMul {type_name}: ready_out True on reset",
                            fsu.ready_out is True))
            results.append((f"FusedMul {type_name}: EX/WB latch empty on reset",
                            not fsu.ex_wb_interface.valid))
        except KeyError as e:
            print(Colors.yellow(f"  SKIP: {e}"))
    return results


def test_fusedmul_1_2_fp32_same_sign(harness):
 """1.2 — Single FP32 multiply, same sign."""

    print_test_header("FusedMul 1.2 — FP32 same sign")

    tests = [
        ("MULF pos×pos", 3.5, 2.0),
        ("MULF neg×neg", -1.5, -4.0),
    ]
    for name, a, b in tests:
        ref = _fp32(_fp32(a) * _fp32(b))
        instr = create_instruction(
            opcode=R_Op.MULF,
            intended_fsu="FusedMul_float_0",
            rdat1_vals=a, rdat2_vals=b, is_float=True,
            pc_value=hash(name) & 0xFFFF,
        )
        harness.issue_instruction(
            instr,
            validation_func=lambda r, expected=ref: all(
                abs(r.wdat[i].float - expected) < 1e-4
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


"""1.3 — Single FP32 multiply, different sign."""
def test_fusedmul_1_3_fp32_diff_sign(harness):
    print_test_header("FusedMul 1.3 — FP32 different sign")

    tests = [
        ("MULF pos×neg", 3.0, -2.5),
        ("MULF neg×pos", -6.0, 2.0),
    ]
    for name, a, b in tests:
        ref = _fp32(_fp32(a) * _fp32(b))
        instr = create_instruction(
            opcode=R_Op.MULF,
            intended_fsu="FusedMul_float_0",
            rdat1_vals=a, rdat2_vals=b, is_float=True,
            pc_value=hash(name) & 0xFFFF,
        )
        harness.issue_instruction(
            instr,
            validation_func=lambda r, expected=ref: all(
                abs(r.wdat[i].float - expected) < 1e-4
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()

 """1.4 — FP32 × 0 = 0."""
def test_fusedmul_1_4_fp32_zero(harness): 
   
    print_test_header("FusedMul 1.4 — FP32 zero")

    tests = [
        ("MULF a×0",   99999.9,  0.0),
        ("MULF 0×b",   0.0,      -5.5),
        ("MULF 0×0",   0.0,       0.0),
    ]
    for name, a, b in tests:
        instr = create_instruction(
            opcode=R_Op.MULF,
            intended_fsu="FusedMul_float_0",
            rdat1_vals=a, rdat2_vals=b, is_float=True,
            pc_value=hash(name) & 0xFFFF,
        )
        harness.issue_instruction(
            instr,
            validation_func=lambda r: all(
                r.wdat[i].float == 0.0
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()



def test_fusedmul_1_5_fp32_overflow(harness):
    """1.5 — FP32 overflow → inf."""
    print_test_header("FusedMul 1.5 — FP32 overflow")

    tests = [
        ("MULF +overflow", 3.4028235e+38,  2.0),
        ("MULF -overflow", -3.4028235e+38, 2.0),
    ]
    for name, a, b in tests:
        instr = create_instruction(
            opcode=R_Op.MULF,
            intended_fsu="FusedMul_float_0",
            rdat1_vals=a, rdat2_vals=b, is_float=True,
            pc_value=hash(name) & 0xFFFF,
        )
        harness.issue_instruction(
            instr,
            validation_func=lambda r: all(
                math.isinf(r.wdat[i].float)
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


"""2.1 — Single INT32 multiply, positive values."""
def test_fusedmul_2_1_int32_normal(harness):
    print_test_header("FusedMul 2.1 — INT32 normal")

    tests = [
        ("MUL 6×7=42",   6,   7,   42),
        ("MUL 100×3=300", 100, 3,  300),
        ("MUL 1×1=1",    1,   1,    1),
    ]
    for name, a, b, expected in tests:
        instr = create_instruction(
            opcode=R_Op.MUL,
            intended_fsu="FusedMul_int_0",
            rdat1_vals=a, rdat2_vals=b, is_float=False,
            pc_value=hash(name) & 0xFFFF,
        )
        harness.issue_instruction(
            instr,
            validation_func=lambda r, exp=expected: all(
                r.wdat[i].int == exp
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


"""2.2 — Single INT32 multiply, different sign."""
def test_fusedmul_2_2_int32_diff_sign(harness):
    print_test_header("FusedMul 2.2 — INT32 different sign")

    tests = [
        ("MUL 10×-3=-30",  10,  -3,  -30),
        ("MUL -5×-5=25",   -5,  -5,   25),
        ("MUL -1×100=-100",-1, 100, -100),
    ]
    for name, a, b, expected in tests:
        instr = create_instruction(
            opcode=R_Op.MUL,
            intended_fsu="FusedMul_int_0",
            rdat1_vals=a, rdat2_vals=b, is_float=False,
            pc_value=hash(name) & 0xFFFF,
        )
        harness.issue_instruction(
            instr,
            validation_func=lambda r, exp=expected: all(
                r.wdat[i].int == exp
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


"""2.3 — INT32 × 0 = 0."""
def test_fusedmul_2_3_int32_zero(harness):
    print_test_header("FusedMul 2.3 — INT32 zero")

    tests = [
        ("MUL 12345×0",  12345, 0),
        ("MUL 0×99999",  0,     99999),
        ("MUL -7×0",     -7,    0),
    ]
    for name, a, b in tests:
        instr = create_instruction(
            opcode=R_Op.MUL,
            intended_fsu="FusedMul_int_0",
            rdat1_vals=a, rdat2_vals=b, is_float=False,
            pc_value=hash(name) & 0xFFFF,
        )
        harness.issue_instruction(
            instr,
            validation_func=lambda r: all(
                r.wdat[i].int == 0
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


def test_fusedmul_2_4_int32_overflow(harness):
    """2.4 — INT32 overflow → correct lower 32 bits."""
    print_test_header("FusedMul 2.4 — INT32 overflow")

    tests = [
       # lower 32 = 0
        ("MUL 0x10000×0x10000", 0x10000, 0x10000, 0x00000000),
       #  0xFFFFFFFE → lower 32 bits
        ("MUL MAX×2",           2147483647, 2, (2147483647 * 2) & 0xFFFFFFFF),
    ]
    for name, a, b, expected_uint in tests:
        instr = create_instruction(
            opcode=R_Op.MUL,
            intended_fsu="FusedMul_int_0",
            rdat1_vals=a, rdat2_vals=b, is_float=False,
            pc_value=hash(name) & 0xFFFF,
        )
        harness.issue_instruction(
            instr,
            validation_func=lambda r, exp=expected_uint: all(
                r.wdat[i].uint == exp
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


"""3.1 — 100 random FP32 multiplications within 0.5 ULP."""
def test_fusedmul_3_1_ulp(harness):
    print_test_header("FusedMul 3.1 — ULP accuracy")

    random.seed(0xDEADBEEF)
    FP32_SAFE = 1e30
    pc = 0x3000

    for i in range(100):
        a = random.uniform(-FP32_SAFE, FP32_SAFE)
        b = random.uniform(-FP32_SAFE, FP32_SAFE)
        # Reference uses FP32-rounded inputs (Bits(float=x) rounds on construction)
        a32, b32 = _fp32(a), _fp32(b)
        ref = _fp32(a32 * b32)

        if math.isinf(ref) or math.isnan(ref):
            continue

        instr = create_instruction(
            opcode=R_Op.MULF,
            intended_fsu="FusedMul_float_0",
            rdat1_vals=a, rdat2_vals=b, is_float=True,
            pc_value=pc,
        )
        pc += 4

        harness.issue_instruction(
            instr,
            validation_func=lambda r, expected=ref: all(
                _within_half_ulp(r.wdat[lane].float, expected)
                for lane in range(32) if r.predicate[lane].bin == "1"
            ),
            test_name=f"MULF ULP #{i}",
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


def test_fusedmul_4_1_burst_fp32(harness):
    """4.1 — Burst FP32: back-to-back multiplications, correct result every cycle."""
    print_test_header("FusedMul 4.1 — Burst FP32")

    BURST = 8
    pc = 0x4100
    for i in range(BURST):
        a = float(i + 1) * 1.1
        b = float(i + 1) * 0.9
        ref = _fp32(_fp32(a) * _fp32(b))
        instr = create_instruction(
            opcode=R_Op.MULF,
            intended_fsu="FusedMul_float_0",
            rdat1_vals=a, rdat2_vals=b, is_float=True,
            pc_value=pc,
        )
        pc += 4
        harness.issue_instruction(
            instr,
            validation_func=lambda r, expected=ref: all(
                abs(r.wdat[lane].float - expected) < 1e-4
                for lane in range(32) if r.predicate[lane].bin == "1"
            ),
            test_name=f"MULF burst #{i}",
        )
        harness.tick()
        #issue then tick for burst mode

    harness.run_until_complete()
    return harness.print_summary()


"""4.2 — Burst INT32: back-to-back multiplications, correct result every cycle."""
def test_fusedmul_4_2_burst_int32(harness):
    print_test_header("FusedMul 4.2 — Burst INT32")

    BURST = 8
    pc = 0x4200
    for i in range(BURST):
        a = i + 1
        b = i + 2
        expected = (a * b) & 0xFFFFFFFF
        instr = create_instruction(
            opcode=R_Op.MUL,
            intended_fsu="FusedMul_int_0",
            rdat1_vals=a, rdat2_vals=b, is_float=False,
            pc_value=pc,
        )
        pc += 4
        harness.issue_instruction(
            instr,
            validation_func=lambda r, exp=expected: all(
                r.wdat[lane].uint == exp
                for lane in range(32) if r.predicate[lane].bin == "1"
            ),
            test_name=f"MUL burst #{i}",
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


"""4.3 — Burst switching: alternating FP32 and INT32 back-to-back."""
def test_fusedmul_4_3_burst_switching(harness):
    print_test_header("FusedMul 4.3 — Burst mode switching")

    BURST = 8
    pc = 0x4300
    for i in range(BURST):
        if i % 2 == 0:
            instr = create_instruction(
                opcode=R_Op.MULF,
                intended_fsu="FusedMul_float_0",
                rdat1_vals=float(i + 1), rdat2_vals=2.0, is_float=True,
                pc_value=pc,
            )
            harness.issue_instruction(instr, validation_func=lambda r: True,
                                      test_name=f"MULF switch #{i}")
        else:
            instr = create_instruction(
                opcode=R_Op.MUL,
                intended_fsu="FusedMul_int_0",
                rdat1_vals=i + 1, rdat2_vals=3, is_float=False,
                pc_value=pc,
            )
            harness.issue_instruction(instr, validation_func=lambda r: True,
                                      test_name=f"MUL switch #{i}")
        pc += 4
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


    """5.1 — Mixed burst with stall: fill pipeline, block WB, verify backpressure
    and correct results after recovery."""
def test_fusedmul_5_1_stall(harness):
    print_test_header("FusedMul 5.1 — Mixed burst with stall")

    fsu_name = "FusedMul_float_0"
    fsu = _get_fsu(harness, fsu_name)
    results = []
    pc = 0x5100

    # issue one instruction
    target_a, target_b = 3.0, 4.0
    target_ref = _fp32(_fp32(target_a) * _fp32(target_b))
    target = create_instruction(
        opcode=R_Op.MULF, intended_fsu=fsu_name,
        rdat1_vals=target_a, rdat2_vals=target_b, is_float=True,
        pc_value=pc,
    )
    pc += 4
    harness.issue_instruction(target, validation_func=lambda r: True,
                              test_name="MULF stall: target issued")
    harness.tick()

    # block WB and fill the rest of the pipeline 
    harness.enable_wb_pop = False #the thingy to stall
    for i in range(fsu.pipeline.length + 2):
        dummy = create_instruction(
            opcode=R_Op.MULF, intended_fsu=fsu_name,
            rdat1_vals=1.0, rdat2_vals=1.0, is_float=True,
            pc_value=pc,
        )
        pc += 4
        harness.issue_instruction(dummy, validation_func=lambda r: True,
                                  test_name=f"MULF stall: fill #{i}", allow_stall=True) 
        harness.tick()

    results.append(("FusedMul stall: ready_out False when full+WB blocked",
                    fsu.ready_out is False))

    # unblock and drain
    harness.enable_wb_pop = True
    harness.run_until_complete()

    results.append(("FusedMul stall: ready_out True after recovery",
                    fsu.ready_out is True))

    # Validate target result survived the stall
    target_correct = any(
        t.result_instr is not None and
        all(abs(t.result_instr.wdat[i].float - target_ref) < 1e-4
            for i in range(32) if t.result_instr.predicate[i].bin == "1")
        for t in harness.completed_trackers
        if t.instr.pc == target.pc
    )
    results.append(("FusedMul stall: result correct after stall", target_correct))

    return results


# ADDSUB TESTS

def test_addsub_1_1_reset(harness):
    """1.1 — Reset: pipeline empty, ready_out True, EX/WB latch empty."""
    print_test_header("AddSub 1.1 — Reset")

    results = []
    for type_name in ("int", "float"):
        fsu_name = f"AddSub_{type_name}_0"
        try:
            fsu = _get_fsu(harness, fsu_name)
            results.append((f"AddSub {type_name}: pipeline empty on reset",
                            all(s is None for s in fsu.pipeline.queue)))
            results.append((f"AddSub {type_name}: ready_out True on reset",
                            fsu.ready_out is True))
            results.append((f"AddSub {type_name}: EX/WB latch empty on reset",
                            not fsu.ex_wb_interface.valid))
        except KeyError as e:
            print(Colors.yellow(f"  SKIP: {e}"))
    return results


def test_addsub_1_2_fp32_same_sign(harness):
    """1.2 — Single FP32 add & sub, same sign."""
    print_test_header("AddSub 1.2 — FP32 same sign")

    tests = [
        ("ADDF pos+pos", R_Op.ADDF, 1.5,  2.5),
        ("ADDF neg+neg", R_Op.ADDF, -3.0, -4.0),
        ("SUBF pos-pos", R_Op.SUBF, 5.0,  2.0),
        ("SUBF neg-neg", R_Op.SUBF, -8.0, -3.0),
    ]
    pc = 0x1200
    for name, opcode, a, b in tests:
        ref = _fp32(_fp32(a) + _fp32(b)) if opcode == R_Op.ADDF else _fp32(_fp32(a) - _fp32(b))
        instr = create_instruction(
            opcode=opcode, intended_fsu="AddSub_float_0",
            rdat1_vals=a, rdat2_vals=b, is_float=True,
            pc_value=pc,
        )
        pc += 4
        harness.issue_instruction(
            instr,
            validation_func=lambda r, expected=ref: all(
                abs(r.wdat[i].float - expected) < 1e-4
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


def test_addsub_1_3_fp32_diff_sign(harness):
    """1.3 — Single FP32 add & sub, different sign."""
    print_test_header("AddSub 1.3 — FP32 different sign")

    tests = [
        ("ADDF pos+neg", R_Op.ADDF, 5.0,  -3.0),
        ("ADDF neg+pos", R_Op.ADDF, -5.0,  3.0),
        ("SUBF pos-neg", R_Op.SUBF, 3.0,  -2.0),
        ("SUBF neg-pos", R_Op.SUBF, -3.0,  2.0),
    ]
    pc = 0x1300
    for name, opcode, a, b in tests:
        ref = _fp32(_fp32(a) + _fp32(b)) if opcode == R_Op.ADDF else _fp32(_fp32(a) - _fp32(b))
        instr = create_instruction(
            opcode=opcode, intended_fsu="AddSub_float_0",
            rdat1_vals=a, rdat2_vals=b, is_float=True,
            pc_value=pc,
        )
        pc += 4
        harness.issue_instruction(
            instr,
            validation_func=lambda r, expected=ref: all(
                abs(r.wdat[i].float - expected) < 1e-4
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


def test_addsub_1_6_fp32_zero(harness):
    """1.6 — FP32 op with 0."""
    print_test_header("AddSub 1.6 — FP32 zero")

    tests = [
        ("ADDF n+0=n",  R_Op.ADDF, 7.25,  0.0,  7.25),
        ("ADDF 0+n=n",  R_Op.ADDF, 0.0,   3.5,  3.5),
        ("SUBF n-0=n",  R_Op.SUBF, 7.25,  0.0,  7.25),
        ("SUBF 0-n=-n", R_Op.SUBF, 0.0,   3.5, -3.5),
    ]
    pc = 0x1600
    for name, opcode, a, b, expected in tests:
        ref = _fp32(expected)
        instr = create_instruction(
            opcode=opcode, intended_fsu="AddSub_float_0",
            rdat1_vals=a, rdat2_vals=b, is_float=True,
            pc_value=pc,
        )
        pc += 4
        harness.issue_instruction(
            instr,
            validation_func=lambda r, exp=ref: all(
                abs(r.wdat[i].float - exp) < 1e-4
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


def test_addsub_1_7_fp32_overflow(harness):
    """1.7 — FP32 overflow → inf."""
    print_test_header("AddSub 1.7 — FP32 overflow")

    BIG = 3.4028235e+38
    tests = [
        ("ADDF +overflow", R_Op.ADDF,  BIG,  BIG),
        ("SUBF -overflow", R_Op.SUBF, -BIG,  BIG),
    ]
    pc = 0x1700
    for name, opcode, a, b in tests:
        instr = create_instruction(
            opcode=opcode, intended_fsu="AddSub_float_0",
            rdat1_vals=a, rdat2_vals=b, is_float=True,
            pc_value=pc,
        )
        pc += 4
        harness.issue_instruction(
            instr,
            validation_func=lambda r: all(
                math.isinf(r.wdat[i].float)
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


def test_addsub_2_1_int32_same_sign(harness):
    """2.1 — Single INT32 add & sub, same sign."""
    print_test_header("AddSub 2.1 — INT32 same sign")

    tests = [
        ("ADD pos+pos",   R_Op.ADD, 10,   20,  30),
        ("ADD neg+neg",   R_Op.ADD, -10, -20, -30),
        ("SUB pos-pos",   R_Op.SUB, 20,    8,  12),
        ("SUB neg-neg",   R_Op.SUB, -5,   -2,  -3),
    ]
    pc = 0x2100
    for name, opcode, a, b, expected in tests:
        fsu = "AddSub_int_0"
        instr = create_instruction(
            opcode=opcode, intended_fsu=fsu,
            rdat1_vals=a, rdat2_vals=b, is_float=False,
            pc_value=pc,
        )
        pc += 4
        harness.issue_instruction(
            instr,
            validation_func=lambda r, exp=expected: all(
                r.wdat[i].int == exp
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


def test_addsub_2_2_int32_diff_sign(harness):
    """2.2 — Single INT32 add & sub, different sign."""
    print_test_header("AddSub 2.2 — INT32 different sign")

    tests = [
        ("ADD pos+neg",  R_Op.ADD, 10,  -3,   7),
        ("ADD neg+pos",  R_Op.ADD, -10,  3,  -7),
        ("SUB pos-neg",  R_Op.SUB,  5,  -5,  10),
        ("SUB neg-pos",  R_Op.SUB, -5,   5, -10),
        ("ADDI pos+imm", I_Op.ADDI, 10, 0,   15),  # imm patched below
        ("SUBI pos-imm", I_Op.SUBI, 10, 0,    7),  # imm patched below
    ]
    pc = 0x2200
    imm_map = {"ADDI pos+imm": 5, "SUBI pos-imm": 3}

    for name, opcode, a, b, expected in tests:
        instr = create_instruction(
            opcode=opcode, intended_fsu="AddSub_int_0",
            rdat1_vals=a, rdat2_vals=b, is_float=False,
            pc_value=pc,
        )
        if opcode in (I_Op.ADDI, I_Op.SUBI):
            instr.imm = Bits(length=32, int=imm_map[name])
        pc += 4
        harness.issue_instruction(
            instr,
            validation_func=lambda r, exp=expected: all(
                r.wdat[i].int == exp
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


def test_addsub_2_5_int32_zero(harness):
    """2.5 — INT32 op with 0."""
    print_test_header("AddSub 2.5 — INT32 zero")

    tests = [
        ("ADD n+0=n",  R_Op.ADD, 42,  0, 42),
        ("ADD 0+n=n",  R_Op.ADD,  0, 42, 42),
        ("SUB n-0=n",  R_Op.SUB, 99,  0, 99),
        ("SUB 0-n=-n", R_Op.SUB,  0, 42, -42),
    ]
    pc = 0x2500
    for name, opcode, a, b, expected in tests:
        instr = create_instruction(
            opcode=opcode, intended_fsu="AddSub_int_0",
            rdat1_vals=a, rdat2_vals=b, is_float=False,
            pc_value=pc,
        )
        pc += 4
        harness.issue_instruction(
            instr,
            validation_func=lambda r, exp=expected: all(
                r.wdat[i].int == exp
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


def test_addsub_2_6_int32_overflow(harness):
    """2.6 — INT32 overflow → correct lower 32 bits."""
    print_test_header("AddSub 2.6 — INT32 overflow")

    INT32_MAX = 2147483647
    INT32_MIN = -2147483648

    tests = [
        #  (0x8000_0000)
        ("ADD MAX+1 wraps",  R_Op.ADD, INT32_MAX, 1,          0x80000000),
        # (0x7FFF_FFFF)
        ("SUB MIN-1 wraps",  R_Op.SUB, INT32_MIN, 1,          0x7FFFFFFF),
        # Large add overflow
        ("ADD large overflow",R_Op.ADD, INT32_MAX, INT32_MAX,  (INT32_MAX + INT32_MAX) & 0xFFFFFFFF),
    ]
    pc = 0x2600
    for name, opcode, a, b, expected_uint in tests:
        instr = create_instruction(
            opcode=opcode, intended_fsu="AddSub_int_0",
            rdat1_vals=a, rdat2_vals=b, is_float=False,
            pc_value=pc,
        )
        pc += 4
        harness.issue_instruction(
            instr,
            validation_func=lambda r, exp=expected_uint: all(
                r.wdat[i].uint == exp
                for i in range(32) if r.predicate[i].bin == "1"
            ),
            test_name=name,
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


def test_addsub_3_1_ulp(harness):
    """3.1 — 100 random FP32 add/sub within 0.5 ULP."""
    print_test_header("AddSub 3.1 — ULP accuracy")

    FP32_SAFE = 1e30
    pc = 0x3100

    for opcode, label in [(R_Op.ADDF, "ADDF"), (R_Op.SUBF, "SUBF")]:
        random.seed(0xDEADBEEF)
        for i in range(100):
            a = random.uniform(-FP32_SAFE, FP32_SAFE)
            b = random.uniform(-FP32_SAFE, FP32_SAFE)
            a32, b32 = _fp32(a), _fp32(b)
            ref = _fp32(a32 + b32) if opcode == R_Op.ADDF else _fp32(a32 - b32)

            if math.isinf(ref) or math.isnan(ref):
                continue

            instr = create_instruction(
                opcode=opcode, intended_fsu="AddSub_float_0",
                rdat1_vals=a, rdat2_vals=b, is_float=True,
                pc_value=pc,
            )
            pc += 4
            harness.issue_instruction(
                instr,
                validation_func=lambda r, expected=ref: all(
                    _within_half_ulp(r.wdat[lane].float, expected)
                    for lane in range(32) if r.predicate[lane].bin == "1"
                ),
                test_name=f"{label} ULP #{i}",
            )
            harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


def test_addsub_4_1_burst_fp32(harness):
    """4.1 — Burst FP32 add & sub: back-to-back, correct result every cycle."""
    print_test_header("AddSub 4.1 — Burst FP32")

    BURST = 8
    pc = 0x4100
    for i in range(BURST):
        a = 1.5 * (i + 1)
        b = 0.5 * (i + 1)
        opcode = R_Op.ADDF if i % 2 == 0 else R_Op.SUBF
        ref = _fp32(_fp32(a) + _fp32(b)) if opcode == R_Op.ADDF else _fp32(_fp32(a) - _fp32(b))
        instr = create_instruction(
            opcode=opcode, intended_fsu="AddSub_float_0",
            rdat1_vals=a, rdat2_vals=b, is_float=True,
            pc_value=pc,
        )
        pc += 4
        harness.issue_instruction(
            instr,
            validation_func=lambda r, expected=ref: all(
                abs(r.wdat[lane].float - expected) < 1e-4
                for lane in range(32) if r.predicate[lane].bin == "1"
            ),
            test_name=f"{'ADDF' if opcode == R_Op.ADDF else 'SUBF'} burst #{i}",
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


def test_addsub_4_2_burst_int32(harness):
    """4.2 — Burst INT32 add & sub: back-to-back, correct result every cycle."""
    print_test_header("AddSub 4.2 — Burst INT32")

    BURST = 8
    pc = 0x4200
    for i in range(BURST):
        a = i + 1
        b = i + 10
        opcode = R_Op.ADD if i % 2 == 0 else R_Op.SUB
        expected = (a + b) & 0xFFFFFFFF if opcode == R_Op.ADD else (a - b) & 0xFFFFFFFF
        instr = create_instruction(
            opcode=opcode, intended_fsu="AddSub_int_0",
            rdat1_vals=a, rdat2_vals=b, is_float=False,
            pc_value=pc,
        )
        pc += 4
        harness.issue_instruction(
            instr,
            validation_func=lambda r, exp=expected: all(
                r.wdat[lane].uint == exp
                for lane in range(32) if r.predicate[lane].bin == "1"
            ),
            test_name=f"{'ADD' if opcode == R_Op.ADD else 'SUB'} burst #{i}",
        )
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


def test_addsub_4_3_burst_switching(harness):
    """4.3 — Burst mode switching: alternating FP32 and INT32 back-to-back."""
    print_test_header("AddSub 4.3 — Burst mode switching")

    BURST = 8
    pc = 0x4300
    for i in range(BURST):
        if i % 2 == 0:
            instr = create_instruction(
                opcode=R_Op.ADDF, intended_fsu="AddSub_float_0",
                rdat1_vals=float(i + 1), rdat2_vals=1.0, is_float=True,
                pc_value=pc,
            )
            harness.issue_instruction(instr, validation_func=lambda r: True,
                                      test_name=f"ADDF switch #{i}")
        else:
            instr = create_instruction(
                opcode=R_Op.ADD, intended_fsu="AddSub_int_0",
                rdat1_vals=i + 1, rdat2_vals=2, is_float=False,
                pc_value=pc,
            )
            harness.issue_instruction(instr, validation_func=lambda r: True,
                                      test_name=f"ADD switch #{i}")
        pc += 4
        harness.tick()

    harness.run_until_complete()
    return harness.print_summary()


def test_addsub_4_4_stall(harness):
    """4.4 — Mixed burst with stall: block WB, verify backpressure and result
    correctness after recovery."""
    print_test_header("AddSub 4.4 — Mixed burst with stall")

    fsu_name = "AddSub_float_0"
    fsu = _get_fsu(harness, fsu_name)
    results = []
    pc = 0x4400

    # issue one instruction 
    target_a, target_b = 3.0, 4.0
    target_ref = _fp32(_fp32(target_a) + _fp32(target_b))
    target = create_instruction(
        opcode=R_Op.ADDF, intended_fsu=fsu_name,
        rdat1_vals=target_a, rdat2_vals=target_b, is_float=True,
        pc_value=pc,
    )
    pc += 4
    harness.issue_instruction(target, validation_func=lambda r: True,
                              test_name="ADDF stall: target issued")
    harness.tick()

    # block WB latch and fill the pipeline 
    harness.enable_wb_pop = False
    for i in range(fsu.pipeline.length + 2):
        dummy = create_instruction(
            opcode=R_Op.ADDF, intended_fsu=fsu_name,
            rdat1_vals=1.0, rdat2_vals=1.0, is_float=True,
            pc_value=pc,
        )
        pc += 4
        harness.issue_instruction(dummy, validation_func=lambda r: True,
                                  test_name=f"ADDF stall: fill #{i}", allow_stall=True)
        harness.tick()

    results.append(("AddSub stall: ready_out False when full+WB blocked",
                    fsu.ready_out is False))

    #unblock WB and drain
    harness.enable_wb_pop = True
    harness.run_until_complete()

    results.append(("AddSub stall: ready_out True after recovery",
                    fsu.ready_out is True))

    # Verify result 
    target_correct = any(
        t.result_instr is not None and
        all(abs(t.result_instr.wdat[i].float - target_ref) < 1e-4
            for i in range(32) if t.result_instr.predicate[i].bin == "1")
        for t in harness.completed_trackers
        if t.instr.pc == target.pc
    )
    results.append(("AddSub stall: result correct after stall", target_correct))

    return results



#main

def main():
    print("\n" + Colors.bold(Colors.magenta("=" * 80)))
    print(Colors.bold(Colors.magenta("  FUSEDMUL + ADDSUB UNIT TEST SUITE")))
    print(Colors.bold(Colors.magenta("=" * 80)))

    config = FunctionalUnitConfig.get_default_config()
    fust = config.generate_fust_dict()
    ex_stage = ExecuteStage(config=config, fust=fust)
    harness = PipelineTestHarness(ex_stage)

    all_results = []

    # ---- FusedMul ----
    print("\n[1/14] FusedMul 1.1 reset...")
    all_results.extend(test_fusedmul_1_1_reset(harness))

    print("\n[2/14] FusedMul 1.2 FP32 same sign...")
    all_results.extend(test_fusedmul_1_2_fp32_same_sign(harness))
    harness.completed_trackers.clear()

    print("\n[3/14] FusedMul 1.3 FP32 different sign...")
    all_results.extend(test_fusedmul_1_3_fp32_diff_sign(harness))
    harness.completed_trackers.clear()

    print("\n[4/14] FusedMul 1.4 FP32 zero...")
    all_results.extend(test_fusedmul_1_4_fp32_zero(harness))
    harness.completed_trackers.clear()

    print("\n[5/14] FusedMul 1.5 FP32 overflow...")
    all_results.extend(test_fusedmul_1_5_fp32_overflow(harness))
    harness.completed_trackers.clear()

    print("\n[6/14] FusedMul 2.1-2.4 INT32...")
    all_results.extend(test_fusedmul_2_1_int32_normal(harness))
    harness.completed_trackers.clear()
    all_results.extend(test_fusedmul_2_2_int32_diff_sign(harness))
    harness.completed_trackers.clear()
    all_results.extend(test_fusedmul_2_3_int32_zero(harness))
    harness.completed_trackers.clear()
    all_results.extend(test_fusedmul_2_4_int32_overflow(harness))
    harness.completed_trackers.clear()

    print("\n[7/14] FusedMul 3.1 ULP...")
    all_results.extend(test_fusedmul_3_1_ulp(harness))
    harness.completed_trackers.clear()

    print("\n[8/14] FusedMul 4.1-4.3 burst + switching...")
    all_results.extend(test_fusedmul_4_1_burst_fp32(harness))
    harness.completed_trackers.clear()
    all_results.extend(test_fusedmul_4_2_burst_int32(harness))
    harness.completed_trackers.clear()
    all_results.extend(test_fusedmul_4_3_burst_switching(harness))
    harness.completed_trackers.clear()

    print("\n[9/14] FusedMul 5.1 stall...")
    all_results.extend(test_fusedmul_5_1_stall(harness))
    harness.completed_trackers.clear()

    # ---- AddSub ----
    print("\n[10/14] AddSub 1.1 reset...")
    all_results.extend(test_addsub_1_1_reset(harness))

    print("\n[11/14] AddSub 1.2-1.7 FP32...")
    all_results.extend(test_addsub_1_2_fp32_same_sign(harness))
    harness.completed_trackers.clear()
    all_results.extend(test_addsub_1_3_fp32_diff_sign(harness))
    harness.completed_trackers.clear()
    all_results.extend(test_addsub_1_6_fp32_zero(harness))
    harness.completed_trackers.clear()
    all_results.extend(test_addsub_1_7_fp32_overflow(harness))
    harness.completed_trackers.clear()

    print("\n[12/14] AddSub 2.1-2.6 INT32...")
    all_results.extend(test_addsub_2_1_int32_same_sign(harness))
    harness.completed_trackers.clear()
    all_results.extend(test_addsub_2_2_int32_diff_sign(harness))
    harness.completed_trackers.clear()
    all_results.extend(test_addsub_2_5_int32_zero(harness))
    harness.completed_trackers.clear()
    all_results.extend(test_addsub_2_6_int32_overflow(harness))
    harness.completed_trackers.clear()

    print("\n[13/14] AddSub 3.1 ULP...")
    all_results.extend(test_addsub_3_1_ulp(harness))
    harness.completed_trackers.clear()

    print("\n[14/14] AddSub 4.1-4.4 burst + stall...")
    all_results.extend(test_addsub_4_1_burst_fp32(harness))
    harness.completed_trackers.clear()
    all_results.extend(test_addsub_4_2_burst_int32(harness))
    harness.completed_trackers.clear()
    all_results.extend(test_addsub_4_3_burst_switching(harness))
    harness.completed_trackers.clear()
    all_results.extend(test_addsub_4_4_stall(harness))
    harness.completed_trackers.clear()

    # ---- Final summary ----
    print_test_header("FINAL SUMMARY")
    passed = sum(1 for _, r in all_results if r)
    total  = len(all_results)

    print(f"\nTotal: {Colors.bold(str(total))}")
    print(Colors.green(f"Passed: {passed}"))
    if total - passed:
        print(Colors.red(f"Failed: {total - passed}"))
        for name, r in all_results:
            if not r:
                print(Colors.red(f"  ✗ {name}"))
    else:
        print(Colors.green(Colors.bold("✓ All tests passed!")))

    print("\n" + Colors.cyan("=" * 80))
    print(Colors.bold(Colors.cyan("  TEST SUITE COMPLETE")))
    print(Colors.cyan("=" * 80) + "\n")


if __name__ == "__main__":
    main()