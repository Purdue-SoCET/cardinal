"""
test_stretch_clos_network.py
=============================================================
Stretch tests: flits that span many / all egress groups.

Run:
    python test_stretch_clos_network.py

Test groups
-----------
1. MAX-DISTANCE 2-POINT      bank b -> {thread b, thread (b+16)%32}        32 tests
2. ALL-EGRESS 1-THREAD       4^8 = 65,536 combos: one thread per egress   65536 tests
3. FULL-GROUP BROADCAST      bank b -> all 4 threads of egress group E      32×8 = 256 tests
4. N-EGRESS ACTIVE SWEEP     all C(8,N) for N=1..8                         255 tests
5. ROTATING DIAGONAL         bank b -> {(b+k*4)%32 for k=0..7}             32 tests
6. SIMULTANEOUS CROSS-INGRESS 8 banks fire at once, rotated destinations   8 tests
7. PIPELINE STRETCH          8 back-to-back all-egress spanning flits      8 flits

Verbose trace is shown for one representative case inside each group.
Performance metrics (elapsed, throughput) are printed at the end of each group.
=============================================================
"""

from __future__ import annotations

import sys
import time
from itertools import combinations, product
from math import comb as math_comb

from clos_network_sim import (
    ClosNetwork, Flit,
    NUM_BANKS, NUM_THREADS, NUM_EGRESS, NUM_INGRESS,
    BANKS_PER_INGRESS, THREADS_PER_EGRESS,
    ERR_GOOD, ERR_NAMES,
)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
failures: list[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def egr_grp(tid: int) -> int:
    """Egress group for thread tid (= tid // THREADS_PER_EGRESS)."""
    return tid >> 2

def mk(*threads: int) -> int:
    """Build dest_mask from thread ids."""
    return sum(1 << t for t in threads)

def active_threads(mask: int) -> list[int]:
    return [i for i in range(NUM_THREADS) if (mask >> i) & 1]

def section(title: str) -> float:
    print(f"\n{'=' * 64}")
    print(f"  {title}")
    print(f"{'=' * 64}")
    return time.perf_counter()

def perf(t0: float, n_tests: int, n_inject: int, n_deliver: int) -> None:
    elapsed = time.perf_counter() - t0
    rate    = n_inject / elapsed if elapsed > 0 else 0.0
    print(f"\n  Elapsed   : {elapsed * 1000:.1f} ms")
    print(f"  Tests     : {n_tests:,}")
    print(f"  Injected  : {n_inject:,} flits")
    print(f"  Delivered : {n_deliver:,} thread-deliveries")
    print(f"  Throughput: {rate:,.0f} flits/sec")

def send_check(net: ClosNetwork, batch: dict, expected: dict, tag: str) -> tuple[int, bool]:
    """
    Send batch, verify all expected thread deliveries, return (delivery_count, ok).
    """
    deliveries = net.send(batch)
    total = sum(len(v) for v in deliveries.values())
    ok    = True

    for tid, dv in expected.items():
        rxs = deliveries.get(tid, [])
        if not (len(rxs) == 1 and rxs[0][0] == dv and rxs[0][1] == ERR_GOOD):
            ok = False
            failures.append(f"{tag}: thread {tid} expected 0x{dv:08X}, got {rxs}")

    stray = {t for t in deliveries if t not in expected}
    if stray:
        ok = False
        failures.append(f"{tag}: stray deliveries to threads {sorted(stray)}")

    return total, ok


# ---------------------------------------------------------------------------
# 1. MAX-DISTANCE 2-POINT MULTICAST
#    bank b -> {thread b, thread (b+16)%32}
#    The two destinations are always in different egress groups (offset 16 > 4).
# ---------------------------------------------------------------------------
def test_max_distance_pairs() -> None:
    """
    32 tests.  bank b sends a 2-point multicast to thread b and thread (b+16)%32.

    Example stretch: bank 1 -> threads [1, 17]
      thread  1 lives in egress group 0  (threads  0-3)
      thread 17 lives in egress group 4  (threads 16-19)
      -> flit traverses ingress 0, travels via two different middle switches,
        arrives at two different egress switches.
    """
    t0    = section("1. MAX-DISTANCE 2-POINT MULTICAST  (bank b -> threads b, (b+16)%32)")
    net_t = ClosNetwork(verbose=True)
    net   = ClosNetwork(verbose=False)
    n_ok  = n_inj = n_del = 0

    for b in range(NUM_BANKS):
        ta   = b
        tb   = (b + 16) % NUM_THREADS
        dm   = mk(ta, tb)
        dv   = 0xA1000000 | (b << 8)
        flit = Flit.make(dest_mask=dm, data=dv)
        exp  = {ta: dv, tb: dv}

        if b == 1:
            print(f"\n  [TRACE] bank={b}  dest_mask=0x{dm:08X}  data=0x{dv:08X}")
            print(f"    thread {ta} -> egress group {egr_grp(ta)}")
            print(f"    thread {tb} -> egress group {egr_grp(tb)}")
            print(f"    stretch: {abs(egr_grp(ta) - egr_grp(tb))} egress groups apart")
            d, ok = send_check(net_t, {b: flit}, exp, f"MaxDist-b{b}")
        else:
            d, ok = send_check(net, {b: flit}, exp, f"MaxDist-b{b}")

        n_inj += 1
        n_del += d
        if ok:
            n_ok += 1
        tag = PASS if ok else FAIL
        print(f"  {tag}: bank={b:2d} -> threads=[{ta:2d},{tb:2d}]  "
              f"egr_grps=[{egr_grp(ta)},{egr_grp(tb)}]  data=0x{dv:08X}")

    status = PASS if n_ok == NUM_BANKS else FAIL
    print(f"\n  {status}: {n_ok}/{NUM_BANKS} max-distance pairs passed")
    perf(t0, NUM_BANKS, n_inj, n_del)


# ---------------------------------------------------------------------------
# 2. ALL-EGRESS 1-THREAD EXHAUSTIVE  (4^8 = 65,536 combos)
#    For every way to pick exactly one thread from each of the 8 egress groups,
#    bank 0 sends a single spanning flit.
# ---------------------------------------------------------------------------
def test_all_egress_one_thread_exhaustive() -> None:
    """
    65,536 tests.  bank 0 sends to exactly one thread per egress group —
    all possible selections.  Proves any 8-way spanning multicast works
    regardless of which specific thread is chosen within each egress group.

    NOTE: this test takes ~20-40 seconds; throughput numbers are meaningful.

    Trace shown for the diagonal case: threads [0, 5, 10, 15, 16, 21, 26, 31]
    (offset 0,1,2,3,0,1,2,3 within each group).
    """
    t0     = section("2. ALL-EGRESS 1-THREAD EXHAUSTIVE  (4^8 = 65,536 combos, bank 0)")
    net    = ClosNetwork(verbose=False)
    net_t  = ClosNetwork(verbose=True)
    n_ok   = n_fail = n_del = 0
    TOTAL  = THREADS_PER_EGRESS ** NUM_EGRESS   # 65536
    DATA   = 0xA2000000
    TRACE  = (0, 1, 2, 3, 0, 1, 2, 3)          # diagonal offset pattern

    for combo in product(range(THREADS_PER_EGRESS), repeat=NUM_EGRESS):
        threads = [g * THREADS_PER_EGRESS + combo[g] for g in range(NUM_EGRESS)]
        dm      = mk(*threads)
        dv      = DATA | sum(combo[g] << (g * 2) for g in range(NUM_EGRESS))
        exp     = {t: dv for t in threads}
        flit    = Flit.make(dest_mask=dm, data=dv)

        if combo == TRACE:
            print(f"\n  [TRACE] combo={combo}  threads={threads}")
            print(f"    dest_mask=0x{dm:08X}  data=0x{dv:08X}")
            for g, t in enumerate(threads):
                print(f"    egress {g}: thread {t}")
            d, ok = send_check(net_t, {0: flit}, exp, f"AllEgr1-{combo}")
        else:
            d, ok = send_check(net, {0: flit}, exp, f"AllEgr1-{combo}")

        n_del += d
        if ok:
            n_ok += 1
        else:
            n_fail += 1
            if n_fail <= 5:
                print(f"  {FAIL}: combo={combo} threads={threads}")

    status = PASS if n_fail == 0 else FAIL
    print(f"\n  {status}: {n_ok:,}/{TOTAL:,} all-egress-1-thread combos passed "
          f"({n_fail} failures)")
    perf(t0, TOTAL, TOTAL, n_del)


# ---------------------------------------------------------------------------
# 3. FULL-GROUP BROADCAST  (bank b -> all 4 threads of egress group E)
#    32 banks × 8 egress groups = 256 tests
# ---------------------------------------------------------------------------
def test_full_group_broadcast() -> None:
    """
    256 tests.  For every (bank, egress_group) pair, the bank sends a 4-thread
    multicast to all threads in that egress group.

    Stretch is maximized when ingress_group(bank) is as far as possible from
    the target egress group.

    Trace: bank 1 -> egress group 4 (threads 16-19).
      bank 1 is in ingress 0 (banks 0-3);  egress 4 is 4 groups away.
    """
    t0    = section("3. FULL-GROUP BROADCAST  (bank b -> all 4 threads of egress E)  [256]")
    net_t = ClosNetwork(verbose=True)
    net   = ClosNetwork(verbose=False)
    n_ok  = n_fail = n_inj = n_del = 0

    for b in range(NUM_BANKS):
        for e in range(NUM_EGRESS):
            threads = list(range(e * THREADS_PER_EGRESS, (e + 1) * THREADS_PER_EGRESS))
            dm      = mk(*threads)
            dv      = 0xA3000000 | (b << 8) | e
            exp     = {t: dv for t in threads}
            flit    = Flit.make(dest_mask=dm, data=dv)
            stretch = abs(b // BANKS_PER_INGRESS - e)

            if b == 1 and e == 4:
                print(f"\n  [TRACE] bank={b} (ingress {b // BANKS_PER_INGRESS}) "
                      f"-> egress_grp={e}  threads={threads}")
                print(f"    dest_mask=0x{dm:08X}  data=0x{dv:08X}")
                print(f"    stretch: {stretch} egress groups apart")
                d, ok = send_check(net_t, {b: flit}, exp, f"FGB-b{b}-e{e}")
            else:
                d, ok = send_check(net, {b: flit}, exp, f"FGB-b{b}-e{e}")

            n_inj += 1
            n_del += d
            if ok:
                n_ok += 1
            else:
                n_fail += 1
            tag = PASS if ok else FAIL
            print(f"  {tag}: bank={b:2d} -> egr={e}  "
                  f"threads={threads}  stretch={stretch}  data=0x{dv:08X}")

    total  = NUM_BANKS * NUM_EGRESS
    status = PASS if n_fail == 0 else FAIL
    print(f"\n  {status}: {n_ok}/{total} full-group broadcasts passed")
    perf(t0, total, n_inj, n_del)


# ---------------------------------------------------------------------------
# 4. N-EGRESS ACTIVE SWEEP  (all C(8,N) combos for N=1..8)
#    Sends to the first thread of each active egress group.
#    Total: sum C(8,N) for N=1..8 = 2^8 - 1 = 255 tests
# ---------------------------------------------------------------------------
def test_n_egress_active_sweep() -> None:
    """
    255 tests covering every possible subset of active egress groups.
    Each test picks the first thread (offset 0) of every active group.
    Exercises all possible 'widths' of multicast spanning.

    N=1 -> 8 tests  (single egress, no stretch)
    N=2 -> 28 tests (two egress groups)
    ...
    N=8 -> 1 test   (all 8 egress groups = broadcast to thread 0 of each)

    Trace: N=4 with groups {0, 2, 4, 6} (alternating, wide spread).
    """
    t0    = section("4. N-EGRESS ACTIVE SWEEP  (all C(8,N) for N=1..8 = 255 combos)")
    net_t = ClosNetwork(verbose=True)
    net   = ClosNetwork(verbose=False)
    n_ok  = n_fail = n_inj = n_del = 0
    TRACE = frozenset({0, 2, 4, 6})

    for n in range(1, NUM_EGRESS + 1):
        n_ok_n = n_fail_n = 0
        for active in combinations(range(NUM_EGRESS), n):
            threads = [g * THREADS_PER_EGRESS for g in active]
            dm      = mk(*threads)
            dv      = 0xA4000000 | (n << 16) | sum(1 << g for g in active)
            exp     = {t: dv for t in threads}
            flit    = Flit.make(dest_mask=dm, data=dv)

            if frozenset(active) == TRACE:
                print(f"\n  [TRACE] N={n}  active_groups={list(active)}  threads={threads}")
                print(f"    dest_mask=0x{dm:08X}  data=0x{dv:08X}")
                for g, t in zip(active, threads):
                    print(f"    egress {g}: thread {t}")
                d, ok = send_check(net_t, {0: flit}, exp, f"NEgr-N{n}-{tuple(active)}")
            else:
                d, ok = send_check(net, {0: flit}, exp, f"NEgr-N{n}-{tuple(active)}")

            n_inj += 1
            n_del += d
            if ok:
                n_ok += 1
                n_ok_n += 1
            else:
                n_fail += 1
                n_fail_n += 1
                if n_fail_n <= 3:
                    print(f"  {FAIL}: N={n} active={list(active)} threads={threads}")

        cnt    = math_comb(NUM_EGRESS, n)
        status = PASS if n_fail_n == 0 else FAIL
        print(f"  {status}: N={n}  C(8,{n})={cnt:3d}  {n_ok_n}/{cnt} passed")

    total  = 2 ** NUM_EGRESS - 1
    status = PASS if n_fail == 0 else FAIL
    print(f"\n  {status}: {n_ok}/{total} N-egress combos passed")
    perf(t0, total, n_inj, n_del)


# ---------------------------------------------------------------------------
# 5. ROTATING DIAGONAL MULTICAST
#    bank b -> {(b + k*4) % 32 for k = 0..7}
#    = exactly one thread per egress group, rotated by the bank index.
# ---------------------------------------------------------------------------
def test_rotating_diagonal() -> None:
    """
    32 tests.  Bank b sends to one thread per egress group; the thread
    within each group is chosen as (b + k*4) % 32, so the pattern
    'rotates' as b increases.

    Only 4 unique dest_mask patterns exist (period 4 in b), but all 32
    banks are tested independently to verify routing from every source.

    Trace: bank 3 -> threads [3,7,11,15,19,23,27,31] (one per egress group).
    """
    t0    = section("5. ROTATING DIAGONAL MULTICAST  (bank b -> {(b+k*4)%32 for k=0..7})")
    net_t = ClosNetwork(verbose=True)
    net   = ClosNetwork(verbose=False)
    n_ok  = n_inj = n_del = 0

    for b in range(NUM_BANKS):
        threads = sorted({(b + k * THREADS_PER_EGRESS) % NUM_THREADS
                          for k in range(NUM_EGRESS)})
        assert len({egr_grp(t) for t in threads}) == NUM_EGRESS, \
            f"bank {b}: not all egress groups covered"
        dm   = mk(*threads)
        dv   = 0xA5000000 | b
        exp  = {t: dv for t in threads}
        flit = Flit.make(dest_mask=dm, data=dv)

        if b == 3:
            print(f"\n  [TRACE] bank={b}  threads={threads}")
            print(f"    dest_mask=0x{dm:08X}  data=0x{dv:08X}")
            for t in threads:
                print(f"    thread {t:2d} -> egress group {egr_grp(t)}")
            d, ok = send_check(net_t, {b: flit}, exp, f"RotDiag-b{b}")
        else:
            d, ok = send_check(net, {b: flit}, exp, f"RotDiag-b{b}")

        n_inj += 1
        n_del += d
        if ok:
            n_ok += 1
        tag  = PASS if ok else FAIL
        grps = [egr_grp(t) for t in threads]
        print(f"  {tag}: bank={b:2d}  threads={threads}  egr_grps={grps}")

    status = PASS if n_ok == NUM_BANKS else FAIL
    print(f"\n  {status}: {n_ok}/{NUM_BANKS} rotating-diagonal multicasts passed")
    perf(t0, NUM_BANKS, n_inj, n_del)


# ---------------------------------------------------------------------------
# 6. SIMULTANEOUS CROSS-INGRESS STRETCH
#    8 banks (one per ingress switch) fire simultaneously.
#    Bank at ingress I -> egress group (I + offset) % 8
#    Tested for all 8 offset values (0 = same group, 4 = maximum stretch).
#    Each offset covers all 32 threads across all 8 egress groups.
# ---------------------------------------------------------------------------
def test_simultaneous_cross_ingress() -> None:
    """
    8 tests (one per offset 0..7).
    Each batch has 8 banks firing simultaneously, each targeting a different
    egress group (no conflict: distinct ingress, distinct target egress).

    Offset 0 -> each ingress targets its 'own' egress group (identity).
    Offset 4 -> maximum stretch: every ingress targets the egress group
               that is farthest away in the circular topology.

    Trace: offset=4 (maximum stretch).
    """
    t0    = section("6. SIMULTANEOUS CROSS-INGRESS STRETCH  (8 offsets × 32 threads)")
    net_t = ClosNetwork(verbose=True)
    net   = ClosNetwork(verbose=False)
    n_ok  = n_inj = n_del = 0

    for offset in range(NUM_EGRESS):
        batch    : dict[int, Flit] = {}
        expected : dict[int, int]  = {}

        for ing in range(NUM_INGRESS):
            bank    = ing * BANKS_PER_INGRESS
            egr_g   = (ing + offset) % NUM_EGRESS
            threads = list(range(egr_g * THREADS_PER_EGRESS,
                                 (egr_g + 1) * THREADS_PER_EGRESS))
            dv      = 0xA6000000 | (offset << 8) | ing
            dm      = mk(*threads)
            batch[bank] = Flit.make(dest_mask=dm, data=dv)
            for t in threads:
                expected[t] = dv

        if offset == 4:
            print(f"\n  [TRACE] offset={offset} (maximum stretch = {offset} egress hops)")
            for bank, flit in sorted(batch.items()):
                ing = bank // BANKS_PER_INGRESS
                thr = active_threads(flit.dest_mask)
                print(f"    bank={bank:2d} (ingress {ing}) -> "
                      f"egr_grp={(ing+offset)%NUM_EGRESS}  threads={thr}  "
                      f"data=0x{flit.data:08X}")
            deliveries = net_t.send(batch)
            total      = sum(len(v) for v in deliveries.values())
            ok         = True
            for t, dv in expected.items():
                rxs = deliveries.get(t, [])
                if not (len(rxs) == 1 and rxs[0][0] == dv and rxs[0][1] == ERR_GOOD):
                    ok = False
                    failures.append(f"SimCross-off{offset}: thread {t} expected "
                                    f"0x{dv:08X}, got {rxs}")
            stray = {t for t in deliveries if t not in expected}
            if stray:
                ok = False
                failures.append(f"SimCross-off{offset}: stray threads {sorted(stray)}")
        else:
            total, ok = send_check(net, batch, expected, f"SimCross-off{offset}")

        n_inj += len(batch)
        n_del += total
        if ok:
            n_ok += 1
        tag = PASS if ok else FAIL
        print(f"  {tag}: offset={offset}  stretch={min(offset, NUM_EGRESS-offset)} hops  "
              f"banks={sorted(batch.keys())}  threads_delivered={len(expected)}")

    status = PASS if n_ok == NUM_EGRESS else FAIL
    print(f"\n  {status}: {n_ok}/{NUM_EGRESS} cross-ingress offset variants passed")
    perf(t0, NUM_EGRESS, n_inj, n_del)


# ---------------------------------------------------------------------------
# 7. PIPELINE STRETCH  (back-to-back spanning flits via tick())
#    8 flits injected consecutively, each spanning all 8 egress groups.
# ---------------------------------------------------------------------------
def test_pipeline_stretch() -> None:
    """
    8 flits, one per cycle, each a distinct rotating-diagonal pattern.
    Each flit hits all 8 egress groups (one thread per group).
    Uses tick() directly to inject back-to-back.

    Flit k:  bank = k * BANKS_PER_INGRESS (one per ingress)
             threads = {(k + g*4) % 32 for g = 0..7}
             injected at cycle k+1, exits at cycle k+3 (3-stage latency)

    The test verifies:
      - Each flit appears at exactly the right output cycle
      - No flit leaks into adjacent output cycles
      - All 8 egress groups are covered per flit
    """
    t0  = section("7. PIPELINE STRETCH  (8 back-to-back all-egress spanning flits)")
    net = ClosNetwork(verbose=True)
    N   = NUM_EGRESS

    batches  : list[dict[int, Flit]] = []
    expected : list[dict[int, int]]  = []

    for k in range(N):
        bank    = k * BANKS_PER_INGRESS
        threads = sorted({(k + g * THREADS_PER_EGRESS) % NUM_THREADS
                          for g in range(NUM_EGRESS)})
        dm      = mk(*threads)
        dv      = 0xA7000000 | k
        batches.append({bank: Flit.make(dest_mask=dm, data=dv)})
        expected.append({t: dv for t in threads})

    print(f"\n  Injecting {N} spanning flits (all-egress) back-to-back:")
    for i, (fb, exp) in enumerate(zip(batches, expected)):
        bank = next(iter(fb))
        f    = fb[bank]
        thr  = sorted(exp.keys())
        print(f"    Cycle {i+1}: bank={bank:2d}  dest_mask=0x{f.dest_mask:08X}  "
              f"data=0x{f.data:08X}  threads={thr}")

    # Inject N cycles + drain 2
    all_out = [net.tick(fb) for fb in batches]
    all_out.append(net.tick({}))
    all_out.append(net.tick({}))

    print(f"\n  Checking outputs:")
    ok    = True
    n_ok  = 0
    n_del = 0

    for k in range(N):
        out_cycle  = k + 2          # 0-indexed output slot
        deliveries = all_out[out_cycle]
        exp        = expected[k]
        n_del += sum(len(v) for v in deliveries.values())

        good = all(
            len(deliveries.get(t, [])) == 1 and
            deliveries[t][0][0] == exp[t] and
            deliveries[t][0][1] == ERR_GOOD
            for t in exp
        )
        stray = {t for t in deliveries if t not in exp}
        if stray:
            good = False
            failures.append(f"PipeStretch-flit{k}: stray threads {sorted(stray)}")

        tag = PASS if good else FAIL
        print(f"  {tag}: flit {k}  inject=cycle {k+1}  exit=cycle {out_cycle+1}  "
              f"threads={sorted(exp.keys())}")
        if good:
            n_ok += 1
        else:
            ok = False
            failures.append(f"PipeStretch-flit{k}: delivery check failed")

    # Verify no flit leaks into wrong output slot
    for k in range(N):
        exp      = expected[k]
        correct  = k + 2
        for idx, deliveries in enumerate(all_out):
            if idx == correct:
                continue
            for t, dv in exp.items():
                rxs = deliveries.get(t, [])
                if rxs and rxs[0][0] == dv:
                    ok = False
                    failures.append(
                        f"PipeStretch-flit{k}: appeared at wrong cycle {idx+1}, "
                        f"expected cycle {correct+1}")
                    print(f"  {FAIL}: flit {k} leaked to output cycle {idx+1}")

    status = PASS if ok else FAIL
    print(f"\n  {status}: {n_ok}/{N} pipeline stretch flits delivered correctly "
          f"(3-cycle latency, no cross-cycle leakage)")
    perf(t0, N, N, n_del)


# ---------------------------------------------------------------------------
# 8. FULLY-LOADED PIPELINE — all 32 stretch flits back-to-back via tick()
#
# Every cycle a new spanning flit enters ingress at the SAME TIME as the
# previous one advances through middle and the one before exits egress.
# All three stages are active simultaneously from cycle 3 onward.
#
# Each flit uses a rotating-diagonal dest_mask (one thread per egress group)
# so every flit is a true full-network stretch.  32 banks are exercised in
# order; each cycle one bank injects, no bank repeats.
#
# Timeline (I=ingress, M=middle, E=egress, '-'=idle):
#
#   Cycle  1:  flit 0  [I  -  -]
#   Cycle  2:  flit 1  [I  M  -]   flit 0 in middle
#   Cycle  3:  flit 2  [I  M  E]   flit 0 exits — ALL 3 STAGES LIVE
#   Cycle  4:  flit 3  [I  M  E]   flit 1 exits
#   ...
#   Cycle 32:  flit31  [I  M  E]   flit29 exits
#   Cycle 33:  drain   [-  M  E]   flit30 exits
#   Cycle 34:  drain   [-  -  E]   flit31 exits
#
# Verification: all_out[k+2] must contain exactly the 8 deliveries from
# flit k, with no bleed into adjacent slots.
# ---------------------------------------------------------------------------
def test_full_pipeline_all_stretch() -> None:
    """
    32 back-to-back spanning flits (one per bank, all 32 banks) through the
    full 3-stage Clos pipeline using tick().

    Each flit targets all 8 egress groups (one thread per group) — maximum
    possible network stretch.  All three pipeline stages are live
    simultaneously from cycle 3 through cycle 32.

    Verbose trace is printed for cycles 1-6 to show the ramp-up from
    empty to fully loaded, plus cycle 33-34 drain.  Cycles 7-32 are
    silent (results checked, printed as single PASS/FAIL per flit).
    """
    t0  = section("8. FULLY-LOADED PIPELINE  (32 stretch flits, all 3 stages live)")
    N   = NUM_BANKS   # 32 inject cycles

    # Build one batch per cycle: bank k -> rotating-diagonal dest_mask
    batches  : list[dict[int, Flit]] = []
    expected : list[dict[int, int]]  = []

    for k in range(N):
        threads = sorted({(k + g * THREADS_PER_EGRESS) % NUM_THREADS
                          for g in range(NUM_EGRESS)})
        dm      = mk(*threads)
        dv      = 0xA8000000 | k
        batches.append({k: Flit.make(dest_mask=dm, data=dv)})
        expected.append({t: dv for t in threads})

    # Print batch plan
    print(f"\n  {N} batches queued (bank k -> 8 egress groups, rotating diagonal):")
    for k, (fb, exp) in enumerate(zip(batches, expected)):
        bank = k
        thr  = sorted(exp.keys())
        grps = [egr_grp(t) for t in thr]
        print(f"    Batch {k:2d}: bank={bank:2d}  threads={thr}  "
              f"egr_grps={grps}  data=0xA8{k:06X}")

    # Verbose for first 6 inject cycles + drain; silent in between
    net = ClosNetwork(verbose=True)

    all_out: list[dict] = []

    print(f"\n  --- Injecting {N} cycles + 2 drain cycles ---")
    for k, fb in enumerate(batches):
        bank = k
        f    = fb[bank]
        if k < 6:
            print(f"\n  >> Cycle {k+1}: inject bank={bank}  "
                  f"dest_mask=0x{f.dest_mask:08X}  data=0x{f.data:08X}")
            print(f"     (threads={sorted(expected[k].keys())})")
            net.verbose = True
        else:
            net.verbose = False
        all_out.append(net.tick(fb))

    # Drain
    for d in range(2):
        cyc = N + d + 1
        net.verbose = True
        print(f"\n  >> Cycle {cyc} (drain {d+1})")
        all_out.append(net.tick({}))

    # ---- Verify outputs ----
    print(f"\n  --- Checking {N} output slots (flit k exits at cycle k+3) ---")
    ok     = True
    n_ok   = 0
    n_del  = 0
    # Track whether a thread received data in a non-expected slot
    # (data value encodes which flit it came from, so misrouting is detectable)

    for k in range(N):
        out_idx    = k + 2                    # 0-indexed slot in all_out
        deliveries = all_out[out_idx]
        exp        = expected[k]
        n_del     += sum(len(v) for v in deliveries.values())

        # Every expected thread gets the right data
        good = all(
            len(deliveries.get(t, [])) == 1 and
            deliveries[t][0][0] == exp[t] and
            deliveries[t][0][1] == ERR_GOOD
            for t in exp
        )
        # No thread outside the expected set received this flit's data
        for t, rxs in deliveries.items():
            if t not in exp:
                good = False
                failures.append(
                    f"FullPipe-flit{k}: stray delivery to thread {t}: {rxs}")

        # No bleed: flit k's data must NOT appear in any other slot
        for other_idx, other_del in enumerate(all_out):
            if other_idx == out_idx:
                continue
            for t, dv in exp.items():
                rxs = other_del.get(t, [])
                if rxs and rxs[0][0] == dv:
                    good = False
                    failures.append(
                        f"FullPipe-flit{k}: data leaked to cycle {other_idx+1} "
                        f"(expected cycle {out_idx+1})")

        tag    = PASS if good else FAIL
        status = f"cycle {out_idx+1}"
        thr    = sorted(exp.keys())
        print(f"  {tag}: flit {k:2d}  bank={k:2d}->egr_grps={[egr_grp(t) for t in thr]}"
              f"  exits=cycle {out_idx+1}")
        if good:
            n_ok += 1
        else:
            ok = False

    # Summary — show which cycles had how many stages live
    print(f"\n  Pipeline utilization:")
    print(f"    Ramp-up  : cycles 1-2  (1 then 2 stages active)")
    print(f"    Steady   : cycles 3-{N}  ({N-2} cycles with all 3 stages live simultaneously)")
    print(f"    Drain    : cycles {N+1}-{N+2}  (2 then 1 stage active)")

    status = PASS if ok else FAIL
    print(f"\n  {status}: {n_ok}/{N} flits delivered at correct cycle "
          f"with zero bleed between slots")
    perf(t0, N, N, n_del)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def main() -> None:
    t_total = time.perf_counter()

    print("=" * 64)
    print("  Clos Network — STRETCH TESTS + PERFORMANCE METRICS")
    print("=" * 64)
    print("""
  Stretch = a flit destined for threads in egress groups far from
  the source bank's ingress group, or simultaneously targeting
  many / all of the 8 egress groups.
""")

    test_max_distance_pairs()
    test_all_egress_one_thread_exhaustive()
    test_full_group_broadcast()
    test_n_egress_active_sweep()
    test_rotating_diagonal()
    test_simultaneous_cross_ingress()
    test_pipeline_stretch()
    test_full_pipeline_all_stretch()

    elapsed_total = time.perf_counter() - t_total
    print(f"\n{'=' * 64}")
    print(f"  Total wall-clock time: {elapsed_total:.2f} s")

    if failures:
        print(f"  RESULT: {len(failures)} FAILURE(S)")
        for f in failures:
            print(f"    - {f}")
        sys.exit(1)
    else:
        print("  RESULT: ALL STRETCH TESTS PASSED")
    print("=" * 64)


if __name__ == "__main__":
    main()
