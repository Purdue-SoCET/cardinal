from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List
from bitstring import Bits
from common.custom_enums_multi import Op

@dataclass
class Instruction:
    # ----- required (no defaults) -----
    # STRUCTURAL HAZARD WITH PRED REG FILE WRITE AND READ LATER ON
    # INSTRUCTION JUST CONTAINS THE OPCODE INFORMATION
    # discusss more later about this..
    pc: Optional[Bits] = None
    warp_id: Optional[int] = None
    warp_group_id: Optional[int] = None
    num_operands: Optional[int] = None

    # ----- fields populated by decode ----
    intended_FU: Optional[str] = None 
    rs1: Optional[Bits] = None
    rs2: Optional[Bits] = None
    rd: Optional[Bits]= None
    src_pred: Optional[Bits]= None
    dest_pred: Optional[Bits]= None
    predicate: Optional[Bits] = None
    active_mask: Optional[Bits] = None
    opcode: Optional[Op]= None
    imm: Optional[Bits]= None
    csr_value: Optional[Any] = None
    csr_param: Optional[Any] = None
    
    packet: Optional[Bits] = None
    issued_cycle: Optional[int] = None
    wb_cycle: Optional[int] = None
    target_bank: int = None 
    target_regfile: Optional[str] = None

    rdat1: list[Bits] = field(default_factory=list)
    rdat2: list[Bits] = field(default_factory=list)
    wdat: list[Bits] = field(default_factory=list)
    wdat_pred: list[Bits] = field(default_factory=list)


    # ----- optional / with defaults (must come after ALL non-defaults) -----
    # this is for instruction data memory responses, populated by the MemController
    stage_entry: Dict[str, int] = field(default_factory=dict)
    stage_exit:  Dict[str, int] = field(default_factory=dict)
    fu_entries:  List[Dict]     = field(default_factory=list)
    



    
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