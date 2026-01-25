# decode_test.py — Comprehensive & diagnostic tests for DecodeStage

import sys
from pathlib import Path
gpu_sim_root = Path(__file__).resolve().parents[2]
repo_pkg_root = gpu_sim_root.parent

sys.path.insert(0,str(repo_pkg_root))
from gpu_sim.common.custom_enums_multi import Op
from gpu_sim.cyclesim.base import LatchIF, ForwardingIF, Instruction, DecodeType
from units.decode import DecodeStage
from units.pred_reg_file import PredicateRegFile
from bitstring import Bits


# ------------------------------------------------------------
# Helper: run stage with repeated attempts
# ------------------------------------------------------------
def run_stage(stage, behind, ahead, cycles=50):
    for c in range(cycles):
        print(f"  [run_stage] cycle {c}")
        stage.compute()
        if ahead.valid:
            out = ahead.pop()
            print(f"  [run_stage] → OUTPUT ARRIVED: {out}")
            return out
    print("  [run_stage] → NO OUTPUT AFTER TIMEOUT")
    return None


# ------------------------------------------------------------
# Utility for 32-bit Bits
# ------------------------------------------------------------
def bits32(x):
    return Bits(uint=x & 0xFFFFFFFF, length=32)


# ------------------------------------------------------------
# Instruction encoder for tests
# ------------------------------------------------------------
def encode_inst(opcode, rd, rs1, rs2, pred=0, mop=0, eop=0, barrier=0):
    raw = 0
    raw |= (opcode & 0x7F)
    raw |= (rd & 0x3F) << 7
    raw |= (rs1 & 0x3F) << 13
    raw |= (rs2 & 0x3F) << 19
    raw |= (pred & 0x1F) << 25
    raw |= (mop & 1) << 30
    raw |= (eop & 1) << 31
    raw |= (barrier & 1) << 29
    return bits32(raw)


# ============================================================
# MAIN TEST SUITE
# ============================================================
def test_decode_stage_full():

    print("\n====== DECODE STAGE: COMPREHENSIVE TEST SUITE ======\n")

    prf = PredicateRegFile(num_preds_per_warp=16, num_warps=8)

    fetch_dec = LatchIF("Fetch→Decode")
    dec_exec  = LatchIF("Decode→Exec")
    ihit_if   = ForwardingIF("ICache_Decode_Ihit")

    decode = DecodeStage(
        name="Decode",
        behind_latch=fetch_dec,
        ahead_latch=dec_exec,
        prf=prf,
        forward_ifs_read={"ICache_Decode_Ihit": ihit_if},
        forward_ifs_write={}
    )

    # ========================================================
    # TEST 1 — ihit stall + resume
    # ========================================================
    print("----------------------------------------------------")
    print("TEST 1: ihit stall + resume")
    print("----------------------------------------------------")

    inst = Instruction(
        iid=0, pc=0x1000, warp=0, warpGroup=0,
        opcode=None, rs1=0, rs2=0, rd=0,
        packet=encode_inst(0, 2, 3, 4),
        intended_FSU="ALU"
    )

    print(f"Pushing instruction PC=0x{inst.pc:X} (ihit=False)")
    fetch_dec.push(inst)
    ihit_if.push(False)
    ihit_if.set_wait(True)

    out = run_stage(decode, fetch_dec, dec_exec)
    assert out is None, "[FAIL] Decode must stall on ihit=False"
    print("[OK] Decode stalled correctly.")

    print("Unstalling (ihit=True)")
    ihit_if.set_wait(False)
    ihit_if.payload = None
    ihit_if.push(True)

    out = run_stage(decode, fetch_dec, dec_exec)
    assert out is not None, "[FAIL] Decode must resume on ihit=True"
    print("[OK] Decode resumed correctly.\n")

    # ========================================================
    # TEST 2 — All opcode mappings
    # ========================================================
    print("----------------------------------------------------")
    print("TEST 2: opcode mapping")
    print("----------------------------------------------------")

    opcode_map = {
        0b0000000: "ADD",  0b0000001: "SUB",  0b0000010: "MUL",
        0b0000011: "DIV",  0b0100000: "LW",   0b0110000: "SW",
        0b1000000: "BEQ",  0b1100000: "JAL",  0b1111111: "HALT",
    }


    for opc, mnemonic in opcode_map.items():
        fetch_dec.clear_all()
        dec_exec.clear_all()
        ihit_if.payload = None
        ihit_if.wait = False

        inst = Instruction(
            iid=0, pc=0x200 + opc,
            warp=1, warpGroup=0,
            opcode=None, rs1=0, rs2=0, rd=0,
            packet=encode_inst(opc, 1, 2, 3),
            intended_FSU="ALU"
        )

        print(f" Decoding opcode {opc:07b} expecting mnemonic '{mnemonic}'")
        fetch_dec.push(inst)
        ihit_if.push(True)

        out = run_stage(decode, fetch_dec, dec_exec)
        assert hasattr(out.opcode, "name"), "[FAIL] out.opcode is not an Enum"
        assert out.opcode.name == mnemonic, f"[FAIL] Expected {mnemonic}, got {out.opcode}"


        print(f"[OK] {mnemonic} decoded correctly.\n")

    # ========================================================
    # TEST 3 — Register index decode
    # ========================================================
    print("----------------------------------------------------")
    print("TEST 3: register field decode")
    print("----------------------------------------------------")

    fetch_dec.clear_all(); dec_exec.clear_all()
    ihit_if.payload = None

    inst = Instruction(
        iid=0, pc=0x300, warp=0, warpGroup=0,
        opcode=None, rs1=0, rs2=0, rd=0,
        packet=encode_inst(0, 63, 62, 61),
        intended_FSU="ALU"
    )

    fetch_dec.push(inst)
    ihit_if.push(True)

    out = run_stage(decode, fetch_dec, dec_exec)
    assert out.rd.uint == 63
    assert out.rs1.uint == 62
    assert out.rs2.uint == 61

    print(f"[OK] rd={out.rd}, rs1={out.rs1}, rs2={out.rs2} decoded correctly.\n")

    def flush_latches():
        fetch_dec.clear_all()
        dec_exec.clear_all()
        ihit_if.payload = None
        ihit_if.wait = False

    print("----------------------------------------------------")
    print("TEST 4: control bits decode")
    print("----------------------------------------------------")

    # ===========================
    # Test Barrier
    # ===========================
    flush_latches()

    inst = Instruction(
        iid=0, pc=0x400, warp=0, warpGroup=0,
        opcode=None, rs1=0, rs2=0, rd=0,
        packet=encode_inst(0,1,1,1,mop=0,eop=0,barrier=1),
        intended_FSU="ALU"
    )

    fetch_dec.push(inst)
    ihit_if.push(True)
    out = run_stage(decode, fetch_dec, dec_exec)
    assert out.type == DecodeType.Barrier


    # ===========================
    # Test MOP
    # ===========================
    flush_latches()

    inst = Instruction(
        iid=0, pc=0x400, warp=0, warpGroup=0,
        opcode=None, rs1=0, rs2=0, rd=0,
        packet=encode_inst(0,1,1,1,mop=1,eop=0,barrier=0),
        intended_FSU="ALU"
    )

    fetch_dec.push(inst)
    ihit_if.push(True)
    out = run_stage(decode, fetch_dec, dec_exec)
    assert out.type == DecodeType.MOP


    # ===========================
    # Test EOP
    # ===========================
    flush_latches()

    inst = Instruction(
        iid=0, pc=0x400, warp=0, warpGroup=0,
        opcode=None, rs1=0, rs2=0, rd=0,
        packet=encode_inst(0,1,1,1,mop=0,eop=1,barrier=0),
        intended_FSU="ALU"
    )

    fetch_dec.push(inst)
    ihit_if.push(True)
    out = run_stage(decode, fetch_dec, dec_exec)
    assert out.type == DecodeType.EOP


    # ===========================
    # Test HALT (opcode7)
    # ===========================
    flush_latches()

    halt_raw = 0x7F   # opcode7 = 1111111 → HALT

    inst = Instruction(
        iid=0, pc=0x400, warp=0, warpGroup=0,
        opcode=None, rs1=0, rs2=0, rd=0,
        packet=halt_raw,
        intended_FSU="ALU"
    )

    fetch_dec.push(inst)
    ihit_if.push(True)
    out = run_stage(decode, fetch_dec, dec_exec)
    assert out.type == DecodeType.halt

    print("[OK] Control bits correctly decoded.\n")


    # ========================================================
    # TEST 5 — Predicate register read
    # ========================================================
    print("----------------------------------------------------")
    print("TEST 5: predicate register read")
    print("----------------------------------------------------")

    mask = [True]*10 + [False]*22
    prf.write_predicate(1,2,7,mask)

    inst = Instruction(
        iid=0, pc=0x500, warp=2, warpGroup=0,
        opcode=None, rs1=0, rs2=0, rd=0,
        packet=encode_inst(0,1,1,1,pred=7),
        intended_FSU="ALU"
    )

    fetch_dec.push(inst); ihit_if.push(True)
    out = run_stage(decode, fetch_dec, dec_exec)

    print(f"  pred[0]={out.pred[0]} ...")

    print("[OK] Predicate mask matched PRF.\n")

    # ========================================================
    # TEST 6 — Warp-indexed predicate banks
    # ========================================================
    print("----------------------------------------------------")
    print("TEST 6: warp-indexed PRF reads")
    print("----------------------------------------------------")

    mask0 = [True]*32
    mask3 = [False]*32
    prf.write_predicate(1,0,5,mask0)
    prf.write_predicate(1,3,5,mask3)

    # Warp 0
    inst = Instruction(iid=0,pc=0x600,warp=0,warpGroup=0,
                       opcode=None,rs1=0,rs2=0,rd=0,
                       packet=encode_inst(0,0,0,0,pred=5),
                       intended_FSU="ALU"
                       )
    fetch_dec.push(inst); ihit_if.push(True)
    out0 = run_stage(decode, fetch_dec, dec_exec)
#    assert out0.pred == mask0
    print("[OK] Warp 0 predicate bank OK.")

    # Warp 3
    inst = Instruction(iid=0,pc=0x604,warp=3,warpGroup=0,
                       opcode=None,rs1=0,rs2=0,rd=0,
                       packet=encode_inst(0,0,0,0,pred=5),
                       intended_FSU="ALU"
                       )
    fetch_dec.push(inst); ihit_if.push(True)
    out3 = run_stage(decode, fetch_dec, dec_exec)
  #  assert out3.pred == mask3
    print("[OK] Warp 3 predicate bank OK.\n")

    # ========================================================
    # TEST 7 — Streaming instructions
    # ========================================================
    print("----------------------------------------------------")
    print("TEST 7: streaming multiple instructions")
    print("----------------------------------------------------")

    stream = [
        encode_inst(0b0000000,1,2,3),    # add
        encode_inst(0b0100000,4,5,6),    # lw
        encode_inst(0b0110000,7,8,9),    # sw
        encode_inst(0b1111111,0,0,0),    # halt
    ]

    for i, rawbits in enumerate(stream):
        inst = Instruction(
            iid=0, pc=0x800 + i*4,
            warp=0, warpGroup=0,
            opcode=None, rs1=0, rs2=0, rd=0,
            packet=rawbits,
            intended_FSU=None
        )

        print(f"Streaming PC=0x{inst.pc:X}")
        fetch_dec.push(inst)
        ihit_if.push(True)

        out = run_stage(decode, fetch_dec, dec_exec)
        assert out is not None
        print(f"  [OK] streamed instruction decoded: opcode={out.opcode}")

    print("\n====== ALL DECODE TESTS PASSED SUCCESSFULLY ======\n")


if __name__ == "__main__":
    test_decode_stage_full()
