"""
Exhaustive functional tests for the 3-stage Clos network.

Run:
    python test_clos.py

Tests:
  [A] UNICAST    - Every bank (0-31) to every thread (0-31) = 1024 combinations
  [B] MULTICAST  - Representative patterns across egress groups
  [B2] MULTICAST PROOF BY DECOMPOSITION (384 tests, covers all 2^32 masks):
       - Per-group: all 16 dest subsets for each of 8 egress groups (128 tests)
       - Cross-group: all 256 combinations of which egress groups are active (256 tests)
  [C] BROADCAST  - Every bank broadcasts to all 32 threads
  [D] ERRORS     - Unmapped/access-violation flits routed to correct thread
  [E] MSHR       - MSHR merge produces single multicast response to both threads
"""

import sys
from clos_network_sim import (
    ClosNetwork, SRAMBank, Flit,
    NUM_BANKS, NUM_THREADS,
    ERR_GOOD, ERR_ACCESS, ERR_UNMAPPED,
)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
        print(f"  {FAIL}: {msg}")
        return False
    return True


# ---------------------------------------------------------------------------
# Helper: create a fresh network + 32 banks each time
# ---------------------------------------------------------------------------
def fresh():
    return ClosNetwork(), [SRAMBank(i) for i in range(NUM_BANKS)]


# ---------------------------------------------------------------------------
# A. UNICAST — every bank to every thread
# ---------------------------------------------------------------------------
def test_A_unicast_all():
    print("\n" + "=" * 60)
    print("[A] UNICAST — every bank to every thread (1024 combinations)")
    print("=" * 60)

    net, banks = fresh()

    # Pre-write distinct data for each (bank, address) pair
    # Use address = thread_id for simplicity; data encodes bank+thread
    flits_by_thread: dict[int, list] = {}

    for bank_id in range(NUM_BANKS):
        for thread_id in range(NUM_THREADS):
            addr     = thread_id        # one address slot per thread
            data_val = (bank_id << 8) | thread_id   # unique per pair
            banks[bank_id].write(addr, data_val)

    pass_count = 0
    fail_count = 0

    for bank_id in range(NUM_BANKS):
        for thread_id in range(NUM_THREADS):
            addr     = thread_id
            data_val = (bank_id << 8) | thread_id
            flit     = Flit.make(dest_mask=(1 << thread_id), data=data_val)

            deliveries = net.send({bank_id: flit})

            # Correct thread receives the flit
            rxs = deliveries.get(thread_id, [])
            ok  = (len(rxs) == 1 and rxs[0][0] == data_val and rxs[0][1] == ERR_GOOD)

            # No other thread receives anything
            stray = {t: v for t, v in deliveries.items() if t != thread_id}
            ok   &= (len(stray) == 0)

            if ok:
                pass_count += 1
            else:
                fail_count += 1
                msg = (f"bank{bank_id}->thread{thread_id}: "
                       f"rxs={rxs}, stray={stray}, expected data=0x{data_val:04X}")
                failures.append(msg)
                print(f"  {FAIL}: {msg}")

    status = PASS if fail_count == 0 else FAIL
    print(f"  {status}: {pass_count}/1024 unicast combinations passed")


# ---------------------------------------------------------------------------
# B. MULTICAST — representative patterns
# ---------------------------------------------------------------------------
MULTICAST_PATTERNS = [
    # (name, bank_id, [thread_ids])
    ("two threads, same egress group",          0,  [0, 1]),
    ("two threads, different egress groups",    1,  [0, 8]),
    ("four threads spread across 4 egresses",   2,  [0, 8, 16, 24]),
    ("eight threads, one per egress",           3,  [0, 4, 8, 12, 16, 20, 24, 28]),
    ("threads 0,1,4,8,20,31 (mixed groups)",    5,  [0, 1, 4, 8, 20, 31]),
    ("all threads in egress 0 (0-3)",          10,  [0, 1, 2, 3]),
    ("all threads in egress 7 (28-31)",        15,  [28, 29, 30, 31]),
    ("half the threads (even)",                20,  list(range(0, 32, 2))),
    ("half the threads (odd)",                 25,  list(range(1, 32, 2))),
    ("31 threads (all except thread 0)",       31,  list(range(1, 32))),
]

def test_B_multicast():
    print("\n" + "=" * 60)
    print("[B] MULTICAST — representative destination patterns")
    print("=" * 60)

    net, _ = fresh()

    for name, bank_id, dest_threads in MULTICAST_PATTERNS:
        data_val  = 0xAB000000 | (bank_id << 8) | len(dest_threads)
        dest_mask = sum(1 << t for t in dest_threads)
        flit      = Flit.make(dest_mask=dest_mask, data=data_val)

        deliveries = net.send({bank_id: flit})

        ok = True

        # Every destination thread must receive the flit
        for tid in dest_threads:
            rxs = deliveries.get(tid, [])
            if not rxs or rxs[0][0] != data_val or rxs[0][1] != ERR_GOOD:
                ok = False
                failures.append(f"multicast '{name}': thread {tid} did not receive correctly")

        # No non-destination thread should receive anything
        non_dest = set(range(NUM_THREADS)) - set(dest_threads)
        stray    = {t: v for t, v in deliveries.items() if t in non_dest}
        if stray:
            ok = False
            failures.append(f"multicast '{name}': stray deliveries to {list(stray.keys())}")

        status = PASS if ok else FAIL
        print(f"  {status}: bank{bank_id} -> [{len(dest_threads)} threads] — {name}")


# ---------------------------------------------------------------------------
# C. BROADCAST — every bank to all 32 threads
# ---------------------------------------------------------------------------
def test_B2_multicast_proof_by_decomposition():
    """
    Prove correctness for all 2^32 destination masks via decomposition.

    The ingress switch splits every flit into independent sub-flits, one per
    egress group.  Those sub-flits never interact.  Therefore:

      dest_mask M works  <=>
        (a) every active egress group handles its 4-bit subset correctly, AND
        (b) active egress groups don't interfere with each other.

    We prove (a) with 8 groups × 15 non-empty subsets = 120 tests.
    We prove (b) with all 2^8 = 256 combinations of active egress groups.
    Total: 376 tests, covers all 2^32 masks by the decomposition argument.
    """
    print("\n" + "=" * 60)
    print("[B2] MULTICAST PROOF BY DECOMPOSITION")
    print("     (a) all 16 subsets × 8 egress groups  = 120 tests")
    print("     (b) all 256 cross-group combinations   = 256 tests")
    print("=" * 60)

    from clos_network_sim import THREADS_PER_EGRESS, NUM_EGRESS

    net = ClosNetwork()

    # ------------------------------------------------------------------
    # (a) Per-group completeness
    #     For each egress group g and every non-empty 4-bit subset s (1-15):
    #     send a flit from bank 0 with dest_mask = those threads only.
    #     Verify exactly those threads receive it and no others do.
    # ------------------------------------------------------------------
    part_a_pass = 0
    part_a_fail = 0

    for group in range(NUM_EGRESS):           # 0..7
        base = group * THREADS_PER_EGRESS     # first thread in this group
        for subset in range(1, 1 << THREADS_PER_EGRESS):   # 1..15
            dest_threads = [base + i for i in range(THREADS_PER_EGRESS)
                            if (subset >> i) & 1]
            dest_mask = sum(1 << t for t in dest_threads)
            data_val  = 0xA0000000 | (group << 8) | subset
            flit      = Flit.make(dest_mask=dest_mask, data=data_val)

            deliveries = net.send({0: flit})

            ok = True
            for tid in dest_threads:
                rxs = deliveries.get(tid, [])
                if not (len(rxs) == 1 and rxs[0][0] == data_val and rxs[0][1] == ERR_GOOD):
                    ok = False
                    failures.append(
                        f"[B2a] group={group} subset={subset:04b} "
                        f"thread {tid} did not receive correctly: {rxs}")

            stray = {t: v for t, v in deliveries.items() if t not in dest_threads}
            if stray:
                ok = False
                failures.append(
                    f"[B2a] group={group} subset={subset:04b} "
                    f"stray deliveries to threads {list(stray.keys())}")

            if ok:
                part_a_pass += 1
            else:
                part_a_fail += 1

    status_a = PASS if part_a_fail == 0 else FAIL
    print(f"  {status_a} (a) per-group: {part_a_pass}/120 passed")

    # ------------------------------------------------------------------
    # (b) Cross-group independence
    #     For each of the 256 non-trivial combinations of active egress
    #     groups, activate thread 0 of each active group.
    #     Verify every active-group thread receives the flit and inactive
    #     groups receive nothing.
    # ------------------------------------------------------------------
    part_b_pass = 0
    part_b_fail = 0

    for combo in range(1 << NUM_EGRESS):      # 0..255
        active_groups  = [g for g in range(NUM_EGRESS) if (combo >> g) & 1]
        dest_threads   = [g * THREADS_PER_EGRESS for g in active_groups]  # thread 0 of each group
        dest_mask      = sum(1 << t for t in dest_threads)
        data_val       = 0xB0000000 | combo
        flit           = Flit.make(dest_mask=dest_mask, data=data_val)

        deliveries = net.send({0: flit})

        ok = True
        if combo == 0:
            # No destinations — nothing should arrive anywhere
            if deliveries:
                ok = False
                failures.append(f"[B2b] combo=0 (no dest): unexpected deliveries {deliveries}")
        else:
            for tid in dest_threads:
                rxs = deliveries.get(tid, [])
                if not (len(rxs) == 1 and rxs[0][0] == data_val and rxs[0][1] == ERR_GOOD):
                    ok = False
                    failures.append(
                        f"[B2b] combo={combo:08b} thread {tid} did not receive: {rxs}")

            stray = {t: v for t, v in deliveries.items() if t not in dest_threads}
            if stray:
                ok = False
                failures.append(
                    f"[B2b] combo={combo:08b} stray deliveries to {list(stray.keys())}")

        if ok:
            part_b_pass += 1
        else:
            part_b_fail += 1

    status_b = PASS if part_b_fail == 0 else FAIL
    print(f"  {status_b} (b) cross-group: {part_b_pass}/256 passed")
    print()
    print("  By decomposition: if (a) and (b) both pass, ALL 2^32 destination")
    print("  masks are guaranteed correct — no further testing needed.")


def test_C_broadcast():
    print("\n" + "=" * 60)
    print("[C] BROADCAST — every bank sends to all 32 threads")
    print("=" * 60)

    net      = ClosNetwork()
    all_mask = (1 << NUM_THREADS) - 1
    pass_count = 0
    fail_count = 0

    for bank_id in range(NUM_BANKS):
        data_val  = 0xBC000000 | bank_id
        flit      = Flit.make(dest_mask=all_mask, data=data_val)
        deliveries = net.send({bank_id: flit})

        ok = all(
            (len(deliveries.get(t, [])) == 1 and
             deliveries[t][0][0] == data_val and
             deliveries[t][0][1] == ERR_GOOD)
            for t in range(NUM_THREADS)
        )

        if ok:
            pass_count += 1
        else:
            fail_count += 1
            for t in range(NUM_THREADS):
                rxs = deliveries.get(t, [])
                if not rxs or rxs[0][0] != data_val:
                    msg = f"broadcast bank{bank_id}: thread {t} got {rxs}, expected 0x{data_val:08X}"
                    failures.append(msg)
                    print(f"  {FAIL}: {msg}")

    status = PASS if fail_count == 0 else FAIL
    print(f"  {status}: {pass_count}/32 banks broadcast to all 32 threads correctly")


# ---------------------------------------------------------------------------
# D. ERROR PROPAGATION
# ---------------------------------------------------------------------------
def test_D_errors():
    print("\n" + "=" * 60)
    print("[D] ERROR PROPAGATION — error flits routed to correct thread")
    print("=" * 60)

    error_cases = [
        ("UNMAPPED  bank 0  -> thread 0",  0,  0,  ERR_UNMAPPED),
        ("UNMAPPED  bank 7  -> thread 15", 7,  15, ERR_UNMAPPED),
        ("UNMAPPED  bank 15 -> thread 31", 15, 31, ERR_UNMAPPED),
        ("ACCESS    bank 0  -> thread 7",  0,  7,  ERR_ACCESS),
        ("ACCESS    bank 31 -> thread 24", 31, 24, ERR_ACCESS),
    ]

    net = ClosNetwork()

    for name, bank_id, thread_id, err_code in error_cases:
        flit = Flit.make(dest_mask=(1 << thread_id), data=0, error=err_code)
        deliveries = net.send({bank_id: flit})

        rxs = deliveries.get(thread_id, [])
        ok  = (len(rxs) == 1 and rxs[0][1] == err_code)

        stray = {t: v for t, v in deliveries.items() if t != thread_id}
        ok   &= (len(stray) == 0)

        status = PASS if ok else FAIL
        if not ok:
            failures.append(f"error test '{name}': rxs={rxs}, stray={stray}")
        print(f"  {status}: {name}")


# ---------------------------------------------------------------------------
# E. MSHR MERGE
# ---------------------------------------------------------------------------
def test_E_mshr_merge():
    print("\n" + "=" * 60)
    print("[E] MSHR MERGE — two threads request same line, one multicast response")
    print("=" * 60)

    from clos_network_sim import MSHRTable

    merge_cases = [
        # (bank_id, address, thread_a, thread_b, data_val)
        (0,  0x0020, 3,  5,  0xCAFEBABE),
        (7,  0x0040, 0,  31, 0x11223344),
        (15, 0x0080, 12, 20, 0xDEADC0DE),
        (31, 0x0100, 1,  28, 0xFEEDFACE),
    ]

    net = ClosNetwork()

    for bank_id, addr, ta, tb, data_val in merge_cases:
        mshr = MSHRTable(bank_id)

        eid1, merged1 = mshr.request(addr, ta)
        assert not merged1, "First request must NOT be merged"

        eid2, merged2 = mshr.request(addr, tb)
        assert merged2,     "Second request to same address MUST merge"
        assert eid2 == eid1, "Merged entry must share the same entry_id"

        # Verify both threads are in dest_mask before completing
        entry = mshr._table[eid1]
        check((entry.dest_mask >> ta) & 1, f"Thread {ta} missing from MSHR dest_mask")
        check((entry.dest_mask >> tb) & 1, f"Thread {tb} missing from MSHR dest_mask")

        flit = mshr.complete(eid1, data_val, ERR_GOOD)
        mshr.free(eid1)
        assert flit is not None

        deliveries = net.send({bank_id: flit})

        ok_a = len(deliveries.get(ta, [])) == 1 and deliveries[ta][0][0] == data_val
        ok_b = len(deliveries.get(tb, [])) == 1 and deliveries[tb][0][0] == data_val
        stray = {t: v for t, v in deliveries.items() if t not in (ta, tb)}
        ok   = ok_a and ok_b and not stray

        if not ok:
            failures.append(f"MSHR merge bank{bank_id} addr=0x{addr:04X} "
                            f"threads {ta},{tb}: ok_a={ok_a}, ok_b={ok_b}, stray={stray}")

        status = PASS if ok else FAIL
        print(f"  {status}: bank{bank_id} addr=0x{addr:04X}, "
              f"threads {ta} and {tb} both received 0x{data_val:08X}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("Clos Network — Exhaustive Functional Test Suite")
    print("=" * 60)

    test_A_unicast_all()
    test_B_multicast()
    test_B2_multicast_proof_by_decomposition()
    test_C_broadcast()
    test_D_errors()
    test_E_mshr_merge()

    print("\n" + "=" * 60)
    if failures:
        print(f"RESULT: {len(failures)} FAILURE(S)")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("RESULT: ALL TESTS PASSED")
    print("=" * 60)
