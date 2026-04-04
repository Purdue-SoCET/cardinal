from pathlib import Path
import sys
from collections import deque
from bitstring import Bits

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.base_class import Stage, LatchIF, ForwardingIF, simple_instruction
from src.simple_isa import R_Op, I_Op


THREADS_PER_WARP = 8
LOAD_OP = getattr(I_Op, "LD", None) or getattr(I_Op, "LW")


# ============================================================
# Helpers
# ============================================================

def regbits(n: int) -> Bits:
    return Bits(uint=n, length=6)


def predbits(n: int) -> Bits:
    return Bits(uint=n, length=5)


def wordbits(n: int) -> Bits:
    return Bits(int=n, length=32)


def immbits(n: int) -> Bits:
    return Bits(int=n, length=32)


def reg_num(x):
    return None if x is None else x.uint


def pred_num(x):
    return 0 if x is None else x.uint


def bits_to_int(x):
    if x is None:
        return 0
    if isinstance(x, Bits):
        return x.int
    return int(x)


def writes_rd(instr: simple_instruction) -> bool:
    return instr.opcode in (R_Op.ADD, R_Op.SUB, R_Op.MUL, LOAD_OP)


def reads_rs1(instr: simple_instruction) -> bool:
    return instr.opcode in (R_Op.ADD, R_Op.SUB, R_Op.MUL, LOAD_OP)


def reads_rs2(instr: simple_instruction) -> bool:
    return instr.opcode in (R_Op.ADD, R_Op.SUB, R_Op.MUL)


def active_lanes(mask):
    return [i for i, bit in enumerate(mask) if bit]


def instr_str(instr: simple_instruction) -> str:
    if instr is None:
        return "None"
    return (
        f"{instr.opcode.name}"
        f".P{pred_num(instr.pred_reg)}"
        f"(pc={bits_to_int(instr.pc)}, "
        f"rd={reg_num(instr.rd)}, rs1={reg_num(instr.rs1)}, "
        f"rs2={reg_num(instr.rs2)}, imm={bits_to_int(instr.imm)})"
    )


# ============================================================
# Builders
# ============================================================

def make_r(op, pc, rd, rs1, rs2, pred):
    return simple_instruction(
        pc=wordbits(pc),
        warp_id=0,
        opcode=op,
        rs1=regbits(rs1),
        rs2=regbits(rs2),
        rd=regbits(rd),
        pred_reg=predbits(pred),
    )


def make_i(op, pc, rd, rs1, imm, pred):
    return simple_instruction(
        pc=wordbits(pc),
        warp_id=0,
        opcode=op,
        rs1=regbits(rs1),
        rd=regbits(rd),
        imm=immbits(imm),
        pred_reg=predbits(pred),
    )


# ============================================================
# Predicate file
# ============================================================

class PredicateFile:
    def __init__(self, num_preds=4, threads_per_warp=THREADS_PER_WARP):
        self.num_preds = num_preds
        self.threads_per_warp = threads_per_warp
        self.regs = {p: [False] * threads_per_warp for p in range(num_preds)}

    def write(self, pred_idx: int, mask):
        self.regs[pred_idx] = list(mask)

    def read(self, pred_idx: int):
        return list(self.regs[pred_idx])

    def dump(self):
        print("Predicate file:")
        for p in sorted(self.regs):
            print(f"  P{p}: {self.regs[p]}")


# ============================================================
# Stages
# ============================================================

class IssueStage(Stage):
    def __init__(self, name, ahead_latch, program, regfile, reg_busy, predfile):
        super().__init__(name=name, behind_latch=None, ahead_latch=ahead_latch)
        self.program = program
        self.regfile = regfile
        self.reg_busy = reg_busy
        self.predfile = predfile

    def _busy_sources(self, instr):
        busy = []

        if reads_rs1(instr):
            r1 = reg_num(instr.rs1)
            if r1 is not None and self.reg_busy.get(r1, False):
                busy.append(r1)

        if reads_rs2(instr):
            r2 = reg_num(instr.rs2)
            if r2 is not None and self.reg_busy.get(r2, False):
                busy.append(r2)

        return busy

    def compute(self, cycle):
        if not self.program:
            print(f"{self.name}: idle (program empty)")
            return

        if not self.ahead_latch.ready_for_push():
            print(f"{self.name}: stall (ISSUE_EX not ready)")
            return

        instr = self.program[0]
        busy = self._busy_sources(instr)
        if busy:
            print(f"{self.name}: stall RAW hazard on regs {busy} for {instr_str(instr)}")
            return

        instr = self.program.popleft()
        instr.mark_stage_enter("ISSUE", cycle)

        instr.pred_mask = self.predfile.read(pred_num(instr.pred_reg))

        if reads_rs1(instr):
            instr.rdat1 = list(self.regfile[reg_num(instr.rs1)])

        if reads_rs2(instr):
            instr.rdat2 = list(self.regfile[reg_num(instr.rs2)])

        if writes_rd(instr):
            self.reg_busy[reg_num(instr.rd)] = True

        ok = self.ahead_latch.push(instr)
        if not ok:
            raise RuntimeError("Issue expected ahead latch to be ready")

        instr.mark_stage_exit("ISSUE", cycle)
        print(
            f"{self.name}: issued {instr_str(instr)} "
            f"active_lanes={active_lanes(instr.pred_mask)}"
        )


class ExecuteStage(Stage):
    def __init__(self, name, behind_latch, ahead_latch):
        super().__init__(name=name, behind_latch=behind_latch, ahead_latch=ahead_latch)
        self.holding = None

    def compute(self, cycle):
        if self.holding is None:
            self.holding = self.behind_latch.pop()
            if self.holding is not None:
                self.holding.mark_stage_enter("EXECUTE", cycle)

        instr = self.holding
        if instr is None:
            print(f"{self.name}: idle")
            return

        if instr.opcode == R_Op.ADD:
            instr.wdat = [a + b for a, b in zip(instr.rdat1, instr.rdat2)]
            instr.intended_FU = "ALU"

        elif instr.opcode == R_Op.SUB:
            instr.wdat = [a - b for a, b in zip(instr.rdat1, instr.rdat2)]
            instr.intended_FU = "ALU"

        elif instr.opcode == R_Op.MUL:
            instr.wdat = [a * b for a, b in zip(instr.rdat1, instr.rdat2)]
            instr.intended_FU = "ALU"

        elif instr.opcode == LOAD_OP:
            imm = bits_to_int(instr.imm)
            instr.mem_addr = [base + imm for base in instr.rdat1]
            instr.intended_FU = "MEM"

        else:
            raise ValueError(f"Unsupported opcode {instr.opcode}")

        ok = self.ahead_latch.push(instr)
        if not ok:
            print(f"{self.name}: stall (EX_MEM blocked) holding {instr_str(instr)}")
            return

        instr.mark_stage_exit("EXECUTE", cycle)
        print(f"{self.name}: forwarded {instr_str(instr)}")
        self.holding = None


class MemoryStage(Stage):
    def __init__(self, name, behind_latch, ahead_latch, memory, latency=3):
        super().__init__(name=name, behind_latch=behind_latch, ahead_latch=ahead_latch)
        self.memory = memory
        self.latency = latency
        self.current = None
        self.remaining = 0

    def _set_backpressure(self, flag: bool):
        if self.behind_latch.forward_if is not None:
            self.behind_latch.forward_if.set_wait(flag)

    def compute(self, cycle):
        if self.current is None:
            self.current = self.behind_latch.pop()
            if self.current is not None:
                self.current.mark_stage_enter("MEM", cycle)
                if self.current.opcode == LOAD_OP:
                    self.remaining = self.latency - 1
                else:
                    self.remaining = 0

        if self.current is None:
            self._set_backpressure(False)
            print(f"{self.name}: idle")
            return

        self._set_backpressure(True)

        if self.remaining > 0:
            print(
                f"{self.name}: busy with {instr_str(self.current)} "
                f"(remaining={self.remaining})"
            )
            self.remaining -= 1
            return

        if not self.ahead_latch.ready_for_push():
            print(f"{self.name}: stall (MEM_WB blocked) for {instr_str(self.current)}")
            return

        instr = self.current

        if instr.opcode == LOAD_OP:
            loaded = [self.memory.get(addr, 0) for addr in instr.mem_addr]
            instr.load_data = loaded
            instr.wdat = loaded
            print(f"{self.name}: loaded values {loaded} from addrs {instr.mem_addr}")
        else:
            print(f"{self.name}: pass-through {instr_str(instr)}")

        ok = self.ahead_latch.push(instr)
        if not ok:
            raise RuntimeError("Memory expected MEM_WB latch to be ready")

        instr.mark_stage_exit("MEM", cycle)
        self.current = None
        self._set_backpressure(False)


class WritebackStage(Stage):
    def __init__(self, name, behind_latch, regfile, reg_busy):
        super().__init__(name=name, behind_latch=behind_latch, ahead_latch=None)
        self.regfile = regfile
        self.reg_busy = reg_busy
        self.completed = []

    def compute(self, cycle):
        instr = self.behind_latch.pop()
        if instr is None:
            print(f"{self.name}: idle")
            return

        instr.mark_stage_enter("WB", cycle)

        if writes_rd(instr):
            rd = reg_num(instr.rd)
            before = list(self.regfile[rd])

            if not instr.pred_mask:
                instr.pred_mask = [True] * THREADS_PER_WARP

            instr.lane_wb_mask = list(instr.pred_mask)

            for lane in range(THREADS_PER_WARP):
                if instr.pred_mask[lane]:
                    self.regfile[rd][lane] = instr.wdat[lane]

            after = list(self.regfile[rd])
            self.reg_busy[rd] = False

            print(f"{self.name}: writeback for {instr_str(instr)}")
            print(f"  active lanes : {active_lanes(instr.pred_mask)}")
            print(f"  before R{rd} : {before}")
            print(f"  result wdat  : {instr.wdat}")
            print(f"  after  R{rd} : {after}")

        instr.mark_stage_exit("WB", cycle)
        instr.mark_writeback(cycle)
        self.completed.append(instr)


# ============================================================
# Debug dump
# ============================================================

def dump_latch(name, latch):
    if latch.valid:
        print(f"  {name}: {instr_str(latch.payload)}")
    else:
        print(f"  {name}: empty")


def dump_reg(regfile, reg):
    print(f"  R{reg}: {regfile[reg]}")


def dump_state(cycle, issue_ex, ex_mem, mem_wb, regfile, reg_busy):
    print(f"\n================ CYCLE {cycle} ================")
    dump_latch("ISSUE_EX", issue_ex)
    dump_latch("EX_MEM", ex_mem)
    dump_latch("MEM_WB", mem_wb)

    busy_regs = sorted([r for r, v in reg_busy.items() if v])
    print(f"  Busy regs: {busy_regs}")
    for r in [1, 2, 3, 4, 10, 11, 12, 13, 20]:
        dump_reg(regfile, r)


# ============================================================
# Main demo
# ============================================================

def run_predicated_demo():
    # Vector register file: reg -> list of per-thread values
    regfile = {i: [0] * THREADS_PER_WARP for i in range(32)}
    reg_busy = {i: False for i in range(32)}

    # Predicate file
    predfile = PredicateFile(num_preds=4, threads_per_warp=THREADS_PER_WARP)

    # P0 = all lanes active
    predfile.write(0, [True] * THREADS_PER_WARP)

    # P1 = even lanes only
    predfile.write(1, [lane % 2 == 0 for lane in range(THREADS_PER_WARP)])

    # P2 = upper half only
    predfile.write(2, [lane >= 4 for lane in range(THREADS_PER_WARP)])

    # Initial vector register contents
    regfile[10] = [0, 1, 2, 3, 4, 5, 6, 7]
    regfile[11] = [10] * THREADS_PER_WARP
    regfile[12] = [100] * THREADS_PER_WARP
    regfile[13] = [1] * THREADS_PER_WARP

    # Per-thread base addresses for load
    regfile[20] = [100, 104, 108, 112, 116, 120, 124, 128]

    # Memory contents
    memory = {
        100: 50,
        104: 51,
        108: 52,
        112: 53,
        116: 54,
        120: 55,
        124: 56,
        128: 57,
    }

    # Program:
    #   ADD.P0 R1 = R10 + R11       -> all lanes write
    #   ADD.P1 R2 = R10 + R12       -> only even lanes write
    #   LD.P2  R3 = MEM[R20 + 0]    -> only upper-half lanes write, memory stalls
    #   ADD.P2 R4 = R3 + R13        -> waits on R3, then only upper-half lanes write
    program = deque([
        make_r(R_Op.ADD, pc=0,  rd=1, rs1=10, rs2=11, pred=0),
        make_r(R_Op.ADD, pc=4,  rd=2, rs1=10, rs2=12, pred=1),
        make_i(LOAD_OP, pc=8,   rd=3, rs1=20, imm=0, pred=2),
        make_r(R_Op.ADD, pc=12, rd=4, rs1=3,  rs2=13, pred=2),
    ])

    # Latches
    issue_ex_latch = LatchIF(name="ISSUE_EX")
    ex_mem_backpressure = ForwardingIF(name="EX_MEM_backpressure")
    ex_mem_latch = LatchIF(name="EX_MEM", forward_if=ex_mem_backpressure)
    mem_wb_latch = LatchIF(name="MEM_WB")

    # Stages
    issue = IssueStage(
        name="ISSUE",
        ahead_latch=issue_ex_latch,
        program=program,
        regfile=regfile,
        reg_busy=reg_busy,
        predfile=predfile,
    )

    ex = ExecuteStage(
        name="EXECUTE",
        behind_latch=issue_ex_latch,
        ahead_latch=ex_mem_latch,
    )

    mem = MemoryStage(
        name="MEM",
        behind_latch=ex_mem_latch,
        ahead_latch=mem_wb_latch,
        memory=memory,
        latency=3,
    )

    wb = WritebackStage(
        name="WB",
        behind_latch=mem_wb_latch,
        regfile=regfile,
        reg_busy=reg_busy,
    )

    predfile.dump()

    max_cycles = 20
    for cycle in range(max_cycles):
        dump_state(cycle, issue_ex_latch, ex_mem_latch, mem_wb_latch, regfile, reg_busy)

        # downstream -> upstream
        wb.compute(cycle)
        mem.compute(cycle)
        ex.compute(cycle)
        issue.compute(cycle)

        done = (
            not program
            and not issue_ex_latch.valid
            and not ex_mem_latch.valid
            and not mem_wb_latch.valid
            and ex.holding is None
            and mem.current is None
        )
        if done:
            print(f"\nPipeline drained at cycle {cycle}.")
            break

    print("\n================ FINAL STATE ================")
    print(f"R1 expected all lanes written:      {regfile[1]}")
    print(f"R2 expected even lanes only:        {regfile[2]}")
    print(f"R3 expected upper-half lanes only:  {regfile[3]}")
    print(f"R4 expected upper-half lanes only:  {regfile[4]}")

    print("\nCompleted instructions:")
    for instr in wb.completed:
        print(
            f"  {instr_str(instr)} | "
            f"active_lanes={active_lanes(instr.lane_wb_mask)} | "
            f"wb_cycle={instr.wb_cycle}"
        )


if __name__ == "__main__":
    run_predicated_demo()