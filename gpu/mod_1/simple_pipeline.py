from pathlib import Path
import sys
from collections import deque
from bitstring import Bits

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.base_class import Stage, LatchIF, ForwardingIF, simple_instruction
from src.simple_isa import R_Op, I_Op, S_Op

# ------------------------------------------------------------------
# Small helpers
# ------------------------------------------------------------------

LOAD_OP = getattr(I_Op, "LD", None) or getattr(I_Op, "LW")
STORE_OP = getattr(S_Op, "ST", None) or getattr(S_Op, "SW")


def regbits(n: int) -> Bits:
    return Bits(uint=n, length=6)


def wordbits(n: int) -> Bits:
    return Bits(int=n, length=32)


def immbits(n: int) -> Bits:
    return Bits(int=n, length=32)


def reg_num(x):
    return None if x is None else x.uint


def bits_to_int(x):
    if x is None:
        return 0
    if isinstance(x, Bits):
        return x.int
    return int(x)


def writes_rd(instr: simple_instruction) -> bool:
    return instr.opcode in (R_Op.ADD, R_Op.SUB, R_Op.MUL, LOAD_OP)


def reads_rs1(instr: simple_instruction) -> bool:
    return instr.opcode in (R_Op.ADD, R_Op.SUB, R_Op.MUL, LOAD_OP, STORE_OP)


def reads_rs2(instr: simple_instruction) -> bool:
    return instr.opcode in (R_Op.ADD, R_Op.SUB, R_Op.MUL, STORE_OP)


def op_name(instr: simple_instruction) -> str:
    return "NONE" if instr.opcode is None else instr.opcode.name


def instr_str(instr: simple_instruction) -> str:
    if instr is None:
        return "None"
    return (
        f"{op_name(instr)}"
        f"(pc={bits_to_int(instr.pc)}, "
        f"rd={reg_num(instr.rd)}, rs1={reg_num(instr.rs1)}, "
        f"rs2={reg_num(instr.rs2)}, imm={bits_to_int(instr.imm)})"
    )


# ------------------------------------------------------------------
# Instruction builders
# ------------------------------------------------------------------

def make_r(op, pc, rd, rs1, rs2):
    return simple_instruction(
        pc=wordbits(pc),
        warp_id=0,
        opcode=op,
        rs1=regbits(rs1),
        rs2=regbits(rs2),
        rd=regbits(rd),
    )


def make_i(op, pc, rd, rs1, imm):
    return simple_instruction(
        pc=wordbits(pc),
        warp_id=0,
        opcode=op,
        rs1=regbits(rs1),
        rd=regbits(rd),
        imm=immbits(imm),
    )


def make_s(op, pc, rs1, rs2, imm):
    return simple_instruction(
        pc=wordbits(pc),
        warp_id=0,
        opcode=op,
        rs1=regbits(rs1),
        rs2=regbits(rs2),
        imm=immbits(imm),
    )


# ------------------------------------------------------------------
# Pipeline stages
# ------------------------------------------------------------------

class IssueStage(Stage):
    def __init__(self, name, ahead_latch, program, regfile, reg_busy):
        super().__init__(name=name, behind_latch=None, ahead_latch=ahead_latch)
        self.program = program
        self.regfile = regfile
        self.reg_busy = reg_busy

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
            print(f"{self.name}: stall (ISSUE_EX latch not ready)")
            return

        instr = self.program[0]
        busy = self._busy_sources(instr)

        if busy:
            print(f"{self.name}: stall RAW hazard on regs {busy} for {instr_str(instr)}")
            return

        instr = self.program.popleft()
        instr.mark_stage_enter("ISSUE", cycle)

        if reads_rs1(instr):
            instr.rdat1 = wordbits(self.regfile[reg_num(instr.rs1)])

        if reads_rs2(instr):
            instr.rdat2 = wordbits(self.regfile[reg_num(instr.rs2)])

        if writes_rd(instr):
            self.reg_busy[reg_num(instr.rd)] = True

        ok = self.ahead_latch.push(instr)
        if not ok:
            raise RuntimeError("Issue stage expected ISSUE_EX latch to be ready")

        instr.mark_stage_exit("ISSUE", cycle)
        print(f"{self.name}: issued {instr_str(instr)}")


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
            result = bits_to_int(instr.rdat1) + bits_to_int(instr.rdat2)
            instr.wdat = wordbits(result)
            instr.intended_FU = "ALU"

        elif instr.opcode == R_Op.SUB:
            result = bits_to_int(instr.rdat1) - bits_to_int(instr.rdat2)
            instr.wdat = wordbits(result)
            instr.intended_FU = "ALU"

        elif instr.opcode == R_Op.MUL:
            result = bits_to_int(instr.rdat1) * bits_to_int(instr.rdat2)
            instr.wdat = wordbits(result)
            instr.intended_FU = "ALU"

        elif instr.opcode == LOAD_OP:
            instr.mem_addr = bits_to_int(instr.rdat1) + bits_to_int(instr.imm)
            instr.intended_FU = "MEM"

        elif instr.opcode == STORE_OP:
            instr.mem_addr = bits_to_int(instr.rdat1) + bits_to_int(instr.imm)
            instr.store_data = wordbits(bits_to_int(instr.rdat2))
            instr.intended_FU = "MEM"

        else:
            raise ValueError(f"Unsupported opcode in Execute: {instr.opcode}")

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

                if self.current.opcode in (LOAD_OP, STORE_OP):
                    self.remaining = self.latency - 1
                else:
                    self.remaining = 0

        if self.current is None:
            self._set_backpressure(False)
            print(f"{self.name}: idle")
            return

        # While MEM owns an instruction, block EX from sending another one.
        self._set_backpressure(True)

        if self.remaining > 0:
            print(
                f"{self.name}: busy with {instr_str(self.current)} "
                f"(remaining={self.remaining})"
            )
            self.remaining -= 1
            return

        if not self.ahead_latch.ready_for_push():
            print(f"{self.name}: stall (MEM_WB latch blocked) for {instr_str(self.current)}")
            return

        instr = self.current

        if instr.opcode == LOAD_OP:
            loaded = self.memory.get(instr.mem_addr, 0)
            instr.load_data = wordbits(loaded)
            instr.wdat = wordbits(loaded)
            print(f"{self.name}: load mem[{instr.mem_addr}] -> {loaded}")

        elif instr.opcode == STORE_OP:
            value = bits_to_int(instr.store_data)
            self.memory[instr.mem_addr] = value
            print(f"{self.name}: store {value} -> mem[{instr.mem_addr}]")

        else:
            print(f"{self.name}: pass-through for {instr_str(instr)}")

        ok = self.ahead_latch.push(instr)
        if not ok:
            print(f"{self.name}: unexpected push failure into MEM_WB")
            return

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
            value = bits_to_int(instr.wdat)
            self.regfile[rd] = value
            self.reg_busy[rd] = False
            print(f"{self.name}: wrote R{rd} = {value} for {instr_str(instr)}")

        elif instr.opcode == STORE_OP:
            print(f"{self.name}: completed store {instr_str(instr)}")

        else:
            print(f"{self.name}: completed {instr_str(instr)}")

        instr.mark_stage_exit("WB", cycle)
        instr.mark_writeback(cycle)
        self.completed.append(instr)


# ------------------------------------------------------------------
# Debug printing
# ------------------------------------------------------------------

def dump_latch(name, latch):
    if latch.valid:
        print(f"  {name}: {instr_str(latch.payload)}")
    else:
        print(f"  {name}: empty")


def dump_state(cycle, issue_ex, ex_mem, mem_wb, regfile, reg_busy, memory):
    print(f"\n================ CYCLE {cycle} ================")
    dump_latch("ISSUE_EX", issue_ex)
    dump_latch("EX_MEM", ex_mem)
    dump_latch("MEM_WB", mem_wb)

    busy_regs = sorted([r for r, v in reg_busy.items() if v])
    print(f"  Busy regs: {busy_regs}")
    print(
        "  Regs: "
        f"R1={regfile[1]} R2={regfile[2]} R3={regfile[3]} "
        f"R4={regfile[4]} R5={regfile[5]} R6={regfile[6]} "
        f"R8={regfile[8]} R9={regfile[9]}"
    )
    print(f"  Memory: mem[100]={memory.get(100, 0)} mem[104]={memory.get(104, 0)}")


# ------------------------------------------------------------------
# Main demo
# ------------------------------------------------------------------

def run_multistage_demo():
    # Register file + scoreboard
    regfile = {i: 0 for i in range(16)}
    reg_busy = {i: False for i in range(16)}

    # Initial values
    regfile[5] = 4
    regfile[6] = 5
    regfile[8] = 100
    regfile[9] = 1

    # Memory contents
    memory = {
        100: 42,   # load target
        104: 0,    # store target
    }

    # Program:
    #   R1 = R5 + R6          = 9
    #   R2 = MEM[R8 + 0]      = 42     <-- memory stall
    #   R4 = R5 * R6          = 20     <-- independent, but blocked behind MEM
    #   R3 = R2 + R9          = 43     <-- RAW stall until load completes
    #   MEM[R8 + 4] = R3      = 43
    program = deque([
        make_r(R_Op.ADD, pc=0,  rd=1, rs1=5, rs2=6),
        make_i(LOAD_OP, pc=4,   rd=2, rs1=8, imm=0),
        make_r(R_Op.MUL, pc=8,  rd=4, rs1=5, rs2=6),
        make_r(R_Op.ADD, pc=12, rd=3, rs1=2, rs2=9),
        make_s(STORE_OP, pc=16, rs1=8, rs2=3, imm=4),
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

    # Run downstream -> upstream each cycle
    # This matches the same basic idea as your bigger driver:
    # consumers run before producers so newly-pushed data does not
    # move through multiple stages in one cycle.
    max_cycles = 20

    for cycle in range(max_cycles):
        dump_state(cycle, issue_ex_latch, ex_mem_latch, mem_wb_latch, regfile, reg_busy, memory)

        # IMPORTANT! Run stages in reverse order of data flow (WB -> MEM -> EX -> ISSUE) so that data pushed by a stage in the current cycle is not consumed by the next stage until the following cycle. This models the real hardware behavior where data moves one stage per cycle.  
        
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
    print(f"R1 = {regfile[1]}  (expected 9)")
    print(f"R2 = {regfile[2]}  (expected 42)")
    print(f"R3 = {regfile[3]}  (expected 43)")
    print(f"R4 = {regfile[4]}  (expected 20)")
    print(f"mem[100] = {memory[100]}  (expected 42)")
    print(f"mem[104] = {memory[104]}  (expected 43)")

    print("\nCompleted instructions:")
    for instr in wb.completed:
        print(
            f"  {instr_str(instr)} | "
            f"stage_entry={instr.stage_entry} "
            f"stage_exit={instr.stage_exit} "
            f"wb_cycle={instr.wb_cycle}"
        )


if __name__ == "__main__":
    run_multistage_demo()