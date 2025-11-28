from dataclasses import dataclass, field
from latch_forward_stage import LatchIF, ForwardingIF, Stage, Instruction
from regfile import RegisterFile
from typing import Any, Optional, Callable, List, Deque, Tuple
from collections import deque

class IssueStage(Stage):
    # configuration
    # num_iBuffer = 16
    # num_entries = 4
    # regfile: RegisterFile
    # fust_latency_cycles: int = 1

    # def __init__(
    #     self,
    #     name: str = "Issue",
    #     evenRF_fn: Optional[Callable[[int, Optional[int], str], Any]] = None,
    #     oddRF_fn: Optional[Callable[[int, Optional[int], str], Any]] = None,
    #     fust_latency_cycles: int = 1,
    # ):
    
    # regfile: RegisterFile = register_file

    # def __post_init__(self):
    # def __init__(self, register_file: RegisterFile, fust_latency_cycles: int = 1, stage_name: str = "Issue"):
    def __init__(self, fust_latency_cycles: int = 1, stage_name: str = "Issue"):
        super().__init__(name=stage_name)
        """
        evenRF_fn/oddRF_fn: optional callables with signature (RS, RD, 'R'/'W') -> value
                            If not given, lightweight internal stub RFs are used (read-only for now).
        fust_latency_cycles: how long a FUST slot stays busy after a dispatch (>=1).
        """
        # super().__init__(name=name)
        self.fust_latency_cycles: int = max(1, int(fust_latency_cycles))

        self.num_iBuffer = 16
        self.num_entries = 4
        # --- iBuffer: 16 warpGroups × 4-deep FIFO each ---
        self.iBuffer: List[List[Optional[Instruction]]] = [
            [None for _ in range(self.num_entries)] for _ in range(self.num_iBuffer)
        ]
        self.iBufferFill: List[int] = [0 for _ in range(self.num_iBuffer)]
        self.iBufferHead: List[int] = [0 for _ in range(self.num_iBuffer)]
        self.curr_wg: int = 0  # RR pointer for iBuffer scans

        # --- Per-bank (EVEN/ODD) staging for operand reads ---
        self.staged_even: Optional[Instruction] = None
        self.staged_odd: Optional[Instruction] = None
        self.even_read_progress: int = 0  # 0 -> need rs1, 1 -> need rs2, 2 -> done
        self.odd_read_progress: int = 0

        # --- Queues of instructions that finished both RF reads and can be dispatched ---
        self.ready_even: Deque[Instruction] = deque()
        self.ready_odd: Deque[Instruction] = deque()

        # --- FUST: per-warpGroup availability (simple model) ---
        # countdown == 0 means free; >0 means busy that many more cycles.
        self.fust_busy_countdown: List[int] = [0 for _ in range(self.num_iBuffer)]
        # self.fust_latency_cycles = max(1, int(fust_latency_cycles))
        self.fust_latency_cycles = max(1, int(self.fust_latency_cycles))

        # --- Register files (banks) ---
        # self._evenRF_fn = evenRF_fn
        # self._oddRF_fn = oddRF_fn
        # # Simple internal stubs if nothing provided:
        # self._even_regs = {}
        # self._odd_regs = {}

    # ---------------------------
    # Public entry point (1→4)
    # ---------------------------
    def compute(self, input_data: Any) -> List[Instruction]:
        """
        Executes the Issue stage in this exact order every cycle:
          1) Try to dispatch ready instructions via FUST (start from EVEN).
          2) Perform register-file reads for the staged EVEN/ODD instructions
             with the oscillating pattern (one read per bank per cycle).
          3) Select from iBuffer to stage next EVEN/ODD instruction(s) for future reads.
          4) Accept the newly decoded instruction into the iBuffer.

        Returns:
            List[Instruction]: The instructions that were actually dispatched this cycle
                               (order: EVEN-first if both dispatched).
        """
        inst_in: Optional[Instruction] = None
        # if input_data is not None and getattr(input_data, "instruction", None) is not None:
        if input_data is not None:
            inst_in = input_data

        # Housekeeping for FUST (advance time)
        self._tick_fust()

        # 1) Dispatch through FUST (EVEN priority)
        dispatched = self._dispatch_ready_via_fust()

        # 2) RF reads for staged instructions with the requested rhythm
        self._issue_register_file_reads()

        # 3) Stage next instructions (from iBuffer) for RF reads in upcoming cycles
        self._stage_from_ibuffer_for_next_cycle()

        # 4) Finally, fill iBuffer with the just-decoded instruction (if present)
        if inst_in is not None:
            self.fill_ibuffer(inst_in)

        return dispatched

    # --------------------------------
    # (1) FUST dispatch (EVEN first)
    # --------------------------------
    def _dispatch_ready_via_fust(self) -> List[Instruction]:
        """
        Try to dispatch up to two instructions (EVEN then ODD) if their warpGroup's
        FUST slot is free. An instruction is ready if both operands were read.
        """
        dispatched: List[Instruction] = []

        # Helper: attempt a single dispatch from a queue
        def try_dispatch_one(q: Deque[Instruction]) -> Optional[Instruction]:
            if not q:
                return None
            inst = q[0]  # peek
            wg = inst.warp_group_id
            if self.fust_busy_countdown[wg] == 0:
                # Reserve FUST for this warpGroup
                self.fust_busy_countdown[wg] = self.fust_latency_cycles
                q.popleft()
                return inst
            return None

        # EVEN gets priority
        first = try_dispatch_one(self.ready_even)
        if first is not None:
            dispatched.append(first)

        # Then ODD
        second = try_dispatch_one(self.ready_odd)
        if second is not None:
            dispatched.append(second)

        return dispatched

    # -------------------------------------------------------
    # (2) Issue reads to RFs with the described oscillation
    # -------------------------------------------------------
    def _issue_register_file_reads(self) -> None:
        """
        Each bank (EVEN/ODD) performs at most one read per cycle, in order:
          - On first involvement of a staged instruction: read rs1 -> rdat1
          - Next cycle for the same staged instruction: read rs2 -> rdat2, then mark ready
        Because each bank is independent, once both EVEN and ODD have staged work,
        the steady-state pattern emerges naturally:
            cycle 0: EVEN rs1
            cycle 1: EVEN rs2 + ODD rs1
            cycle 2: EVEN(next) rs1 + ODD rs2
            cycle 3: EVEN(next) rs2 + ODD(next) rs1
            ...
        This matches the "four possibilities" oscillation without over-constraining timing.
        """
        # EVEN bank one read
        if self.staged_even is not None and self.even_read_progress < 2:
            if self.even_read_progress == 0:
                # val = self.evenRF(self.staged_even.rs1, None, 'R')
                val = regfile.read_warp_gran(self.staged_even.warp_id, self.staged_even.rs1)
                self.staged_even.rdat1 = val
                self.even_read_progress = 1
            elif self.even_read_progress == 1:
                # val = self.evenRF(self.staged_even.rs2, None, 'R')
                val = regfile.read_warp_gran(self.staged_even.warp_id, self.staged_even.rs2)
                self.staged_even.rdat2 = val
                self.even_read_progress = 2
                # Move to ready queue after 2nd operand
                self._push_ready(self.staged_even)
                self.staged_even = None
                self.even_read_progress = 0

        # ODD bank one read
        if self.staged_odd is not None and self.odd_read_progress < 2:
            if self.odd_read_progress == 0:
                # val = self.oddRF(self.staged_odd.rs1, None, 'R')
                val = regfile.read_warp_gran(self.staged_odd.warp_id, self.staged_odd.rs1)
                self.staged_odd.rdat1 = val
                self.odd_read_progress = 1
            elif self.odd_read_progress == 1:
                # val = self.oddRF(self.staged_odd.rs2, None, 'R')
                val = regfile.read_warp_gran(self.staged_odd.warp_id, self.staged_odd.rs2)
                self.staged_odd.rdat2 = val
                self.odd_read_progress = 2
                # Move to ready queue after 2nd operand
                self._push_ready(self.staged_odd)
                self.staged_odd = None
                self.odd_read_progress = 0

    def _push_ready(self, inst: "Instruction") -> None:
        """Place a fully-read instruction into the EVEN/ODD ready queue by warp parity."""
        if (inst.warp_id % 2) == 0:
            self.ready_even.append(inst)
        else:
            self.ready_odd.append(inst)

    # -----------------------------------------------------------
    # (3) Select from iBuffer to stage next EVEN/ODD instructions
    # -----------------------------------------------------------
    def _stage_from_ibuffer_for_next_cycle(self) -> None:
        """
        Pull head instructions from the iBuffer (round-robin) to fill empty
        staging slots: EVEN first (if empty), then ODD (if empty).
        """
        # Fill EVEN staging slot, if available
        if self.staged_even is None:
            inst_even = self._pop_from_ibuffer_matching(lambda inst: (inst.warp_id % 2) == 0)
            # inst_even = self._pop_from_ibuffer_matching()
            if inst_even is not None:
                self.staged_even = inst_even
                self.even_read_progress = 0

        # Fill ODD staging slot, if available
        if self.staged_odd is None:
            inst_odd = self._pop_from_ibuffer_matching(lambda inst: (inst.warp_id % 2) == 1)
            # inst_odd = self._pop_from_ibuffer_matching()
            if inst_odd is not None:
                self.staged_odd = inst_odd
                self.odd_read_progress = 0

    def _pop_from_ibuffer_matching(self, pred) -> Optional["Instruction"]:
        """
        Round-robin scan of warpGroups, return and remove the head instruction
        only if it satisfies 'pred'. Advances RR pointer on a pop.
        """
        for step in range(self.num_iBuffer):
            wg = (self.curr_wg + step) % self.num_iBuffer
            if self.iBufferFill[wg] == 0:
                continue
            head_idx = self.iBufferHead[wg]
            inst = self.iBuffer[wg][head_idx]
            if inst is None:
                continue
            if pred(inst):
                # Pop from FIFO
                self.iBuffer[wg][head_idx] = None
                self.iBufferHead[wg] = (head_idx + 1) % self.num_entries
                self.iBufferFill[wg] -= 1
                # Advance RR starting point
                self.curr_wg = (wg + 1) % self.num_iBuffer
                return inst
        return None

    # ------------------------
    # (4) Fill the iBuffer
    # ------------------------
    def fill_ibuffer(self, inst: "Instruction") -> None:
        given = inst.warp_group_id
        if self.iBufferFill[given] < self.num_entries:
            head = self.iBufferHead[given]
            tail = (head + self.iBufferFill[given]) % self.num_entries
            self.iBuffer[given][tail] = inst
            self.iBufferFill[given] += 1
        # else: upstream should stall/retry

    # -----------------------------------------
    # Original helper kept for compatibility
    # -----------------------------------------
    def select_from_ibuffer(self, curr_wg: int) -> Tuple[Optional["Instruction"], int]:
        """
        (Kept for API compatibility, unused by the new pipeline.)
        Try curr_wg first, then round-robin across all groups.
        Return (instruction, wg). Instruction is the head entry; not removed.
        """
        for step in range(self.num_iBuffer):
            wg = (curr_wg + step) % self.num_iBuffer
            if self.iBufferFill[wg] > 0:
                head_idx = self.iBufferHead[wg]
                return self.iBuffer[wg][head_idx], wg
        return None, curr_wg

    # --------------------------
    # Operand collection (noop)
    # --------------------------
    def collect_operand(self, inst: "Instruction") -> None:
        """Placeholder — operands are latched directly by RF reads here."""
        return

    # --------------------------
    # Register file interfaces
    # --------------------------
    # def evenRF(self, rs: int, rd: Optional[int], op: str) -> Any:
    #     if self._evenRF_fn is not None:
    #         return self._evenRF_fn(rs, rd, op)
    #     # stub: only 'R' supported; returns 0 if unseen
    #     if op.upper() == 'R':
    #         return self._even_regs.get(rs, 0)
    #     raise NotImplementedError("Stub evenRF supports only reads (R) without external RF.")

    # def oddRF(self, rs: int, rd: Optional[int], op: str) -> Any:
    #     if self._oddRF_fn is not None:
    #         return self._oddRF_fn(rs, rd, op)
    #     # stub: only 'R' supported; returns 0 if unseen
    #     if op.upper() == 'R':
    #         return self._odd_regs.get(rs, 0)
    #     raise NotImplementedError("Stub oddRF supports only reads (R) without external RF.")

    # --------------------------
    # FUST time advancement
    # --------------------------
    def _tick_fust(self) -> None:
        """
        Decrement busy countdowns once per cycle. Zero means 'free to dispatch'.
        """
        for i in range(self.num_iBuffer):
            if self.fust_busy_countdown[i] > 0:
                self.fust_busy_countdown[i] -= 1

### TESTING ###

# if __name__ == "__main__":
    # simple register file for testing
    # regfile = RegisterFile(
    #     banks = 2,
    #     warps = 4,
    #     regs_per_warp = 4,
    #     threads_per_warp = 2
    # )

regfile = RegisterFile(
    banks = 2,
    warps = 4,
    regs_per_warp = 4,
    threads_per_warp = 2
)

issue_stage = IssueStage(
    fust_latency_cycles = 1,
    stage_name = "IssueStage"
)

regfile.write_warp_gran(0, 0, [2, 3])
regfile.write_warp_gran(0, 1, [4, 5])
regfile.write_warp_gran(0, 2, [6, 7])
regfile.write_warp_gran(0, 3, [8, 9])

regfile.write_warp_gran(1, 0, [42, 43])
regfile.write_warp_gran(1, 1, [44, 45])
regfile.write_warp_gran(1, 2, [46, 47])
regfile.write_warp_gran(1, 3, [48, 49])

regfile.write_warp_gran(2, 0, [70, 71])
regfile.write_warp_gran(2, 1, [72, 73])
regfile.write_warp_gran(2, 2, [74, 75])
regfile.write_warp_gran(2, 3, [76, 77])

regfile.write_warp_gran(3, 0, [900, 901])
regfile.write_warp_gran(3, 1, [902, 903])
regfile.write_warp_gran(3, 2, [904, 905])
regfile.write_warp_gran(3, 3, [906, 907])

instr0 = Instruction(
    pc = 0x0,
    intended_FU = "ADD",
    warp_id = 0,
    warp_group_id = 0,
    rs1 = 2,
    rs2 = 3,
    rd = 1,
    opcode = "0000000",
    rdat1 = 0,
    rdat2 = 0,
    wdat = 0
)

instr1 = Instruction(
    pc = 0x0,
    intended_FU = "ADD",
    warp_id = 1,
    warp_group_id = 0,
    rs1 = 2,
    rs2 = 3,
    rd = 1,
    opcode = "0000000",
    rdat1 = 0,
    rdat2 = 0,
    wdat = 0
)

instr2 = Instruction(
    pc = 0x4,
    intended_FU = "MUL",
    warp_id = 2,
    warp_group_id = 1,
    rs1 = 0,
    rs2 = 1,
    rd = 2,
    opcode = "0000010",
    rdat1 = 0,
    rdat2 = 0,
    wdat = 0
)

instr3 = Instruction(
    pc = 0x4,
    intended_FU = "MUL",
    warp_id = 3,
    warp_group_id = 1,
    rs1 = 0,
    rs2 = 1,
    rd = 2,
    opcode = "0000010",
    rdat1 = 0,
    rdat2 = 0,
    wdat = 0
)

instructions = [instr0, instr1, instr2, instr3]

for cycle in range(10):
    if cycle in range(4):
        issue_stage.compute(instructions[cycle])
    else:
        issue_stage.compute(None)

print(instr0.rdat1, instr0.rdat2)
print(instr1.rdat1, instr1.rdat2)
print(instr2.rdat1, instr2.rdat2)
print(instr3.rdat1, instr3.rdat2)
