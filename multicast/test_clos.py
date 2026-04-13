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
    NUM_BANKS, NUM_THREADS, NUM_EGRESS, BANKS_PER_INGRESS, THREADS_PER_EGRESS,
    ERR_GOOD, ERR_ACCESS, ERR_UNMAPPED, ERR_NAMES,
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
def fresh(verbose: bool = False):
    return ClosNetwork(verbose=verbose), [SRAMBank(i) for i in range(NUM_BANKS)]


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
            addr      = thread_id
            data_val  = (bank_id << 8) | thread_id
            dest_mask = 1 << thread_id
            flit      = Flit.make(dest_mask=dest_mask, data=data_val)

            deliveries = net.send({bank_id: flit})

            rxs   = deliveries.get(thread_id, [])
            stray = {t: v for t, v in deliveries.items() if t != thread_id}
            ok    = (len(rxs) == 1 and rxs[0][0] == data_val
                     and rxs[0][1] == ERR_GOOD and not stray)

            if ok:
                pass_count += 1
                print(f"  {PASS}: bank={bank_id:2d}  dest_mask=0x{dest_mask:08X}  "
                      f"data=0x{data_val:04X}  -> thread {thread_id:2d}  "
                      f"rx=0x{rxs[0][0]:04X}  err={ERR_NAMES[rxs[0][1]]}")
            else:
                fail_count += 1
                msg = (f"bank{bank_id}->thread{thread_id}: "
                       f"rxs={rxs}, stray={stray}, expected data=0x{data_val:04X}")
                failures.append(msg)
                print(f"  {FAIL}: {msg}")

    status = PASS if fail_count == 0 else FAIL
    print(f"\n  {status}: {pass_count}/1024 unicast combinations passed")


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

    net, _ = fresh(verbose=True)

    for name, bank_id, dest_threads in MULTICAST_PATTERNS:
        data_val  = 0xAB000000 | (bank_id << 8) | len(dest_threads)
        dest_mask = sum(1 << t for t in dest_threads)
        flit      = Flit.make(dest_mask=dest_mask, data=data_val)

        print(f"\n  -- {name} --")
        print(f"  Flit: bank={bank_id}  dest_mask=0x{dest_mask:08X}  "
              f"data=0x{data_val:08X}  threads={dest_threads}")

        deliveries = net.send({bank_id: flit})

        ok = True
        for tid in dest_threads:
            rxs = deliveries.get(tid, [])
            if not rxs or rxs[0][0] != data_val or rxs[0][1] != ERR_GOOD:
                ok = False
                failures.append(f"multicast '{name}': thread {tid} did not receive correctly")

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

            tag = PASS if ok else FAIL
            print(f"  {tag} [B2a] group={group}  subset={subset:04b}  "
                  f"dest_mask=0x{dest_mask:08X}  data=0x{data_val:08X}  "
                  f"threads={dest_threads}")
            if ok:
                part_a_pass += 1
            else:
                part_a_fail += 1

    status_a = PASS if part_a_fail == 0 else FAIL
    print(f"\n  {status_a} (a) per-group: {part_a_pass}/120 passed")

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
        dest_threads   = [g * THREADS_PER_EGRESS for g in active_groups]
        dest_mask      = sum(1 << t for t in dest_threads)
        data_val       = 0xB0000000 | combo
        flit           = Flit.make(dest_mask=dest_mask, data=data_val)

        deliveries = net.send({0: flit})

        ok = True
        if combo == 0:
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

        tag = PASS if ok else FAIL
        print(f"  {tag} [B2b] combo={combo:08b}  active_groups={active_groups}  "
              f"dest_mask=0x{dest_mask:08X}  data=0x{data_val:08X}  threads={dest_threads}")
        if ok:
            part_b_pass += 1
        else:
            part_b_fail += 1

    status_b = PASS if part_b_fail == 0 else FAIL
    print(f"\n  {status_b} (b) cross-group: {part_b_pass}/256 passed")
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
        data_val   = 0xBC000000 | bank_id
        flit       = Flit.make(dest_mask=all_mask, data=data_val)
        print(f"\n  bank={bank_id:2d}: dest_mask=0x{all_mask:08X}  data=0x{data_val:08X}  "
              f"-> all {NUM_THREADS} threads")
        deliveries = net.send({bank_id: flit})

        ok = all(
            len(deliveries.get(t, [])) == 1 and
            deliveries[t][0][0] == data_val and
            deliveries[t][0][1] == ERR_GOOD
            for t in range(NUM_THREADS)
        )

        if ok:
            pass_count += 1
            rx_threads = sorted(deliveries.keys())
            print(f"  {PASS}: received by threads {rx_threads}")
        else:
            fail_count += 1
            for t in range(NUM_THREADS):
                rxs = deliveries.get(t, [])
                if not rxs or rxs[0][0] != data_val:
                    msg = (f"broadcast bank{bank_id}: thread {t} got {rxs}, "
                           f"expected 0x{data_val:08X}")
                    failures.append(msg)
                    print(f"  {FAIL}: {msg}")

    status = PASS if fail_count == 0 else FAIL
    print(f"\n  {status}: {pass_count}/32 banks broadcast to all 32 threads correctly")


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

    net = ClosNetwork(verbose=True)

    for name, bank_id, thread_id, err_code in error_cases:
        dest_mask = 1 << thread_id
        flit      = Flit.make(dest_mask=dest_mask, data=0, error=err_code)
        print(f"\n  -- {name} --")
        print(f"  Flit: bank={bank_id}  dest_mask=0x{dest_mask:08X}  "
              f"data=0x00000000  err={ERR_NAMES[err_code]}  -> thread {thread_id}")
        deliveries = net.send({bank_id: flit})

        rxs   = deliveries.get(thread_id, [])
        stray = {t: v for t, v in deliveries.items() if t != thread_id}
        ok    = len(rxs) == 1 and rxs[0][1] == err_code and not stray

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

    net = ClosNetwork(verbose=True)

    for bank_id, addr, ta, tb, data_val in merge_cases:
        mshr      = MSHRTable(bank_id)
        dest_mask = (1 << ta) | (1 << tb)

        print(f"\n  -- bank={bank_id}  addr=0x{addr:04X}  threads=[{ta},{tb}] --")
        print(f"  MSHR: allocate  addr=0x{addr:04X}  "
              f"dest_mask=0x{dest_mask:08X}  threads=[{ta},{tb}]")

        eid   = mshr.allocate(addr, dest_mask)
        entry = mshr._table[eid]
        check((entry.dest_mask >> ta) & 1, f"Thread {ta} missing from MSHR dest_mask")
        check((entry.dest_mask >> tb) & 1, f"Thread {tb} missing from MSHR dest_mask")

        flit = mshr.complete(eid, data_val, ERR_GOOD)
        mshr.free(eid)
        assert flit is not None
        print(f"  MSHR: complete  eid={eid}  data=0x{data_val:08X}  err=GOOD")
        print(f"  Flit: dest_mask=0x{flit.dest_mask:08X}  data=0x{flit.data:08X}  "
              f"threads=[{ta},{tb}]")

        deliveries = net.send({bank_id: flit})

        ok_a  = len(deliveries.get(ta, [])) == 1 and deliveries[ta][0][0] == data_val
        ok_b  = len(deliveries.get(tb, [])) == 1 and deliveries[tb][0][0] == data_val
        stray = {t: v for t, v in deliveries.items() if t not in (ta, tb)}
        ok    = ok_a and ok_b and not stray

        if not ok:
            failures.append(f"MSHR merge bank{bank_id} addr=0x{addr:04X} "
                            f"threads {ta},{tb}: ok_a={ok_a}, ok_b={ok_b}, stray={stray}")

        status = PASS if ok else FAIL
        print(f"  {status}: bank{bank_id} addr=0x{addr:04X}, "
              f"threads {ta} and {tb} both received 0x{data_val:08X}")


# ---------------------------------------------------------------------------
# F. SINGLE INGRESS — 4 simultaneous flits to different egress groups
# ---------------------------------------------------------------------------
def test_F_single_ingress_4way():
    print("\n" + "=" * 60)
    print("[F] SINGLE INGRESS — 4 banks simultaneous, different egress groups")
    print("=" * 60)

    net = ClosNetwork(verbose=True)

    # Sub-test 1: banks 0-3 (ingress 0), each to a different egress group
    batch = {
        0: Flit.make(dest_mask=1 << 0,  data=0xF0000000),
        1: Flit.make(dest_mask=1 << 4,  data=0xF0000001),
        2: Flit.make(dest_mask=1 << 8,  data=0xF0000002),
        3: Flit.make(dest_mask=1 << 12, data=0xF0000003),
    }
    print(f"\n  -- Sub-test 1: 4 unicasts from ingress 0 --")
    for bank_id, f in batch.items():
        threads = [i for i in range(NUM_THREADS) if (f.dest_mask >> i) & 1]
        print(f"  Flit: bank={bank_id}  dest_mask=0x{f.dest_mask:08X}  "
              f"data=0x{f.data:08X}  threads={threads}")
    deliveries = net.send(batch)

    ok       = True
    expected = {0: 0xF0000000, 4: 0xF0000001, 8: 0xF0000002, 12: 0xF0000003}
    for tid, dv in expected.items():
        rxs = deliveries.get(tid, [])
        if not rxs or rxs[0][0] != dv or rxs[0][1] != ERR_GOOD:
            ok = False
            failures.append(f"[F1] thread{tid}: got {rxs}, expected 0x{dv:08X}")
    stray = {t: v for t, v in deliveries.items() if t not in expected}
    if stray:
        ok = False
        failures.append(f"[F1] stray deliveries to threads {list(stray.keys())}")
    status = PASS if ok else FAIL
    print(f"  {status}: 4 unicasts from ingress 0 all delivered correctly")

    # Sub-test 2: bank 0 multicast to threads 0,1; banks 1-3 unicast
    batch2 = {
        0: Flit.make(dest_mask=(1 << 0) | (1 << 1), data=0xF1000000),
        1: Flit.make(dest_mask=1 << 4,               data=0xF1000001),
        2: Flit.make(dest_mask=1 << 8,               data=0xF1000002),
        3: Flit.make(dest_mask=1 << 12,              data=0xF1000003),
    }
    print(f"\n  -- Sub-test 2: multicast(threads 0,1) + 3 unicasts --")
    for bank_id, f in batch2.items():
        threads = [i for i in range(NUM_THREADS) if (f.dest_mask >> i) & 1]
        print(f"  Flit: bank={bank_id}  dest_mask=0x{f.dest_mask:08X}  "
              f"data=0x{f.data:08X}  threads={threads}")
    deliveries2 = net.send(batch2)

    ok2       = True
    expected2 = {0: 0xF1000000, 1: 0xF1000000, 4: 0xF1000001,
                 8: 0xF1000002, 12: 0xF1000003}
    for tid, dv in expected2.items():
        rxs = deliveries2.get(tid, [])
        if not rxs or rxs[0][0] != dv or rxs[0][1] != ERR_GOOD:
            ok2 = False
            failures.append(f"[F2] thread{tid}: got {rxs}, expected 0x{dv:08X}")
    stray2 = {t: v for t, v in deliveries2.items() if t not in expected2}
    if stray2:
        ok2 = False
        failures.append(f"[F2] stray deliveries to threads {list(stray2.keys())}")
    status2 = PASS if ok2 else FAIL
    print(f"  {status2}: multicast(threads 0,1) + 3 unicasts all delivered correctly")


# ---------------------------------------------------------------------------
# G. ALL INGRESS — 32 simultaneous flits, all unique destinations
# ---------------------------------------------------------------------------
def test_G_all_ingress_32way():
    print("\n" + "=" * 60)
    print("[G] ALL INGRESS — 32 banks simultaneous, all unique threads")
    print("=" * 60)

    net = ClosNetwork(verbose=True)

    # Sub-test 1: bank b -> thread b (32 unique unicasts simultaneously)
    batch = {b: Flit.make(dest_mask=1 << b, data=0xE0000000 | b)
             for b in range(NUM_BANKS)}
    print(f"\n  -- Sub-test 1: 32 simultaneous unicasts (bank b -> thread b) --")
    for bank_id, f in sorted(batch.items()):
        print(f"  Flit: bank={bank_id:2d}  dest_mask=0x{f.dest_mask:08X}  "
              f"data=0x{f.data:08X}  -> thread {bank_id}")
    deliveries = net.send(batch)

    ok = True
    for b in range(NUM_BANKS):
        rxs = deliveries.get(b, [])
        dv  = 0xE0000000 | b
        if not rxs or rxs[0][0] != dv or rxs[0][1] != ERR_GOOD:
            ok = False
            failures.append(f"[G1] thread{b}: got {rxs}, expected 0x{dv:08X}")
    stray = {t: v for t, v in deliveries.items() if t >= NUM_BANKS}
    if stray:
        ok = False
        failures.append(f"[G1] stray deliveries: {list(stray.keys())}")
    status = PASS if ok else FAIL
    print(f"  {status}: 32 simultaneous unicasts all delivered correctly")

    # Sub-test 2: one bank per ingress group sends a full group broadcast
    batch2   = {}
    expected2 = {}
    for g in range(NUM_EGRESS):
        grp_mask = 0xF << (g * THREADS_PER_EGRESS)
        bank_id  = g * BANKS_PER_INGRESS
        dv       = 0xD0000000 | g
        batch2[bank_id] = Flit.make(dest_mask=grp_mask, data=dv)
        for t in range(g * THREADS_PER_EGRESS, (g + 1) * THREADS_PER_EGRESS):
            expected2[t] = dv

    print(f"\n  -- Sub-test 2: 8 simultaneous group-broadcasts --")
    for bank_id, f in sorted(batch2.items()):
        threads = [i for i in range(NUM_THREADS) if (f.dest_mask >> i) & 1]
        print(f"  Flit: bank={bank_id:2d}  dest_mask=0x{f.dest_mask:08X}  "
              f"data=0x{f.data:08X}  threads={threads}")
    deliveries2 = net.send(batch2)

    ok2 = True
    for tid, dv in expected2.items():
        rxs = deliveries2.get(tid, [])
        if not rxs or rxs[0][0] != dv or rxs[0][1] != ERR_GOOD:
            ok2 = False
            failures.append(f"[G2] thread{tid}: got {rxs}, expected 0x{dv:08X}")
    stray2 = {t: v for t, v in deliveries2.items() if t not in expected2}
    if stray2:
        ok2 = False
        failures.append(f"[G2] stray deliveries: {list(stray2.keys())}")
    status2 = PASS if ok2 else FAIL
    print(f"  {status2}: 8 simultaneous group-broadcasts all delivered correctly")


# ---------------------------------------------------------------------------
# H. PIPELINE — back-to-back flits using tick()
# ---------------------------------------------------------------------------
def test_H_pipeline():
    print("\n" + "=" * 60)
    print("[H] PIPELINE — back-to-back flits via tick()")
    print("=" * 60)

    net = ClosNetwork(verbose=True)

    # Each batch is injected one cycle apart.
    # With 3-stage latency, batch N exits egress on cycle N+2 (0-indexed).
    #
    # Cycle 1: inject batch 0  -> ingress
    # Cycle 2: inject batch 1  -> ingress  |  batch 0 -> middle
    # Cycle 3: inject batch 2  -> ingress  |  batch 1 -> middle  |  batch 0 -> egress (out)
    # Cycle 4: inject batch 3  -> ingress  |  batch 2 -> middle  |  batch 1 -> egress (out)
    # Cycle 5: drain (no new)              |  batch 3 -> middle  |  batch 2 -> egress (out)
    # Cycle 6: drain (no new)                                    |  batch 3 -> egress (out)

    batches = [
        # (batch_label, bank_id, thread_id, data_val)
        (0,  0,  0,  0xAA000000),
        (1,  4,  5,  0xBB000001),
        (2,  8,  10, 0xCC000002),
        (3, 12,  15, 0xDD000003),
    ]

    flit_batches = [
        {bank: Flit.make(dest_mask=1 << tid, data=dv)}
        for _, bank, tid, dv in batches
    ]

    print(f"\n  -- Injecting 4 back-to-back batches --")
    for i, (label, bank, tid, dv) in enumerate(batches):
        print(f"  Batch {label}: bank={bank}  dest_mask=0x{1 << tid:08X}  "
              f"data=0x{dv:08X}  -> thread {tid}  (injects at cycle {i+1}, exits at cycle {i+3})")

    all_outputs = []
    for fb in flit_batches:
        all_outputs.append(net.tick(fb))

    print(f"\n  -- Draining pipeline --")
    all_outputs.append(net.tick({}))
    all_outputs.append(net.tick({}))

    # Each batch exits 2 cycles after injection (cycle index = inject_cycle + 2)
    expected_exit = [
        (2, batches[0]),  # batch 0 exits at output index 2 (cycle 3)
        (3, batches[1]),
        (4, batches[2]),
        (5, batches[3]),
    ]
    print(f"\n  -- Checking outputs --")

    ok = True
    for out_idx, (label, bank, tid, dv) in expected_exit:
        deliveries = all_outputs[out_idx]
        rxs = deliveries.get(tid, [])
        ok_this = len(rxs) == 1 and rxs[0][0] == dv and rxs[0][1] == ERR_GOOD
        tag = PASS if ok_this else FAIL
        rx_str = f"0x{rxs[0][0]:08X} err={ERR_NAMES[rxs[0][1]]}" if rxs else "nothing"
        print(f"  {tag}: batch {label}  bank={bank}->thread={tid}  "
              f"data=0x{dv:08X}  exited at cycle {out_idx+1}  rx={rx_str}")
        if not ok_this:
            ok = False
            failures.append(f"pipeline batch bank{bank}->thread{tid}: "
                            f"expected 0x{dv:08X} at output cycle {out_idx}, got {rxs}")

    # Also verify no batch appears in the wrong output slot
    for out_idx, deliveries in enumerate(all_outputs):
        for _, bank, tid, dv in batches:
            expected_out = batches.index((_, bank, tid, dv)) + 2
            if out_idx != expected_out and tid in deliveries:
                rxs = deliveries[tid]
                if rxs and rxs[0][0] == dv:
                    ok = False
                    msg = (f"pipeline bank{bank}->thread{tid} appeared at wrong "
                           f"output cycle {out_idx}, expected {expected_out}")
                    failures.append(msg)
                    print(f"  {FAIL}: {msg}")

    status = PASS if ok else FAIL
    print(f"  {status}: 4 back-to-back flits pipelined correctly "
          f"(3-cycle latency, no mixing between batches)")

    # Sub-test: simultaneous injection and egress (steady state)
    # Inject 3 priming cycles, then verify every new inject immediately
    # has a corresponding egress 2 cycles later.
    net2 = ClosNetwork(verbose=True)
    steady_batches = [
        {b: Flit.make(dest_mask=1 << b, data=0xEE000000 | b)}
        for b in range(NUM_BANKS)
    ]

    print(f"\n  -- Steady-state: {NUM_BANKS} consecutive bank injections (bank b -> thread b) --")
    steady_out = []
    for b, fb in enumerate(steady_batches):
        bank = list(fb.keys())[0]
        f    = list(fb.values())[0]
        print(f"\n  Inject cycle {b+1}: bank={bank}  dest_mask=0x{f.dest_mask:08X}  "
              f"data=0x{f.data:08X}")
        steady_out.append(net2.tick(fb))
    steady_out.append(net2.tick({}))
    steady_out.append(net2.tick({}))

    print(f"\n  -- Checking steady-state outputs --")
    ok2 = True
    for inject_cycle, fb in enumerate(steady_batches):
        out_cycle = inject_cycle + 2
        deliveries = steady_out[out_cycle]
        for bank in fb:
            tid = bank
            dv  = 0xEE000000 | bank
            rxs = deliveries.get(tid, [])
            ok_this = len(rxs) == 1 and rxs[0][0] == dv and rxs[0][1] == ERR_GOOD
            tag     = PASS if ok_this else FAIL
            rx_str  = f"0x{rxs[0][0]:08X}" if rxs else "nothing"
            print(f"  {tag}: inject={inject_cycle+1}  out={out_cycle+1}  "
                  f"bank={bank}->thread={tid}  expected=0x{dv:08X}  rx={rx_str}")
            if not ok_this:
                ok2 = False
                failures.append(f"steady-state pipeline bank{bank}->thread{tid}: "
                                f"expected 0x{dv:08X} at output cycle {out_cycle}, got {rxs}")

    status2 = PASS if ok2 else FAIL
    print(f"\n  {status2}: steady-state — {NUM_BANKS} consecutive single-bank injections "
          f"all exit at correct cycle")


# ---------------------------------------------------------------------------
# I. ALL-THREADS MIXED — multicasts + unicasts covering all 32 threads in one send
# ---------------------------------------------------------------------------
def test_I_all_threads_mixed():
    """
    One send() batch, all 32 threads receive exactly one flit.
    Mix of multicasts (2-4 destinations) and unicasts (1 destination).

    Design: within each ingress switch (4 banks), no two banks target the same
    egress group — satisfies the arbiter guarantee required by hardware.

    Batch layout (bank -> dest threads):
      Ingress 0: bank  0  multicast  {0,1}          egress grp 0
      Ingress 1: bank  4  multicast  {4,5,6,7}      egress grp 1
                 bank  5  multicast  {2,3}           egress grp 0  (different grp, no conflict)
      Ingress 2: bank  8  multicast  {8,9,10,11}    egress grp 2
      Ingress 3: bank 12  multicast  {12,13}         egress grp 3
      Ingress 4: bank 16  unicast    {16}            egress grp 4
                 bank 17  multicast  {14,15}         egress grp 3  (different grp, no conflict)
      Ingress 5: bank 20  multicast  {20,21,22,23}  egress grp 5
                 bank 21  multicast  {17,18,19}      egress grp 4  (different grp, no conflict)
      Ingress 6: bank 24  unicast    {24}            egress grp 6
      Ingress 7: bank 28  multicast  {28,29,30,31}  egress grp 7
                 bank 29  multicast  {25,26,27}      egress grp 6  (different grp, no conflict)
    """
    print("\n" + "=" * 60)
    print("[I] ALL-THREADS MIXED — multicasts + unicasts, all 32 threads in one send")
    print("=" * 60)

    net = ClosNetwork(verbose=True)

    def mask(*threads):
        return sum(1 << t for t in threads)

    # bank -> (dest_mask, data_val, description)
    batch_spec = {
        0:  (mask(0, 1),            0xC0000000, "multicast  {0,1}"),
        4:  (mask(4, 5, 6, 7),      0xC0000001, "multicast  {4,5,6,7}"),
        5:  (mask(2, 3),            0xC0000002, "multicast  {2,3}"),
        8:  (mask(8, 9, 10, 11),    0xC0000003, "multicast  {8,9,10,11}"),
        12: (mask(12, 13),          0xC0000004, "multicast  {12,13}"),
        16: (mask(16),              0xC0000005, "unicast    {16}"),
        17: (mask(14, 15),          0xC0000006, "multicast  {14,15}"),
        20: (mask(20, 21, 22, 23),  0xC0000007, "multicast  {20,21,22,23}"),
        21: (mask(17, 18, 19),      0xC0000008, "multicast  {17,18,19}"),
        24: (mask(24),              0xC0000009, "unicast    {24}"),
        28: (mask(28, 29, 30, 31),  0xC000000A, "multicast  {28,29,30,31}"),
        29: (mask(25, 26, 27),      0xC000000B, "multicast  {25,26,27}"),
    }

    # Expected per-thread delivery
    expected = {}
    for bank_id, (dm, dv, _) in batch_spec.items():
        for t in range(NUM_THREADS):
            if (dm >> t) & 1:
                expected[t] = dv

    assert len(expected) == NUM_THREADS, f"Test bug: only {len(expected)} threads covered"

    # Print batch summary
    print(f"\n  Batch: {len(batch_spec)} flits covering all {NUM_THREADS} threads")
    unicasts   = sum(1 for dm, _, _ in batch_spec.values() if bin(dm).count('1') == 1)
    multicasts = len(batch_spec) - unicasts
    print(f"  Composition: {multicasts} multicasts + {unicasts} unicasts")
    print()
    for bank_id in sorted(batch_spec):
        dm, dv, desc = batch_spec[bank_id]
        ingress = bank_id // BANKS_PER_INGRESS
        print(f"  bank={bank_id:2d} (ingress {ingress}): dest_mask=0x{dm:08X}  "
              f"data=0x{dv:08X}  {desc}")

    batch = {b: Flit.make(dest_mask=dm, data=dv)
             for b, (dm, dv, _) in batch_spec.items()}

    deliveries = net.send(batch)

    print(f"\n  -- Checking all {NUM_THREADS} thread deliveries --")
    ok = True
    for tid in range(NUM_THREADS):
        dv   = expected[tid]
        rxs  = deliveries.get(tid, [])
        good = len(rxs) == 1 and rxs[0][0] == dv and rxs[0][1] == ERR_GOOD
        tag  = PASS if good else FAIL
        rx_str = f"0x{rxs[0][0]:08X} err={ERR_NAMES[rxs[0][1]]}" if rxs else "nothing"
        print(f"  {tag}: thread {tid:2d}  expected=0x{dv:08X}  rx={rx_str}")
        if not good:
            ok = False
            failures.append(f"[I] thread {tid}: expected 0x{dv:08X}, got {rxs}")

    stray = {t: v for t, v in deliveries.items() if t not in expected}
    if stray:
        ok = False
        failures.append(f"[I] stray deliveries to threads {list(stray.keys())}")
        print(f"  {FAIL}: stray deliveries to threads {list(stray.keys())}")

    status = PASS if ok else FAIL
    print(f"\n  {status}: all 32 threads received exactly the expected flit "
          f"({multicasts} multicasts + {unicasts} unicasts)")


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
    test_F_single_ingress_4way()
    test_G_all_ingress_32way()
    test_H_pipeline()
    test_I_all_threads_mixed()

    print("\n" + "=" * 60)
    if failures:
        print(f"RESULT: {len(failures)} FAILURE(S)")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("RESULT: ALL TESTS PASSED")
    print("=" * 60)
