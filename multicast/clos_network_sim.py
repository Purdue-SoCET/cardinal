"""
3-Stage Clos Network Simulation for Shared Memory System
=========================================================
Architecture:
  - 32 SRAM banks, 32 threads
  - 8 ingress switches  (4 inputs  x 8 outputs)
  - 8 middle  switches  (8 inputs  x 8 outputs)
  - 8 egress  switches  (8 inputs  x 4 outputs)

Flit format [70:0]:
  [70:39] = destination bitmask (32 bits, one bit per thread)
  [38:7]  = read data (32 bits)
  [6:2]   = reserved / unused
  [1:0]   = error code  00=good  01=access violation
                        10=hardware ECC error  11=unmapped

thread_rx_flit [38:0]: dest-bitmask stripped; only data + error delivered to thread
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
    Represents a 71-bit flit travelling through the network.

    dest_mask : 32-bit bitmask, bit i set => thread i is a destination
    data      : 32-bit read payload
    error     : 2-bit error code
    _reserved : 5-bit reserved field [6:2] (kept but unused)

    thread_rx_flit view: (data, error) — dest_mask stripped at egress output.
    """
    dest_mask : int = 0          # bits [70:39]
    data      : int = 0          # bits [38:7]
    error     : int = ERR_GOOD   # bits [1:0]
    _reserved : int = 0          # bits [6:2]  reserved

    # --- convenience constructors ---

    @staticmethod
    def make(dest_mask: int, data: int, error: int = ERR_GOOD) -> "Flit":
        return Flit(dest_mask=dest_mask & 0xFFFF_FFFF,
                    data=data & 0xFFFF_FFFF,
                    error=error & 0x3)

    # --- bit-field packing / unpacking (for reference correctness) ---

    def pack(self) -> int:
        """Pack into a 71-bit integer."""
        return ((self.dest_mask & 0xFFFF_FFFF) << 39 |
                (self.data      & 0xFFFF_FFFF) <<  7 |
                (self._reserved & 0x1F)         <<  2 |
                (self.error     & 0x3))

    @staticmethod
    def unpack(bits: int) -> "Flit":
        """Unpack from a 71-bit integer."""
        return Flit(dest_mask = (bits >> 39) & 0xFFFF_FFFF,
                    data      = (bits >>  7) & 0xFFFF_FFFF,
                    _reserved = (bits >>  2) & 0x1F,
                    error     = (bits      ) & 0x3)

    def thread_rx(self) -> Tuple[int, int]:
        """Return (data, error) as seen by a receiving thread [38:0] view."""
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

    Supports:
      - allocate(address, thread_id)  -> entry_id
      - merge   (address, thread_id)  -> True if merged into existing entry
      - complete(entry_id, data, err) -> Flit ready for multicast
    """
    def __init__(self, bank_id: int, num_entries: int = 16):
        self.bank_id    = bank_id
        self.num_entries = num_entries
        self._table: Dict[int, MSHREntry] = {}   # address -> entry
        self._id_map: Dict[int, int]      = {}   # entry_id -> address
        self._next_id = 0

    def lookup(self, address: int) -> Optional[int]:
        """Return entry_id if address already has an outstanding miss, else None."""
        for eid, addr in self._id_map.items():
            if addr == address:
                return eid
        return None

    def allocate(self, address: int, thread_id: int) -> int:
        """Allocate a new MSHR entry; return its entry_id."""
        eid = self._next_id
        self._next_id += 1
        entry = MSHREntry(address=address,
                          dest_mask=(1 << thread_id))
        self._table[eid]  = entry
        self._id_map[eid] = address
        return eid

    def merge(self, address: int, thread_id: int) -> Optional[int]:
        """
        If address is already in MSHR, merge thread_id into dest_mask.
        Returns entry_id if merged, else None.
        """
        eid = self.lookup(address)
        if eid is not None:
            self._table[eid].dest_mask |= (1 << thread_id)
            return eid
        return None

    def request(self, address: int, thread_id: int) -> Tuple[int, bool]:
        """
        High-level: merge if possible, otherwise allocate.
        Returns (entry_id, was_merged).
        """
        eid = self.merge(address, thread_id)
        if eid is not None:
            return eid, True
        return self.allocate(address, thread_id), False

    def complete(self, entry_id: int, data: int,
                 error: int = ERR_GOOD) -> Optional[Flit]:
        """Mark entry complete; return multicast Flit (or None if not found)."""
        entry = self._table.get(entry_id)
        if entry is None:
            return None
        entry.data      = data
        entry.error     = error
        entry.completed = True
        flit = Flit.make(dest_mask=entry.dest_mask, data=data, error=error)
        return flit

    def free(self, entry_id: int) -> None:
        self._table.pop(entry_id, None)
        self._id_map.pop(entry_id, None)


# ---------------------------------------------------------------------------
# Switch helpers
# ---------------------------------------------------------------------------

def _egress_id_for_thread(thread_id: int) -> int:
    """Which egress switch serves this thread?"""
    return thread_id // THREADS_PER_EGRESS   # 0-7


def _ingress_id_for_bank(bank_id: int) -> int:
    """Which ingress switch does this bank connect to?"""
    return bank_id // BANKS_PER_INGRESS      # 0-7


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
            # Determine which egress switches are needed
            for egress_id in range(NUM_EGRESS):
                # Thread bits served by this egress switch
                lo = egress_id * THREADS_PER_EGRESS
                hi = lo + THREADS_PER_EGRESS
                egress_mask = 0
                for t in range(lo, hi):
                    egress_mask |= (1 << t)

                if flit.dest_mask & egress_mask:
                    # Need to reach egress_id -> forward to middle switch egress_id
                    # (In a real Clos, routing is more involved; here each middle
                    #  switch connects to all egress switches, so we use middle
                    #  switch index == egress switch index for simplicity.)
                    sub_flit = flit.copy_for_dest(egress_mask)
                    output[egress_id].append(sub_flit)

        return output


# ---------------------------------------------------------------------------
# Middle Switch  (8 ingress inputs -> 8 egress outputs)
# ---------------------------------------------------------------------------
class MiddleSwitch:
    """
    Collects flits from all ingress switches (one per ingress).
    Forwards each flit to the egress switch indicated by its index.
    (middle switch m routes to egress switch m.)
    """
    def __init__(self, switch_id: int):
        self.switch_id = switch_id   # also the target egress switch id

    def process(self, flits: List[Optional[Flit]]) -> List[Flit]:
        """
        Input : flits[i] = flit arriving from ingress switch i (or None).
        Output: list of flits to pass to the associated egress switch.
        """
        return [f for f in flits if f is not None]


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

    send(flits_from_banks) -> deliveries
      flits_from_banks : dict { bank_id -> Flit }
      deliveries       : dict { thread_id -> list of (data, error) }
    """

    def __init__(self):
        self.ingress = [IngressSwitch(i) for i in range(NUM_INGRESS)]
        self.middle  = [MiddleSwitch(i)  for i in range(NUM_MIDDLE)]
        self.egress  = [EgressSwitch(i)  for i in range(NUM_EGRESS)]

    def send(self, flits_from_banks: Dict[int, Flit]) -> Dict[int, List[Tuple[int, int]]]:
        """
        Route a batch of flits (one dict entry per bank) through the network.
        Returns deliveries: thread_id -> list of (data, error) tuples.
        (A thread may receive more than one flit in a batch.)
        """
        # --- Stage 1: Ingress ---
        # middle_inputs[m] = list of flits arriving at middle switch m
        middle_inputs: List[List[Optional[Flit]]] = [[] for _ in range(NUM_MIDDLE)]

        for ingress_id, ing_sw in enumerate(self.ingress):
            # Gather flits from the 4 banks feeding this ingress switch
            bank_flits: List[Optional[Flit]] = []
            for local_bank in range(BANKS_PER_INGRESS):
                bank_id = ingress_id * BANKS_PER_INGRESS + local_bank
                bank_flits.append(flits_from_banks.get(bank_id))

            ing_output = ing_sw.process(bank_flits)   # ing_output[m] = flits for middle m
            for m in range(NUM_MIDDLE):
                # Each middle switch gets one "slot" per ingress; we may have
                # multiple flits if the ingress has multiple active banks.
                middle_inputs[m].extend(ing_output[m])

        # --- Stage 2: Middle ---
        # egress_inputs[e] = list of flits arriving at egress switch e
        egress_inputs: List[List[Flit]] = [[] for _ in range(NUM_EGRESS)]

        for m, mid_sw in enumerate(self.middle):
            mid_output = mid_sw.process(middle_inputs[m])
            egress_inputs[m].extend(mid_output)   # middle m -> egress m

        # --- Stage 3: Egress ---
        deliveries: Dict[int, List[Tuple[int, int]]] = {}

        for e, eg_sw in enumerate(self.egress):
            eg_deliveries = eg_sw.process(egress_inputs[e])
            for tid, rx in eg_deliveries.items():
                deliveries.setdefault(tid, []).append(rx)

        return deliveries


# ---------------------------------------------------------------------------
# SRAM Bank (simplified model)
# ---------------------------------------------------------------------------
@dataclass
class SRAMBank:
    """Simple SRAM bank with address-mapped storage and MSHR."""
    bank_id : int
    memory  : Dict[int, int] = field(default_factory=dict)
    mshr    : MSHRTable = field(init=False)
    valid_range: Tuple[int, int] = (0, 0xFFFF)   # inclusive address range

    def __post_init__(self):
        self.mshr = MSHRTable(self.bank_id)

    def write(self, address: int, data: int) -> None:
        self.memory[address] = data & 0xFFFF_FFFF

    def read_request(self, address: int,
                     thread_id: int) -> Tuple[Optional[Flit], bool]:
        """
        Simulate a read request from thread_id to address.

        Returns (flit_or_None, was_mshr_merged).
          - If address is valid and not in MSHR: allocate MSHR entry,
            immediately 'complete' it (no real latency in this sim) -> Flit.
          - If address is valid and already in MSHR: merge thread -> no new Flit yet.
          - If address is unmapped: return error Flit immediately.
        """
        # Address range check
        lo, hi = self.valid_range
        if not (lo <= address <= hi):
            flit = Flit.make(dest_mask=(1 << thread_id),
                             data=0,
                             error=ERR_UNMAPPED)
            return flit, False

        eid, merged = self.mshr.request(address, thread_id)
        if merged:
            # Another thread already requested this; MSHR merged them.
            # No new flit until the original request completes.
            return None, True

        # Perform the read (instant in this functional sim)
        data  = self.memory.get(address, 0)
        flit  = self.mshr.complete(eid, data, ERR_GOOD)
        self.mshr.free(eid)
        return flit, False

    def complete_mshr(self, address: int, data: int,
                      error: int = ERR_GOOD) -> Optional[Flit]:
        """
        Explicitly complete an MSHR entry (e.g. after a merged request
        finishes).  Returns the multicast Flit covering all merged threads.
        """
        eid = self.mshr.lookup(address)
        if eid is None:
            return None
        flit = self.mshr.complete(eid, data, error)
        self.mshr.free(eid)
        return flit


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
    flit, _ = banks[0].read_request(0x0010, thread_id=7)
    assert flit is not None

    deliveries = route_flits(net, {0: flit})
    assert_delivered(deliveries, 7, 0xDEADBEEF, test_name="Test1")

    # No other threads should receive anything
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
        flit, _ = banks[bank_id].read_request(addr, thread_id=tid)
        assert flit is not None
        flits[bank_id] = flit

    deliveries = route_flits(net, flits)

    for bank_id, addr, data, tid in scenarios:
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
    banks    = [SRAMBank(i) for i in range(NUM_BANKS)]
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
    net   = ClosNetwork()
    banks = [SRAMBank(i, valid_range=(0x0000, 0x00FF)) for i in range(NUM_BANKS)]

    # Address 0x1000 is outside valid_range -> ERR_UNMAPPED
    flit, _ = banks[2].read_request(0x1000, thread_id=15)
    assert flit is not None, "Expected an error flit"
    assert flit.error == ERR_UNMAPPED

    deliveries = route_flits(net, {2: flit})
    assert_delivered(deliveries, 15, 0, ERR_UNMAPPED, test_name="Test5")
    print("  PASSED")


def test_6_mshr_merge():
    """Test 6: MSHR merge – two threads request same address, single multicast response."""
    print("Test 6: MSHR merge (threads 3 and 5 both request bank 0 address 0x0020)")
    net   = ClosNetwork()
    banks = [SRAMBank(i) for i in range(NUM_BANKS)]

    data_val = 0xCAFEBABE
    banks[0].write(0x0020, data_val)

    # Thread 3 requests first -> allocates MSHR entry, gets a flit back
    flit_t3, merged_t3 = banks[0].read_request(0x0020, thread_id=3)
    assert not merged_t3, "First request should not be merged"
    assert flit_t3 is not None

    # Thread 5 requests same address -> MSHR is freed after first complete above.
    # To properly test merging we need to hold the entry open.
    # Re-implement: allocate manually, merge second, then complete once.

    bank = banks[0]
    bank.mshr = MSHRTable(0)                       # fresh MSHR
    eid1, merged1 = bank.mshr.request(0x0020, thread_id=3)
    assert not merged1

    eid2, merged2 = bank.mshr.request(0x0020, thread_id=5)
    assert merged2, "Second request to same address should merge"
    assert eid2 == eid1, "Merged entry should share the same entry id"

    # Now complete: single response, dest_mask covers both threads
    merged_flit = bank.mshr.complete(eid1, data_val, ERR_GOOD)
    bank.mshr.free(eid1)

    assert merged_flit is not None
    assert (merged_flit.dest_mask >> 3) & 1, "Thread 3 must be in dest_mask"
    assert (merged_flit.dest_mask >> 5) & 1, "Thread 5 must be in dest_mask"

    deliveries = route_flits(net, {0: merged_flit})
    assert_delivered(deliveries, 3, data_val, test_name="Test6-T3")
    assert_delivered(deliveries, 5, data_val, test_name="Test6-T5")

    # Only threads 3 and 5 should receive it
    stray = {t: v for t, v in deliveries.items() if t not in (3, 5)}
    assert not stray, f"Stray deliveries: {stray}"
    print("  PASSED")


def test_7_throughput():
    """Test 7: All 32 banks send simultaneously, all 32 flits delivered."""
    print("Test 7: Throughput – all 32 banks send simultaneously")
    net   = ClosNetwork()
    banks = [SRAMBank(i) for i in range(NUM_BANKS)]

    # Each bank sends to the thread with id = bank_id (one-to-one mapping)
    expected: Dict[int, int] = {}
    flits:    Dict[int, Flit] = {}

    for bank_id in range(NUM_BANKS):
        thread_id = bank_id                      # thread i served by bank i
        data_val  = 0xA0000000 | bank_id
        banks[bank_id].write(bank_id * 4, data_val)
        flit, _ = banks[bank_id].read_request(bank_id * 4, thread_id=thread_id)
        assert flit is not None
        flits[bank_id]        = flit
        expected[thread_id]   = data_val

    deliveries = route_flits(net, flits)

    for tid in range(NUM_THREADS):
        assert_delivered(deliveries, tid, expected[tid], test_name="Test7")

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
    test_6_mshr_merge()
    print()
    test_7_throughput()
    print()
    print("=" * 60)
    print("All tests PASSED.")
    print("=" * 60)


if __name__ == "__main__":
    main()
