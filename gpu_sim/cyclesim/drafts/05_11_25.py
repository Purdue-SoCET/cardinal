from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque


@dataclass
class Warp:
    pc: int
    group_id: int
    can_issue: bool = True
    halt: bool = True

@dataclass
class Instruction:
    # init members
    pc: int
    warp: int
    warpGroup: int
    
    # instruction
    opcode: int
    rs1: int
    rs2: int
    rd: int
    pred: int
    packet: int # what is packet?


    # for perf
    issued_cycle: Optional[int] = None
    stage_entry: Dict[str, int] = field(default_factory=dict)   # stage -> first cycle seen
    stage_exit:  Dict[str, int] = field(default_factory=dict)   # stage -> last cycle completed
    fu_entries:  List[Dict]     = field(default_factory=list)   # [{fu:"ALU", enter: c, exit: c}, ...]
    wb_cycle: Optional[int] = None

    def mark_stage_enter(self, stage: str, cycle: int):
        self.stage_entry.setdefault(stage, cycle)

    def mark_stage_exit(self, stage: str, cycle: int):
        self.stage_exit[stage] = cycle

    def mark_fu_enter(self, fu: str, cycle: int):
        self.fu_entries.append({"fu": fu, "enter": cycle, "exit": None})

    def mark_fu_exit(self, fu: str, cycle: int):
        for e in reversed(self.fu_entries):
            if e["fu"] == fu and e["exit"] is None:
                e["exit"] = cycle
                return

    def mark_writeback(self, cycle: int):
        self.wb_cycle = cycle

@dataclass
class ForwardingIF:
    payload: Optional[Any] = None
    valid: bool = False
    wait: bool = False
    name: str = field(default="BackwardIF", repr=False)

    def push(self, data: Any) -> bool:
        if self.valid:
            return False
        self.payload = data
        self.valid = True
    
    def force_push(self, data: Any) -> None:
        self.payload = data
        self.valid = True

    def snoop(self) -> Optional[Any]:
        return self.payload if self.valid else None
    
    def pop(self) -> Optional[Any]:
        if not self.valid:
            return None
        data = self.payload
        self.payload = None
        self.valid = False
        return data
    
    def set_wait(self, flag: bool) -> None:
        self.wait = bool(flag)

    def clear_all(self) -> None:
        self.payload = None
        self.valid = False
        self.wait = False

    def __repr__(self) -> str:
        return (f"<{self.name} valid={self.valid} wait={self.wait} "
            f"payload={self.payload!r}>")




  
@dataclass
class LatchIF:
    payload: Optional[Any] = None
    valid: bool = False
    read: bool = False
    name: str = field(default="LatchIF", repr=False)
    forward_if: Optional[ForwardingIF] = None

    def ready_for_push(self) -> bool:
        if self.valid:
            return False
        if self.forward_if is not None and self.forward_if.wait:
            return False
        return True

    def push(self, data: Any) -> bool:
        if not self.ready_for_push():
            return False
        self.payload = data
        self.valid = True
        return True
    
    def force_push(self, data: Any) -> None: # will most likely need a forceful push for squashing
        self.payload = data
        self.valid = True

    def snoop(self) -> Optional[Any]: # may need this if we want to see the data without clearing the data
        return self.payload if self.valid else None
    
    def pop(self) -> Optional[Any]:
        if not self.valid:
            return None
        data = self.payload
        self.payload = None
        self.valid = False
        return data
    
    def clear_all(self) -> None:
        self.payload = None
        self.valid = False
    
    def __repr__(self) -> str: # idk if we need this or not
        return (f"<{self.name} valid={self.valid} wait={self.wait} "
                f"payload={self.payload!r}>")
  
    
@dataclass
class Stage:
    name: str
    behind_latch: Optional[LatchIF] = None
    ahead_latch: Optional[LatchIF] = None
    forward_if: Optional[ForwardingIF] = None

    def has_input(self) -> bool:
        if self.behind_latch is None: 
            # no behind latch, so always assume true
            return True
        return self.behind_latch.valid
    
    def get_input(self) -> Optional[Any]:
        if self.behind_latch is None:
            # no behind latch, so pop nothing
            return None
        return self.behind_latch.pop()
    
    def can_output(self) -> bool:
        if self.ahead_latch is None:
            # no ahead latch, so always assume true
            return True
        if self.ahead_latch.forward_if and self.ahead_latch.forward_if.wait:
            return False
        return self.ahead_latch.ready_for_push()
    
    def send_output(self, data: Any) -> None:
        if self.ahead_latch is None:
            print(f"[{self.name}] Done: {data!r}")
        else:
            if self.ahead_latch.ready_for_push():
                self.ahead_latch.push(data)
            else:
                print(f"[{self.name}] Could not push output — next stage not ready.")

    def compute(self, input_data: Any) -> Any:
        # default computation, subclassess will override this
        return input_data

    def step(self) -> None:
        if not self.can_output():
            print(f"[{self.name}] Stalled — next stage not ready.")
            return
        
        if not self.has_input():
            print(f"[{self.name}] No input available, idle this cycle.")
            return
        
        input_data = self.get_input()
        output_data = self.compute(input_data)
        self.send_output(output_data)

FetchDecodeIF = LatchIF(name = "FetchDecodeIF")
DecodeIssue_IbufferIF = LatchIF(name = "DecodeIIF")  
de_sched_EOP = ForwardingIF(name = "Decode_Scheduler_EOP")
de_sched_EOP_WID = ForwardingIF(name = "Decode_Scheduler_WARPID")
de_sched_BARR = ForwardingIF(name = "Deecode_Schedular_BARRIER")
de_sched_B_WID = ForwardingIF(name = "Decode_Scheduler_BARRIER_WARPID")
de_sched_B_GID = ForwardingIF(name = "Decode_Scheduler_BARRIER_GROUPID")
de_sched_B_PC = ForwardingIF(name = "Decode_Scheduler_BARRIER_PC")
icache_de_ihit = ForwardingIF(name = "ICache_Decode_Ihit")

# @dataclass
# class FU():
#     name = 
class BranchFU():
    def __init__(self, instructions: Instruction, prf_rd_data: Any, op_1: Any, op_2: Any):
        # i get the instruction data class (probably) as an input.
        # what I need from the instruction class for MY operation:
        # warp, opcode
        self.warp_id = instructions.warp
        self.opcode = instructions.opcode
        self.prf_rd_data = prf_rd_data
        self.op1 = op_1
        self.op2 = op_2

class PredicateRegFile():
    def __init__(self, num_preds_per_warp: int, num_warps: int):
        num_cols = num_preds_per_warp *2 # the number of 
        num_threads = 32

        # 2D structure: warp -> predicate -> [bits per thread]
        self.reg_file = [
            [[[False] * self.num_threads, [False] * self.num_threads]
              for _ in range(num_cols)]
            for _ in range(num_warps)
        ]
    
    def read_predicate(self, prf_rd_en: int, prf_rd_wsel: int, prf_rd_psel: int, prf_neg: int):
        "Predicate register file reads by selecting a 1 from 32 warps, 1 from 16 predicates,"
        " and whether it wants the inverted version or not..."

        if (prf_rd_en):
            return self.reg_file[prf_rd_wsel][prf_rd_psel][prf_neg]
        else: 
            return None
    
    def write_predicate(self, prf_wr_en, prf_wr_wsel: int, prf_wr_psel: int, prf_wr_data):
        # the write will autopopulate the negated version in the table)
        if (prf_wr_en):
                # Convert int to bit array if needed
            if isinstance(prf_wr_data, int):
                bits = [(prf_wr_data >> i) & 1 == 1 for i in range(self.num_threads)]
            else:
                bits = prf_wr_data  # assume already a list of bools

            # Store positive version
            self.reg_file[prf_wr_wsel][prf_wr_psel][0] = bits
            # Store negated version
            self.reg_file[prf_wr_wsel][prf_wr_psel][1] = [not b for b in bits]

class DecodeStage(Stage):
    name = "Decode"
    behind_latch = FetchDecodeIF
    ahead_latch = DecodeIssue_IbufferIF
    forward_if: # config this as a list of inputs 

    def compute(self, input_data: Any) -> Any:
        if input_data is None:
            return None
                
        if self.forward_if and self.forward_if.wait:
            print(f"[{self.name}] Stalled due to wait from next stage.")
            return None
                
        fwd_val = self.forward_if.snoop() if self.forward_if else None
        if fwd_val is not None: # actual logic 
            fwd_ihit = fwd_val["Ihit"]

        

class SchedulerStage(Stage):
    def __init__(self, name, start_pc, )
    
class FetchStage(Stage):
    def compute(self, input_data: Any) -> Any:
        if input_data is None:
            return None

### PIPELINE FILE
stage0_stage1_latch = LatchIF(name = "Latch0to1")
stage1_stage2_latch = LatchIF(name = "Latch1to2")
forward_if_stage1_to_stage0 = ForwardingIF(name = "Forward1to0")
forward_if_stage2_to_stage1 = ForwardingIF(name = "Forward2to1")

stage0 = Stage0(
    name = "Stage0",
    behind_latch = None,
    ahead_latch = stage0_stage1_latch,
    forward_if = forward_if_stage1_to_stage0
)

stage1 = Stage1(
    name = "Stage1",
    behind_latch = stage0_stage1_latch,
    ahead_latch = stage1_stage2_latch,
    forward_if = forward_if_stage1_to_stage0
)

stage2 = Stage2(
    name = "Stage2",
    behind_latch = stage1_stage2_latch,
    ahead_latch = None,
    forward_if = forward_if_stage2_to_stage1
)

class Stage0(Stage):
    def compute(self, input_data: Any) -> Any:
        if input_data is None:
            return None
        
        if self.forward_if and self.forward_if.wait:
            print(f"[{self.name}] Stalled due to wait from next stage.")
            return None
        
        fwd_val = self.forward_if.snoop() if self.forward_if else None
        if fwd_val is not None:
            output = input_data + fwd_val + 100
        else:
            output = input_data + 100
        print(f"[{self.name}] Computed output: {output!r} (forward value: {fwd_val!r})")

        return output
    
class Stage1(Stage):
    def compute(self, input_data: Any) -> Any:
        if input_data is None:
            return None
        
        if self.forward_if and self.forward_if.wait:
            print(f"[{self.name}] Stalled due to wait from next stage.")
            return None

        fwd_val = self.forward_if.snoop() if self.forward_if else None
        if fwd_val is not None:
            output = input_data + fwd_val + 100
        else:
            output = input_data + 100
        print(f"[{self.name}] Computed output: {output!r} (forward value: {fwd_val!r})")

        return output
    
class Stage2(Stage):
    def compute(self, input_data: Any) -> Any:
        if input_data is None:
            return None
        
        output = input_data + 100
        print(f"[{self.name}] Computed output: {output!r}")

        return output