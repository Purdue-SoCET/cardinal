"""
3-Stage Clos Network Simulation for Shared Memory System
=========================================================
Architecture:
  - 32 SRAM banks, 32 threads
  - 8 ingress switches  (4 inputs  x 8 outputs)
  - 8 middle  switches  (8 inputs  x 8 outputs)
  - 8 egress  switches  (8 inputs  x 4 outputs)

Flit format [65:0]:
  [65:34] = destination bitmask (32 bits, one bit per thread)
  [33: 2] = read data (32 bits)
  [ 1: 0] = error code  00=good  01=access violation
                        10=hardware ECC error  11=unmapped

thread_rx_flit [33:0]: dest-bitmask stripped; {data[31:0], error[1:0]}
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NUM_BANKS          = 32
NUM_THREADS        = 32
NUM_INGRESS        = 8   # ingress switches
NUM_MIDDLE         = 8   # middle switches
NUM_EGRESS         = 8   # egress switches
BANKS_PER_INGRESS  = 4   # banks feeding one ingress switch
THREADS_PER_EGRESS = 4   # threads served by one egress switch

ERR_GOOD      = 0b00
ERR_ACCESS    = 0b01
ERR_ECC       = 0b10
ERR_UNMAPPED  = 0b11

ERR_NAMES = {ERR_GOOD: "GOOD", ERR_ACCESS: "ACCESS_VIOLATION",
             ERR_ECC: "HW_ECC_ERROR", ERR_UNMAPPED: "UNMAPPED"}


# ---------------------------------------------------------------------------
# Flit
# ---------------------------------------------------------------------------
@dataclass
class Flit:
    """
    Represents a 66-bit flit travelling through the network.

    dest_mask : 32-bit bitmask, bit i set => thread i is a destination [65:34]
    data      : 32-bit read payload                                     [33: 2]
    error     : 2-bit error code                                        [ 1: 0]

    thread_rx_flit view: (data, error) — dest_mask stripped at egress output.
    """
    dest_mask : int = 0          # bits [65:34]
    data      : int = 0          # bits [33: 2]
    error     : int = ERR_GOOD   # bits [ 1: 0]

    # --- convenience constructors ---

    @staticmethod
    def make(dest_mask: int, data: int, error: int = ERR_GOOD) -> "Flit":
        return Flit(dest_mask=dest_mask & 0xFFFF_FFFF,
                    data=data & 0xFFFF_FFFF,
                    error=error & 0x3)

    # --- bit-field packing / unpacking (for reference correctness) ---

    def pack(self) -> int:
        """Pack into a 66-bit integer."""
        return ((self.dest_mask & 0xFFFF_FFFF) << 34 |
                (self.data      & 0xFFFF_FFFF) <<  2 |
                (self.error     & 0x3))

    @staticmethod
    def unpack(bits: int) -> "Flit":
        """Unpack from a 66-bit integer."""
        return Flit(dest_mask = (bits >> 34) & 0xFFFF_FFFF,
                    data      = (bits >>  2) & 0xFFFF_FFFF,
                    error     = (bits      ) & 0x3)

    def thread_rx(self) -> Tuple[int, int]:
        """Return (data, error) as seen by a receiving thread [33:0] view."""
        return (self.data, self.error)

    def copy_for_dest(self, subset_mask: int) -> "Flit":
        """Clone this flit but restrict dest_mask to subset_mask."""
        f = copy.copy(self)
        f.dest_mask = self.dest_mask & subset_mask
        return f

    def __repr__(self) -> str:
        threads = [i for i in range(NUM_THREADS) if (self.dest_mask >> i) & 1]
        return (f"Flit(dest={threads}, data=0x{self.data:08X}, "
                f"err={ERR_NAMES[self.error]})")


# ---------------------------------------------------------------------------
# MSHR (Miss Status Handling Register)
# ---------------------------------------------------------------------------
@dataclass
class MSHREntry:
    """One MSHR entry tracks an outstanding miss to a given address."""
    address     : int
    dest_mask   : int   # merged destination bitmask (all requesters)
    data        : Optional[int]  = None
    error       : int            = ERR_GOOD
    completed   : bool           = False


class MSHRTable:
    """
    Per-bank MSHR table.

    Coalescing happens upstream in hardware before the response enters the
    network — entries arrive here with dest_mask already fully formed.

    Supports:
      - allocate(address, dest_mask) -> entry_id
      - complete(entry_id, data, err) -> Flit ready for multicast
      - free(entry_id)
    """
    def __init__(self, bank_id: int, num_entries: int = 16):
        self.bank_id     = bank_id
        self.num_entries = num_entries
        self._table: Dict[int, MSHREntry] = {}
        self._next_id = 0

    def allocate(self, address: int, dest_mask: int) -> int:
        """Allocate a new MSHR entry with a pre-coalesced dest_mask."""
        eid = self._next_id
        self._next_id += 1
        self._table[eid] = MSHREntry(address=address, dest_mask=dest_mask)
        return eid

    def complete(self, entry_id: int, data: int,
                 error: int = ERR_GOOD) -> Optional[Flit]:
        """Mark entry complete; return multicast Flit (or None if not found)."""
        entry = self._table.get(entry_id)
        if entry is None:
            return None
        entry.data      = data
        entry.error     = error
        entry.completed = True
        return Flit.make(dest_mask=entry.dest_mask, data=data, error=error)

    def free(self, entry_id: int) -> None:
        self._table.pop(entry_id, None)


# ---------------------------------------------------------------------------
# Ingress Switch  (4 bank inputs -> 8 middle outputs)
# ---------------------------------------------------------------------------
class IngressSwitch:
    """
    Accepts flits from up to 4 banks.
    For each flit, replicates to the subset of middle switches whose egress
    switches are covered by dest_mask.
    """
    def __init__(self, switch_id: int):
        self.switch_id = switch_id

    def process(self, flits: List[Flit]) -> List[List[Optional[Flit]]]:
        """
        Input : list of flits (one per bank port, None if idle)
        Output: per-middle-switch list of flits to forward.
                output[m] = list of flits destined for middle switch m.
        """
        output: List[List[Flit]] = [[] for _ in range(NUM_MIDDLE)]

        for flit in flits:
            if flit is None:
                continue
            # Determine which egress switches are needed.
            # Diagonal routing: ingress s sends egress group e via middle (s+e) & (N-1).
            # egress_mask for group e = 0xF << (e << 2)  (4 threads per group, shift by log2(4)=2)
            for egress_id in range(NUM_EGRESS):
                lo          = egress_id << 2          # egress_id * THREADS_PER_EGRESS
                egress_mask = 0xF << lo               # 4-bit mask for this group
                if flit.dest_mask & egress_mask:
                    m = (self.switch_id + egress_id) & (NUM_MIDDLE - 1)
                    sub_flit = flit.copy_for_dest(egress_mask)
                    output[m].append(sub_flit)

        return output


# ---------------------------------------------------------------------------
# Middle Switch  (8 ingress inputs -> 8 egress outputs)
# ---------------------------------------------------------------------------
class MiddleSwitch:
    """
    Collects flits from all 8 ingress switches.
    Routes each flit to the correct egress switch based on dest_mask —
    whichever nibble of dest_mask is non-zero determines the target egress.
    """
    def __init__(self, switch_id: int):
        self.switch_id = switch_id

    def process(self, flits: List[Optional[Flit]]) -> Dict[int, List[Flit]]:
        """
        Input : flits[i] = flit arriving from ingress switch i (or None).
        Output: dict { egress_id -> [flits] } routed by dest_mask nibble.
        """
        output: Dict[int, List[Flit]] = {e: [] for e in range(NUM_EGRESS)}
        for f in flits:
            if f is None:
                continue
            for e in range(NUM_EGRESS):
                if (f.dest_mask >> (e << 2)) & 0xF:   # e << 2 == e * THREADS_PER_EGRESS
                    output[e].append(f)
                    break
        return output


# ---------------------------------------------------------------------------
# Egress Switch  (8 middle inputs -> 4 thread outputs)
# ---------------------------------------------------------------------------
class EgressSwitch:
    """
    Receives flits from middle switch.
    Delivers (data, error) to each destination thread in its local group.
    """
    def __init__(self, switch_id: int):
        self.switch_id   = switch_id
        self.thread_base = switch_id * THREADS_PER_EGRESS   # first thread id

    def process(self, flits: List[Flit]) -> Dict[int, Tuple[int, int]]:
        """
        Input : list of flits from the middle switch.
        Output: dict { thread_id -> (data, error) }  for local threads only.
        """
        deliveries: Dict[int, Tuple[int, int]] = {}
        for flit in flits:
            for local in range(THREADS_PER_EGRESS):
                tid = self.thread_base + local
                if (flit.dest_mask >> tid) & 1:
                    deliveries[tid] = flit.thread_rx()
        return deliveries


# ---------------------------------------------------------------------------
# Full Clos Network
# ---------------------------------------------------------------------------
class ClosNetwork:
    """
    3-stage Clos network connecting 32 SRAM banks to 32 threads.

    Pipelined interface:
      tick(flits_from_banks) -> deliveries
        All three stages advance simultaneously each clock cycle:
          - Ingress: processes new flits_from_banks -> fills _pipe_ing_to_mid
          - Middle:  processes _pipe_ing_to_mid     -> fills _pipe_mid_to_egr
          - Egress:  processes _pipe_mid_to_egr     -> returns deliveries
        First delivery appears on the 3rd tick after injection.

    Legacy interface:
      send(flits_from_banks) -> deliveries
        Resets pipeline, injects one batch, drains two empty cycles,
        returns deliveries from the egress cycle. Backward-compatible.
    """

    def __init__(self, verbose: bool = False):
        self.ingress = [IngressSwitch(i) for i in range(NUM_INGRESS)]
        self.middle  = [MiddleSwitch(i)  for i in range(NUM_MIDDLE)]
        self.egress  = [EgressSwitch(i)  for i in range(NUM_EGRESS)]
        self.verbose = verbose
        self._cycle  = 0

        # Pipeline registers — inter-stage state held between ticks
        self._pipe_ing_to_mid: List[List[Flit]] = [[] for _ in range(NUM_MIDDLE)]
        self._pipe_mid_to_egr: List[List[Flit]] = [[] for _ in range(NUM_EGRESS)]

    def _reset_pipeline(self) -> None:
        """Clear all pipeline registers (flush in-flight flits)."""
        self._pipe_ing_to_mid = [[] for _ in range(NUM_MIDDLE)]
        self._pipe_mid_to_egr = [[] for _ in range(NUM_EGRESS)]
        self._cycle = 0

    @staticmethod
    def _mask_threads(mask: int) -> List[int]:
        return [i for i in range(NUM_THREADS) if (mask >> i) & 1]

    def tick(self, flits_from_banks: Dict[int, Flit]) -> Dict[int, List[Tuple[int, int]]]:
        """
        Advance the network by one clock cycle.

        All three stages read from the *current* pipeline registers and compute
        their outputs simultaneously, then the registers are updated atomically.

          Egress  reads  _pipe_mid_to_egr  -> returns deliveries this cycle
          Middle  reads  _pipe_ing_to_mid  -> new _pipe_mid_to_egr next cycle
          Ingress reads  flits_from_banks  -> new _pipe_ing_to_mid next cycle
        """
        self._cycle += 1
        v = self.verbose

        ing_active = bool(flits_from_banks)
        mid_active = any(self._pipe_ing_to_mid)
        egr_active = any(self._pipe_mid_to_egr)

        if v and (ing_active or mid_active or egr_active):
            print(f"    [Cycle {self._cycle}]")

        # --- Stage 3: Egress (reads current _pipe_mid_to_egr) ---
        deliveries: Dict[int, List[Tuple[int, int]]] = {}

        if v and egr_active:
            print(f"      Stage 3 - EGRESS:")
        for e, eg_sw in enumerate(self.egress):
            flits_in = self._pipe_mid_to_egr[e]
            if v and flits_in:
                for f in flits_in:
                    print(f"        Egress {e}: dest=0x{f.dest_mask:08X}  "
                          f"data=0x{f.data:08X}  threads={self._mask_threads(f.dest_mask)}")
            for tid, rx in eg_sw.process(flits_in).items():
                deliveries.setdefault(tid, []).append(rx)
                if v:
                    print(f"          -> Thread {tid:2d}: data=0x{rx[0]:08X}  err={ERR_NAMES[rx[1]]}")

        # --- Stage 2: Middle (reads current _pipe_ing_to_mid) ---
        new_mid_to_egr: List[List[Flit]] = [[] for _ in range(NUM_EGRESS)]

        if v and mid_active:
            print(f"      Stage 2 - MIDDLE:")
        for m, mid_sw in enumerate(self.middle):
            flits_in = self._pipe_ing_to_mid[m]
            if v and flits_in:
                print(f"        Middle {m}: {len(flits_in)} flit(s)")
                for f in flits_in:
                    print(f"          flit: dest=0x{f.dest_mask:08X}  data=0x{f.data:08X}  "
                          f"threads={self._mask_threads(f.dest_mask)}")
            for e, flits in mid_sw.process(flits_in).items():
                new_mid_to_egr[e].extend(flits)
                if v and flits:
                    for f in flits:
                        print(f"          -> Egress {e}: dest=0x{f.dest_mask:08X}  data=0x{f.data:08X}")

        # --- Stage 1: Ingress (processes new inputs) ---
        new_ing_to_mid: List[List[Flit]] = [[] for _ in range(NUM_MIDDLE)]

        if v and ing_active:
            print(f"      Stage 1 - INGRESS:")
        for ingress_id, ing_sw in enumerate(self.ingress):
            bank_flits: List[Optional[Flit]] = [
                flits_from_banks.get(ingress_id * BANKS_PER_INGRESS + lb)
                for lb in range(BANKS_PER_INGRESS)
            ]
            active = [(ingress_id * BANKS_PER_INGRESS + lb, bank_flits[lb])
                      for lb in range(BANKS_PER_INGRESS) if bank_flits[lb] is not None]

            ing_output = ing_sw.process(bank_flits)
            for m, flit_list in enumerate(ing_output):
                new_ing_to_mid[m].extend(flit_list)

            if v and active:
                print(f"        Ingress {ingress_id}:")
                for bank_id, f in active:
                    print(f"          Bank {bank_id:2d}: dest=0x{f.dest_mask:08X}  "
                          f"data=0x{f.data:08X}  err={ERR_NAMES[f.error]}  "
                          f"threads={self._mask_threads(f.dest_mask)}")
                for m, flit_list in enumerate(ing_output):
                    for sf in flit_list:
                        egress_grp = (m - ingress_id) % NUM_MIDDLE
                        print(f"          -> Middle {m}: dest=0x{sf.dest_mask:08X}  "
                              f"threads={self._mask_threads(sf.dest_mask)}  "
                              f"(for Egress {egress_grp})")

        # Advance pipeline registers atomically
        self._pipe_ing_to_mid = new_ing_to_mid
        self._pipe_mid_to_egr = new_mid_to_egr

        return deliveries

    def send(self, flits_from_banks: Dict[int, Flit]) -> Dict[int, List[Tuple[int, int]]]:
        """
        Legacy single-batch interface (backward-compatible with existing tests).
        Resets the pipeline, injects one batch, drains two empty cycles, and
        returns deliveries from the egress (3rd) cycle.
        """
        self._reset_pipeline()
        self.tick(flits_from_banks)   # cycle 1: ingress -> _pipe_ing_to_mid
        self.tick({})                  # cycle 2: middle  -> _pipe_mid_to_egr
        return self.tick({})           # cycle 3: egress  -> deliveries


# ---------------------------------------------------------------------------
# SRAM Bank (simplified model)
# ---------------------------------------------------------------------------
@dataclass
class SRAMBank:
    """Simple SRAM bank with address-mapped storage."""
    bank_id     : int
    memory      : Dict[int, int]    = field(default_factory=dict)
    valid_range : Tuple[int, int]   = (0, 0xFFFF)   # inclusive address range

    def write(self, address: int, data: int) -> None:
        self.memory[address] = data & 0xFFFF_FFFF

    def read(self, address: int, dest_mask: int) -> Flit:
        """
        Return a response Flit for the given address and pre-coalesced dest_mask.
        Coalescing of multiple thread requests into dest_mask is the caller's
        responsibility — this bank just reads and wraps the result.
        """
        lo, hi = self.valid_range
        if not (lo <= address <= hi):
            return Flit.make(dest_mask=dest_mask, data=0, error=ERR_UNMAPPED)
        return Flit.make(dest_mask=dest_mask,
                         data=self.memory.get(address, 0),
                         error=ERR_GOOD)


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

def route_flits(network: ClosNetwork,
                flits: Dict[int, Flit]) -> Dict[int, List[Tuple[int, int]]]:
    """Send a batch of flits and return per-thread deliveries."""
    return network.send(flits)


def assert_delivered(deliveries: Dict[int, List[Tuple[int, int]]],
                     thread_id: int,
                     expected_data: int,
                     expected_error: int = ERR_GOOD,
                     test_name: str = "") -> None:
    rxs = deliveries.get(thread_id, [])
    assert rxs, (f"[{test_name}] Thread {thread_id} received nothing. "
                 f"deliveries={deliveries}")
    data, error = rxs[0]
    assert data == expected_data, (
        f"[{test_name}] Thread {thread_id}: data=0x{data:08X} "
        f"expected=0x{expected_data:08X}")
    assert error == expected_error, (
        f"[{test_name}] Thread {thread_id}: error={ERR_NAMES[error]} "
        f"expected={ERR_NAMES[expected_error]}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_1_basic_unicast():
    """Test 1: Basic unicast – bank 0 -> thread 7."""
    print("Test 1: Basic unicast (bank 0 -> thread 7)")
    net   = ClosNetwork()
    banks = [SRAMBank(i) for i in range(NUM_BANKS)]

    banks[0].write(0x0010, 0xDEADBEEF)
    flit = banks[0].read(0x0010, dest_mask=1 << 7)

    deliveries = route_flits(net, {0: flit})
    assert_delivered(deliveries, 7, 0xDEADBEEF, test_name="Test1")

    other = {t: v for t, v in deliveries.items() if t != 7}
    assert not other, f"Unexpected deliveries: {other}"
    print("  PASSED")


def test_2_multi_bank_unicast():
    """Test 2: Unicast from multiple banks to different threads simultaneously."""
    print("Test 2: Multi-bank unicast (banks 0,4,8,16 -> threads 3,7,11,20)")
    net   = ClosNetwork()
    banks = [SRAMBank(i) for i in range(NUM_BANKS)]

    scenarios = [
        (0,  0x100, 0xAAAA0000, 3),
        (4,  0x200, 0xBBBB1111, 7),
        (8,  0x300, 0xCCCC2222, 11),
        (16, 0x400, 0xDDDD3333, 20),
    ]

    flits: Dict[int, Flit] = {}
    for bank_id, addr, data, tid in scenarios:
        banks[bank_id].write(addr, data)
        flits[bank_id] = banks[bank_id].read(addr, dest_mask=1 << tid)

    deliveries = route_flits(net, flits)

    for _, _, data, tid in scenarios:
        assert_delivered(deliveries, tid, data, test_name="Test2")
    print("  PASSED")


def test_3_multicast():
    """Test 3: Multicast – bank 5 -> threads 0,1,4,8,20,31."""
    print("Test 3: Multicast (bank 5 -> threads {0,1,4,8,20,31})")
    net   = ClosNetwork()
    banks = [SRAMBank(i) for i in range(NUM_BANKS)]

    dest_threads = [0, 1, 4, 8, 20, 31]
    dest_mask    = sum(1 << t for t in dest_threads)
    data_val     = 0x12345678

    banks[5].write(0x050, data_val)

    # Manually craft multicast flit (one thread per MSHR entry is insufficient;
    # here we build the flit directly to simulate multi-thread broadcast response)
    flit = Flit.make(dest_mask=dest_mask, data=data_val)

    deliveries = route_flits(net, {5: flit})

    for tid in dest_threads:
        assert_delivered(deliveries, tid, data_val, test_name="Test3")

    non_dest = {t for t in range(NUM_THREADS) if t not in dest_threads}
    stray    = {t: v for t, v in deliveries.items() if t in non_dest}
    assert not stray, f"Stray deliveries to non-dest threads: {stray}"
    print("  PASSED")


def test_4_broadcast():
    """Test 4: Broadcast – bank 10 -> all 32 threads."""
    print("Test 4: Broadcast (bank 10 -> all 32 threads)")
    net      = ClosNetwork()
    data_val = 0xFFFF0000
    all_mask = (1 << NUM_THREADS) - 1

    flit = Flit.make(dest_mask=all_mask, data=data_val)
    deliveries = route_flits(net, {10: flit})

    for tid in range(NUM_THREADS):
        assert_delivered(deliveries, tid, data_val, test_name="Test4")
    print("  PASSED")


def test_5_error_propagation():
    """Test 5: Unmapped address returns error flit to correct thread."""
    print("Test 5: Error propagation (unmapped address -> thread 15)")
    net  = ClosNetwork()
    bank = SRAMBank(2, valid_range=(0x0000, 0x00FF))

    flit = bank.read(0x1000, dest_mask=1 << 15)   # outside range -> ERR_UNMAPPED
    assert flit.error == ERR_UNMAPPED

    deliveries = route_flits(net, {2: flit})
    assert_delivered(deliveries, 15, 0, ERR_UNMAPPED, test_name="Test5")
    print("  PASSED")


def test_6_mshr_multicast():
    """Test 6: MSHR multicast – pre-coalesced dest_mask delivers to both threads."""
    print("Test 6: MSHR multicast (threads 3 and 5, bank 0 address 0x0020)")
    net      = ClosNetwork()
    data_val = 0xCAFEBABE

    # Coalescing already happened upstream; allocate with the combined mask.
    mshr = MSHRTable(bank_id=0)
    eid  = mshr.allocate(0x0020, dest_mask=(1 << 3) | (1 << 5))
    flit = mshr.complete(eid, data_val, ERR_GOOD)
    mshr.free(eid)

    assert flit is not None
    assert (flit.dest_mask >> 3) & 1, "Thread 3 must be in dest_mask"
    assert (flit.dest_mask >> 5) & 1, "Thread 5 must be in dest_mask"

    deliveries = route_flits(net, {0: flit})
    assert_delivered(deliveries, 3, data_val, test_name="Test6-T3")
    assert_delivered(deliveries, 5, data_val, test_name="Test6-T5")

    stray = {t: v for t, v in deliveries.items() if t not in (3, 5)}
    assert not stray, f"Stray deliveries: {stray}"
    print("  PASSED")


def test_7_throughput():
    """Test 7: All 32 banks send simultaneously, all 32 flits delivered."""
    print("Test 7: Throughput – all 32 banks send simultaneously")
    net   = ClosNetwork()
    banks = [SRAMBank(i) for i in range(NUM_BANKS)]

    flits: Dict[int, Flit] = {}
    for bank_id in range(NUM_BANKS):
        data_val = 0xA0000000 | bank_id
        banks[bank_id].write(bank_id * 4, data_val)
        flits[bank_id] = banks[bank_id].read(bank_id * 4, dest_mask=1 << bank_id)

    deliveries = route_flits(net, flits)

    for tid in range(NUM_THREADS):
        assert_delivered(deliveries, tid, 0xA0000000 | tid, test_name="Test7")
    assert len(deliveries) == NUM_THREADS, (
        f"Expected {NUM_THREADS} thread deliveries, got {len(deliveries)}")
    print("  PASSED")


# ---------------------------------------------------------------------------
# Pack / unpack round-trip sanity check
# ---------------------------------------------------------------------------

def test_flit_pack_unpack():
    """Sanity: pack then unpack a flit and verify fields are preserved."""
    print("Test 0: Flit pack/unpack round-trip")
    f  = Flit.make(dest_mask=0xDEAD_BEEF, data=0x1234_5678, error=ERR_ECC)
    f2 = Flit.unpack(f.pack())
    assert f.dest_mask == f2.dest_mask
    assert f.data      == f2.data
    assert f.error     == f2.error
    print("  PASSED")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("3-Stage Clos Network Simulation — Functional Tests")
    print("=" * 60)
    print()

    test_flit_pack_unpack()
    print()
    test_1_basic_unicast()
    print()
    test_2_multi_bank_unicast()
    print()
    test_3_multicast()
    print()
    test_4_broadcast()
    print()
    test_5_error_propagation()
    print()
    test_6_mshr_multicast()
    print()
    test_7_throughput()
    print()
    print("=" * 60)
    print("All tests PASSED.")
    print("=" * 60)


if __name__ == "__main__":
    main()
