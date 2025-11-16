# decode_test.py — Comprehensive tests for DecodeStage

import sys
from pathlib import Path
parent = Path(__file__).resolve().parent.parent
sys.path.append(str(parent))

from base import LatchIF, ForwardingIF, Instruction
from units.decode import DecodeStage
from units.pred_reg_file import PredicateRegFile
from bitstring import Bits


# ------------------------------------------------------------
# Helper: run stage until output appears
# ------------------------------------------------------------
def run_stage(stage, behind, ahead, cycles=50):
    for _ in range(cycles):
        stage.compute()
        if ahead.valid:
            return ahead.pop()
    return None


# ------------------------------------------------------------
# Utility to wrap a 32-bit word into Bits
# ------------------------------------------------------------
def bits32(x):
    return Bits(uint=x & 0xFFFFFFFF, length=32)


# ------------------------------------------------------------
# Build encoded instruction fields concisely
# ------------------------------------------------------------
def encode_inst(opcode, rd, rs1, rs2, pred=0, mop=0, eop=0, barrier=0):
    raw = 0
    raw |= (opcode & 0x7F)                # opcode7
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

    # --------------------------------------------------------
    # Shared predicate file
    # --------------------------------------------------------
    prf = PredicateRegFile(num_preds_per_warp=16, num_warps=8)

    # --------------------------------------------------------
    # Latches + forwarding
    # --------------------------------------------------------
    fetch_dec = LatchIF("Fetch→Decode")
    dec_exec  = LatchIF("Decode→Exec")

    ihit_if = ForwardingIF("ICache_Decode_Ihit")

    decode = DecodeStage(
        name="Decode",
        behind_latch=fetch_dec,
        ahead_latch=dec_exec,
        prf=prf,
        forward_ifs_read={"ICache_Decode_Ihit": ihit_if},
        forward_ifs_write={}
    )

    # ========================================================
    # TEST 1: ihit stall + recovery
    # ========================================================
    print("TEST 1: ihit stall + resume")

    inst = Instruction(
        iid=0,
        pc=0x1000,
        warp=0,
        warpGroup=0,
        opcode=None,
        rs1=0,
        rs2=0,
        rd=0,      
        packet=encode_inst(0, 2, 3, 4))

    fetch_dec.push(inst)

    ihit_if.push(False)
    ihit_if.set_wait(True)
    out = run_stage(decode, fetch_dec, dec_exec)
    assert out is None, "Decode must stall when ihit=False"

    ihit_if.push(True)
        # Unlock the forwarding interface completely

    ihit_if.set_wait(False)
    ihit_if.payload = None      # CLEAR OLD ihit=False event

    # Now send NEW ihit=True event
    ihit_if.push(True)

    out = run_stage(decode, fetch_dec, dec_exec)
    assert out is not None

    print("TEST 1 PASSED\n")

    # ========================================================
    # TEST 2: All opcode mappings decode correctly
    # ========================================================
    print("TEST 2: opcode mapping")

    opcode_map = {
        0b0000000: "add",
        0b0000001: "sub",
        0b0000010: "mul",
        0b0000011: "div",
        0b0100000: "lw",
        0b0110000: "sw",
        0b1000000: "beq",
        0b1100000: "jal",
        0b1111111: "halt",
    }

    for opc, mnemonic in opcode_map.items():
        fetch_dec.clear_all()
        dec_exec.clear_all()
        ihit_if.payload = None
        ihit_if.wait = False

        inst = Instruction(    
            iid=0,
            pc=0x200 + opc,
            warp=1,
            warpGroup=0,
            opcode=None,
            rs1=0,
            rs2=0,
            rd=0,      
            packet=encode_inst(opc, 1, 2, 3))

        fetch_dec.push(inst)
        ihit_if.push(True)
        out = run_stage(decode, fetch_dec, dec_exec)
        assert out.opcode == mnemonic, f"Expected {mnemonic}, got {out.opcode}"
        print(f"\n[PASSED] UPDATED INST CLASS WITH: {inst}")

    print("TEST 2 PASSED\n")

    # ========================================================
    # TEST 3: Register decode boundaries (0–63)
    # ========================================================
    print("TEST 3: register index extraction")

    fetch_dec.clear_all(); dec_exec.clear_all(); ihit_if.wait = False; ihit_if.payload = None

    inst = Instruction(
            iid=0,
            pc=0x300,
            warp=0,
            warpGroup=0,
            opcode=None,
            rs1=0,
            rs2=0,
            rd=0,     
            packet=encode_inst(0, 63, 62, 61))

    fetch_dec.push(inst)
    ihit_if.push(True)
    out = run_stage(decode, fetch_dec, dec_exec)
    assert out.rd == 63
    assert out.rs1 == 62
    assert out.rs2 == 61
    print(f"\n[PASSED] DECODED rd {out.rd}, rs1 {out.rs1}, rs2 {out.rs2}")
    print("TEST 3 PASSED\n")

    # ========================================================
    # TEST 4: EOP, MOP, Barrier bit extraction
    # ========================================================
    print("TEST 4: control bits")

    inst = Instruction(iid=0,
            pc=0x400,
            warp=0,
            warpGroup=0,
            opcode=None,
            rs1=0,
            rs2=0,
            rd=0, 
            packet=encode_inst(0, 1, 1, 1, mop=1, eop=1, barrier=1))


    fetch_dec.push(inst)
    ihit_if.push(True)
    out = run_stage(decode, fetch_dec, dec_exec)

    assert out.type.EOP
    assert out.type.MOP
    assert out.type.Barrier
    print(f"\n[PASSED] DECODE FORWARDED EOP: {out.type.EOP}, MOP: {out.type.Barrier} w/ PC: {out.pc}, WARPID: {out.warp_id}")
    print("TEST 4 PASSED\n")

    # ========================================================
    # TEST 5: Predicate register read behavior
    # ========================================================
    print("TEST 5: predicate register access")

    # Program warp=2, pred index=7 with custom mask
    mask = [True]*10 + [False]*22
    prf.write_predicate(prf_wr_en=1, prf_wr_wsel=2, prf_wr_psel=7, prf_wr_data=mask)

    inst = Instruction(iid=0,
            pc=0x500,
            warp=2,
            warpGroup=0,
            opcode=None,
            rs1=0,
            rs2=0,
            rd=0, packet=encode_inst(0, 1, 1, 1, pred=7))

    fetch_dec.push(inst)
    ihit_if.push(True)
    out = run_stage(decode, fetch_dec, dec_exec)
    

    assert out.pred == mask, "Predicate mask returned from PRF is wrong"

    print("TEST 5 PASSED\n")

    # ========================================================
    # TEST 6: Each warp returns different predicate banks
    # ========================================================
    print("TEST 6: warp-indexed predicate reads")

    # Write different masks for warp 0 and warp 3
    mask0 = [True]*32
    mask3 = [False]*32
    prf.write_predicate(1,0,5,mask0)
    prf.write_predicate(1,3,5,mask3)

    # Warp=0
    inst = Instruction(iid=0,
            pc=0x600,
            warp=0,
            warpGroup=0,
            opcode=None,
            rs1=0,
            rs2=0,
            rd=0, packet=encode_inst(0,0,0,0,pred=5))

    fetch_dec.push(inst); ihit_if.push(True); out0 = run_stage(decode, fetch_dec, dec_exec)
    assert out0.pred == mask0

    # Warp=3
    inst = Instruction(iid=0,
            pc=0x604,
            warp=3,
            warpGroup=0,
            opcode=None,
            rs1=0,
            rs2=0,
            rd=0, packet=encode_inst(0,0,0,0,pred=5))

    fetch_dec.push(inst); ihit_if.push(True); out3 = run_stage(decode, fetch_dec, dec_exec)
    assert out3.pred == mask3

    print("TEST 6 PASSED\n")

    # ========================================================
    # TEST 7: Streaming multiple instructions through decode
    # ========================================================
    print("TEST 7: multi-instruction streaming")

    stream = [
        encode_inst(0b0000000, 1,2,3),     # add
        encode_inst(0b0100000, 4,5,6),     # lw
        encode_inst(0b0110000, 7,8,9),     # sw
        encode_inst(0b1111111, 0,0,0),     # halt
    ]

    for i, rawbits in enumerate(stream):
        inst = Instruction(iid=0,
            pc= 0x800 + i*4,
            warp=0,
            warpGroup=0,
            opcode=None,
            rs1=0,
            rs2=0,
            rd=0, packet=rawbits)

        fetch_dec.push(inst)
        ihit_if.push(True)
        out = run_stage(decode, fetch_dec, dec_exec)

        assert out is not None

    print("TEST 7 PASSED\n")

    print("\n====== ALL DECODE TESTS PASSED SUCCESSFULLY ======\n")


if __name__ == "__main__":
    test_decode_stage_full()
