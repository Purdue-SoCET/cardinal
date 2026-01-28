# test_mem_controller.py — cycle-driven tests for MemController

import sys
from pathlib import Path

parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

from base import LatchIF, Instruction
from Memory import Mem
from units.mem import MemController
from bitstring import Bits


# -----------------------------
# Helpers
# -----------------------------
def bits32(x: int) -> Bits:
    return Bits(uint=(x & 0xFFFFFFFF), length=32)

def check_out_smoke_1(got):
    assert got is not None, "Expected a response but got none"
    assert got.get("src") in ("icache", "ICache", "i$","ic"), f"Bad src in resp: {got.get('src')}"
    assert got["rw_mode"] == "read"
    if got["uuid"] == 1:
        assert got["addr"] == 0x1000
        assert got["uuid"] == 1
        assert "data" in got, "Read response missing data"
        return True
    elif got["uuid"] == 2:
        assert got["addr"] == 0x1004
        assert got["uuid"] == 2
        assert "data" in got, "Read response missing data"
        return True
    elif got["uuid"] == 3:
        assert got["addr"] == 0x1008
        assert got["uuid"] == 3
        assert "data" in got, "Read response missing data"
        return True
    elif got["uuid"] == 4:
        assert got["addr"] == 0x100A
        assert got["uuid"] == 4
        assert "data" in got, "Read response missing data"
        return True
    elif got["uuid"] == 5:
        assert got["addr"] == 0x100E
        assert got["uuid"] == 5
        assert "data" in got, "Read response missing data"
        return True
    elif got["uuid"] == 6:
        assert got["addr"] == 0x1010
        assert got["uuid"] == 6
        assert "data" in got, "Read response missing data"
        return True
def make_inst(iid: int, pc: int, warp: int = 0, warpGroup: int = 0) -> Instruction:
    # Adjust fields if your Instruction signature differs
    return Instruction(
        iid=iid,
        pc=bits32(pc),
        warp=warp,
        warpGroup=warpGroup,
        opcode=None,
        rs1=Bits(uint=0, length=6),
        rs2=Bits(uint=0, length=6),
        rd=Bits(uint=0, length=6),
        intended_FSU=None,
    )


def make_req_dict(
    addr: int,
    uuid: int,
    warp: int,
    pc: int,
    size: int = 4,
    rw_mode: str = "read",
    data=None,
    inst: Instruction | None = None,
    warpGroup: int = 0,
) -> dict:

    if inst is None:
        inst = make_inst(uuid, pc, warp=warp, warpGroup=warpGroup)

    return {
        "addr": int(addr),
        "size": int(size),
        "uuid": int(uuid),
        "warp": int(warp),
        "warpGroup": int(warpGroup),
        "pc": int(pc),
        "rw_mode": rw_mode,
        "data": data,
        "inst": inst,
    }


def latch_ready_for_push(latch: LatchIF) -> bool:
    """
    Some of your latches expose ready_for_push().
    If not, assume a 1-entry latch: ready if not valid.
    """
    if hasattr(latch, "ready_for_push"):
        return bool(latch.ready_for_push())
    return not bool(getattr(latch, "valid", False))


def step_cycle(memc: MemController, cycle: int, debug: bool = False) -> None:
    if debug:
        inflight_n = len(getattr(memc, "inflight", []))
        pic = len(getattr(memc, "pending_ic", []))
        pdc = len(getattr(memc, "pending_dc", []))
        print(f"[cycle={cycle}] inflight={inflight_n} pending_ic={pic} pending_dc={pdc}")
    memc.compute()


def drain_one_if_valid(latch: LatchIF):
    if getattr(latch, "valid", False):
        return latch.pop()
    return None


# -----------------------------
# Tests
# -----------------------------
def test_smoke_icache_reads_fixed_latency():

    mem = Mem(
        start_pc=0x1000,
        input_file="/home/shay/a/sing1018/Desktop/SoCET_GPU_FuncSim/gpu/gpu_sim/cyclesim/test.bin",
        fmt="bin",
    )

    ic_req = LatchIF("ICacheMemReqIF")
    dc_req = LatchIF("DCacheMemReqIF")
    ic_resp = LatchIF("ICacheMemRespIF")
    dc_resp = LatchIF("DCacheMemRespIF")

    LAT = 10  # keep small for unit test
    memc = MemController(
        name="Memory_Controller",
        ic_req_latch=ic_req,
        dc_req_latch=dc_req,
        ic_serve_latch=ic_resp,
        dc_serve_latch=dc_resp,
        mem_backend=mem,
        latency=LAT,
        policy="rr"
    )

    # Issue one I$ read at cycle 0
    print("Smoke Test #1: Sending ICache Requests @ LAT intervals")

    req0 = make_req_dict(addr=0x1000, uuid=1, warp=0, pc=0x1000, size=4, rw_mode="read")
    req1 = make_req_dict(addr=0x1004, uuid=2, warp=0, pc=0x1004, size=4, rw_mode="read")
    req2 = make_req_dict(addr=0x1008, uuid=3, warp=0, pc=0x1008, size=4, rw_mode="read")
    req3 = make_req_dict(addr=0x100A, uuid=4, warp=0, pc=0x100A, size=4, rw_mode="read")
    req4 = make_req_dict(addr=0x100E, uuid=5, warp=0, pc=0x100E, size=4, rw_mode="read")
    req5 = make_req_dict(addr=0x1010, uuid=6, warp=0, pc=0x1010, size=4, rw_mode="read")
    smoke_1 = [req0, req1, req2, req3, req4, req5]
    
    for test in smoke_1:
        ic_req.push(test)
        got = None

        # loop through LAT cycles and then some 
        for c in range(LAT + 3):
            # before completion, should not have response
            if c < LAT:
                assert not getattr(ic_resp, "valid", False), f"Unexpected early resp at cycle {c}"
            step_cycle(memc, c, debug=False)
            got = drain_one_if_valid(ic_resp) or got

        test_pass = check_out_smoke_1(got)
        if test_pass == True:
            print(f"[OK] ICache read returned after ~latency window for test case: {got["uuid"]} for {test["pc"]}, got instruction {got["data"]}")

    print("\nSmoke Test #2: Queued I$ Requests with LAT = 5\n")

    LAT = 5
    PEND = 2
    MAX_INFLIGHT = 1
    # Fresh controller so no leftover inflight state
    memc2 = MemController(
        name="Memory_Controller_2",
        ic_req_latch=ic_req,
        dc_req_latch=dc_req,
        ic_serve_latch=ic_resp,
        dc_serve_latch=dc_resp,
        mem_backend=mem,
        latency=LAT,
        policy="rr"
    )

    # Clear latches
    ic_req.clear_all()
    ic_resp.clear_all()
    dc_req.clear_all()
    dc_resp.clear_all()

    burst = smoke_1[:]  # 6 requests

    resp_uuids = set()
    stall_cycles = 0
    max_inflight_seen = 0
    next_to_push = 0


    for cycle in range(0, 200):  # longer because we are serialized by max_inflight=1

        # Try to inject aggressively
        if next_to_push < len(burst) and latch_ready_for_push(ic_req):
            ic_req.push(burst[next_to_push])
            next_to_push += 1

        # Step controller
        step_cycle(memc2, cycle, debug=False)

        # Track inflight cap behavior
        inflight_n = len(getattr(memc2, "inflight", []))
        max_inflight_seen = max(max_inflight_seen, inflight_n)

        # Count stall cycles: latch is full while controller is busy
        if getattr(ic_req, "valid", False) and inflight_n >= MAX_INFLIGHT:
            stall_cycles += 1

        # Drain responses
        r = drain_one_if_valid(ic_resp)
        if r:
            resp_uuids.add(r["uuid"])

        # Early exit once everything returned
        if len(resp_uuids) == len(burst):
            break

    # Assertions

    # 1) We should see some backpressure stall (since we try to push burst while controller is busy)
    assert stall_cycles > 0, "[FAIL] Expected input-latch backpressure stalls, saw none."

    # 2) We should never exceed max inflight
    assert max_inflight_seen <= MAX_INFLIGHT, (
        f"[FAIL] inflight exceeded cap: max_inflight_seen={max_inflight_seen}, cap={MAX_INFLIGHT}"
    )

    # 3) All issued UUIDs should come back
    issued = {r["uuid"] for r in burst}
    assert issued.issubset(resp_uuids), f"[FAIL] Missing responses: {sorted(list(issued - resp_uuids))}"

    print(f"[OK] Backpressure observed (stall_cycles={stall_cycles}).")
    print(f"[OK] max inflight respected (max_inflight_seen={max_inflight_seen}).")
    print(f"[OK] All responses returned: {sorted(list(resp_uuids))}")

def test_smoke_rr_arbitration_interleaved():
    print("\nSmoke Test #3: RR arbitration with interleaved I$ + D$ (max_inflight=1)\n")

    mem = Mem(
        start_pc=0x1000,
        input_file="/home/shay/a/sing1018/Desktop/SoCET_GPU_FuncSim/gpu/gpu_sim/cyclesim/test.bin",
        fmt="bin",
    )

    ic_req = LatchIF("ICacheMemReqIF")
    dc_req = LatchIF("DCacheMemReqIF")
    ic_resp = LatchIF("ICacheMemRespIF")
    dc_resp = LatchIF("DCacheMemRespIF")

    LAT = 5
    memc = MemController(
        name="Memory_Controller_RR",
        ic_req_latch=ic_req,
        dc_req_latch=dc_req,
        ic_serve_latch=ic_resp,
        dc_serve_latch=dc_resp,
        mem_backend=mem,
        latency=LAT,
        policy="rr",
        max_inflight=1,
    )

    ic_req.clear_all(); dc_req.clear_all()
    ic_resp.clear_all(); dc_resp.clear_all()

    # Interleave requests: IC, DC, IC, DC
    # Use distinct addr ranges to avoid confusion.
    reqs = [
        ("ic", make_req_dict(addr=0x1000, uuid=101, warp=0, pc=0x1000, size=4, rw_mode="read")),
        ("dc", make_req_dict(addr=0x2000, uuid=201, warp=1, pc=0x2000, size=4, rw_mode="read")),
        ("ic", make_req_dict(addr=0x1004, uuid=102, warp=0, pc=0x1004, size=4, rw_mode="read")),
        ("dc", make_req_dict(addr=0x2004, uuid=202, warp=1, pc=0x2004, size=4, rw_mode="read")),
    ]

    issued = 0
    returned = []  # list of tuples: (src, uuid)

    for cycle in range(0, 200):

        # Push next request whenever its latch is free
        if issued < len(reqs):
            tag, r = reqs[issued]
            if tag == "ic" and latch_ready_for_push(ic_req):
                ic_req.push(r); issued += 1
            elif tag == "dc" and latch_ready_for_push(dc_req):
                dc_req.push(r); issued += 1

        step_cycle(memc, cycle, debug=False)

        r_ic = drain_one_if_valid(ic_resp)
        if r_ic:
            returned.append(("ic", r_ic["uuid"]))

        r_dc = drain_one_if_valid(dc_resp)
        if r_dc:
            returned.append(("dc", r_dc["uuid"]))

        if len(returned) == len(reqs):
            break

    assert len(returned) == len(reqs), f"[FAIL] Expected {len(reqs)} responses, got {len(returned)}"
    got_uuids = [u for (_, u) in returned]
    exp_uuids = [r["uuid"] for (_, r) in reqs]
    assert got_uuids == exp_uuids, f"[FAIL] RR interleave order mismatch. expected={exp_uuids} got={got_uuids}"

    # Proof of arbitration: both sources serviced and sequence alternates
    got_srcs = [s for (s, _) in returned]
    assert got_srcs == ["ic", "dc", "ic", "dc"], f"[FAIL] Expected alternating service, got {got_srcs}"

    print(f"[OK] RR arbitration honored interleaving. returned={returned}")

def test_smoke_rr_arbitration_both_valid():
    print("\nSmoke Test #3: RR arbitration proof (both latches valid at arbitration)\n")

    mem = Mem(
        start_pc=0x1000,
        input_file="/home/shay/a/sing1018/Desktop/SoCET_GPU_FuncSim/gpu/gpu_sim/cyclesim/test.bin",
        fmt="bin",
    )

    ic_req = LatchIF("ICacheMemReqIF")
    dc_req = LatchIF("DCacheMemReqIF")
    ic_resp = LatchIF("ICacheMemRespIF")
    dc_resp = LatchIF("DCacheMemRespIF")

    LAT = 5
    memc = MemController(
        name="Memory_Controller_RR",
        ic_req_latch=ic_req,
        dc_req_latch=dc_req,
        ic_serve_latch=ic_resp,
        dc_serve_latch=dc_resp,
        mem_backend=mem,
        latency=LAT,
        policy="rr",
        max_inflight=1,
    )

    ic_req.clear_all(); dc_req.clear_all()
    ic_resp.clear_all(); dc_resp.clear_all()

    pairs = [
        (make_req_dict(addr=0x1000, uuid=101, warp=0, pc=0x1000, rw_mode="read"),
         make_req_dict(addr=0x2000, uuid=201, warp=1, pc=0x2000, rw_mode="read")),
        (make_req_dict(addr=0x1004, uuid=102, warp=0, pc=0x1004, rw_mode="read"),
         make_req_dict(addr=0x2004, uuid=202, warp=1, pc=0x2004, rw_mode="read")),
    ]

    returned = []  # ("ic"/"dc", uuid)

    for i, (ic_r, dc_r) in enumerate(pairs):
        # --- Ensure both latches are loaded BEFORE allowing controller to pick ---
        assert latch_ready_for_push(ic_req)
        assert latch_ready_for_push(dc_req)
        ic_req.push(ic_r)
        dc_req.push(dc_r)

        # Run until BOTH responses from this pair arrive
        need = {ic_r["uuid"], dc_r["uuid"]}
        for cycle in range(0, 200):
            step_cycle(memc, cycle, debug=False)

            r_ic = drain_one_if_valid(ic_resp)
            if r_ic:
                returned.append(("ic", r_ic["uuid"]))
                need.discard(r_ic["uuid"])

            r_dc = drain_one_if_valid(dc_resp)
            if r_dc:
                returned.append(("dc", r_dc["uuid"]))
                need.discard(r_dc["uuid"])

            if not need:
                break

        assert not need, f"[FAIL] Did not receive both responses for pair {i}: missing={need}"

    # Now verify RR alternation WHEN both were valid at each choice point.
    # Depending on initial rr state, first winner could be ic or dc, but it should alternate.
    src_seq = [s for (s, _) in returned]
    assert len(src_seq) == 4

    # Split into pairs of two completions (because max_inflight=1, each loaded pair drains in 2 responses)
    pair1 = src_seq[0:2]
    pair2 = src_seq[2:4]

    # Each pair must contain both sources (proof that neither starves within the pair)
    assert set(pair1) == {"ic", "dc"}, f"[FAIL] Pair1 did not service both: {pair1}"
    assert set(pair2) == {"ic", "dc"}, f"[FAIL] Pair2 did not service both: {pair2}"

    # RR proof: first winner should flip across consecutive 'both-valid' arbitration points
    w1 = pair1[0]
    w2 = pair2[0]
    assert w1 != w2, f"[FAIL] RR winner did not alternate across pairs: winner1={w1}, winner2={w2}, seq={src_seq}"

    print(f"[OK] RR arbitration proven. pair1={pair1} pair2={pair2} full={src_seq}")

def test_smoke_icache_priority_over_dcache():
    print("\nSmoke Test #4: icache_prio policy favors I$ when both valid\n")

    mem = Mem(
        start_pc=0x1000,
        input_file="/home/shay/a/sing1018/Desktop/SoCET_GPU_FuncSim/gpu/gpu_sim/cyclesim/test.bin",
        fmt="bin",
    )

    ic_req = LatchIF("ICacheMemReqIF")
    dc_req = LatchIF("DCacheMemReqIF")
    ic_resp = LatchIF("ICacheMemRespIF")
    dc_resp = LatchIF("DCacheMemRespIF")

    memc = MemController(
        name="Memory_Controller_ICPRIO",
        ic_req_latch=ic_req,
        dc_req_latch=dc_req,
        ic_serve_latch=ic_resp,
        dc_serve_latch=dc_resp,
        mem_backend=mem,
        latency=4,
        policy="icache_prio",
        max_inflight=1,
    )

    ic_req.clear_all(); dc_req.clear_all()
    ic_resp.clear_all(); dc_resp.clear_all()

    # Make BOTH valid early, then see which completes first.
    ic_req.push(make_req_dict(addr=0x1000, uuid=301, warp=0, pc=0x1000))
    dc_req.push(make_req_dict(addr=0x2000, uuid=401, warp=1, pc=0x2000))

    returned = []
    for c in range(0, 100):
        step_cycle(memc, c, debug=False)
        r_ic = drain_one_if_valid(ic_resp)
        if r_ic: returned.append(("ic", r_ic["uuid"]))
        r_dc = drain_one_if_valid(dc_resp)
        if r_dc: returned.append(("dc", r_dc["uuid"]))
        if len(returned) == 2:
            break

    assert len(returned) == 2, f"[FAIL] Expected 2 responses, got {len(returned)}"
    assert returned[0][0] == "ic", f"[FAIL] Expected I$ to complete first under icache_prio, got {returned}"
    print(f"[OK] icache_prio served I$ before D$: {returned}")

def test_smoke_dcache_write_then_readback():
    print("\nSmoke Test #5: D$ write then readback verifies Mem.write path\n")

    mem = Mem(
        start_pc=0x1000,
        input_file="/home/shay/a/sing1018/Desktop/SoCET_GPU_FuncSim/gpu/gpu_sim/cyclesim/test.bin",
        fmt="bin",
    )

    ic_req = LatchIF("ICacheMemReqIF")
    dc_req = LatchIF("DCacheMemReqIF")
    ic_resp = LatchIF("ICacheMemRespIF")
    dc_resp = LatchIF("DCacheMemRespIF")

    LAT = 3
    memc = MemController(
        name="Memory_Controller_DWRITE",
        ic_req_latch=ic_req,
        dc_req_latch=dc_req,
        ic_serve_latch=ic_resp,
        dc_serve_latch=dc_resp,
        mem_backend=mem,
        latency=LAT,
        policy="rr",
        max_inflight=1,
    )

    ic_req.clear_all(); dc_req.clear_all()
    ic_resp.clear_all(); dc_resp.clear_all()

    addr = 0x2000
    val = 0xDEADBEEF

    # 1) Write
    assert latch_ready_for_push(dc_req)
    dc_req.push(make_req_dict(addr=addr, uuid=501, warp=1, pc=0x9000, size=4, rw_mode="write", data=val))

    got_write = None
    for c in range(0, 50):
        step_cycle(memc, c, debug=False)
        got_write = drain_one_if_valid(dc_resp) or got_write
        if got_write and got_write.get("rw_mode") == "write":
            break

    assert got_write is not None, "[FAIL] Expected a D$ write response."
    assert got_write["rw_mode"] == "write"
    assert got_write.get("status") == "WRITE_DONE"
    assert got_write["addr"] == addr
    assert got_write["uuid"] == 501

    # 2) Read back
    assert latch_ready_for_push(dc_req)
    dc_req.push(make_req_dict(addr=addr, uuid=502, warp=1, pc=0x9004, size=4, rw_mode="read"))

    got_read = None
    for c in range(50, 120):
        step_cycle(memc, c, debug=False)
        got_read = drain_one_if_valid(dc_resp) or got_read
        if got_read and got_read.get("rw_mode") == "read":
            break

    assert got_read is not None, "[FAIL] Expected a D$ read response."
    assert got_read["rw_mode"] == "read"
    assert got_read["addr"] == addr
    assert got_read["uuid"] == 502

    # Data is Bits; compare to uint
    data_bits = got_read["data"]
    got_val = int.from_bytes(data_bits.tobytes()[:4], "little", signed=False)
    assert got_val == (val & 0xFFFFFFFF), (
        f"[FAIL] Readback mismatch: expected=0x{val:08x} got=0x{got_val:08x}"
    )

    print(f"[OK] D$ write/readback success: wrote=0x{val:08x} read=0x{got_val:08x}")


def test_smoke_response_backpressure_blocks_completion():
    print("\nSmoke Test #6: Response latch backpressure blocks completion until drained\n")

    mem = Mem(
        start_pc=0x1000,
        input_file="/home/shay/a/sing1018/Desktop/SoCET_GPU_FuncSim/gpu/gpu_sim/cyclesim/test.bin",
        fmt="bin",
    )

    ic_req = LatchIF("ICacheMemReqIF")
    dc_req = LatchIF("DCacheMemReqIF")
    ic_resp = LatchIF("ICacheMemRespIF")
    dc_resp = LatchIF("DCacheMemRespIF")

    LAT = 4
    memc = MemController(
        name="Memory_Controller_RESPBP",
        ic_req_latch=ic_req,
        dc_req_latch=dc_req,
        ic_serve_latch=ic_resp,
        dc_serve_latch=dc_resp,
        mem_backend=mem,
        latency=LAT,
        policy="rr",
        max_inflight=1,
    )

    ic_req.clear_all(); dc_req.clear_all()
    ic_resp.clear_all(); dc_resp.clear_all()

    # Fill dc_resp latch so controller can't push into it
    assert dc_resp.ready_for_push()
    dc_resp.push({"src": "dcache", "dummy": True})

    # Issue a D$ read
    dc_req.push(make_req_dict(addr=0x2000, uuid=601, warp=1, pc=0xA000, size=4, rw_mode="read"))

    # Run past latency: request should be ready but blocked on resp latch full
    for c in range(0, LAT + 10):
        step_cycle(memc, c, debug=False)

    # Dummy still present, and real response should NOT have overwritten it
    assert dc_resp.valid, "[FAIL] Expected dc_resp to remain occupied."
    cur = dc_resp.snoop()
    assert cur is not None and cur.get("dummy") is True, "[FAIL] Response latch changed despite being full."

    # inflight should still have the request because it couldn't retire
    assert len(memc.inflight) == 1, f"[FAIL] Expected inflight to retain blocked completion, inflight={len(memc.inflight)}"

    # Drain dummy and let completion occur
    dc_resp.pop()

    got = None
    for c in range(LAT + 10, LAT + 40):
        step_cycle(memc, c, debug=False)
        got = drain_one_if_valid(dc_resp) or got
        if got and got.get("uuid") == 601:
            break

    assert got is not None, "[FAIL] Expected completion after backpressure cleared."
    assert got["uuid"] == 601
    assert got["rw_mode"] == "read"
    print("[OK] Completion occurred after draining response latch backpressure.")

def test_mem_controller_all():
    test_smoke_icache_reads_fixed_latency()
    test_smoke_rr_arbitration_both_valid()
    test_smoke_icache_priority_over_dcache()
    test_smoke_dcache_write_then_readback()
    test_smoke_response_backpressure_blocks_completion()
    print("\nALL MEM CONTROLLER TESTS PASSED.\n")


if __name__ == "__main__":
    test_mem_controller_all()

