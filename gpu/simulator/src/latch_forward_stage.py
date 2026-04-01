from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
from bitstring import Bits
from pathlib import Path
import sys

parent = Path(__file__).resolve().parents[2]
sys.path.append(str(parent))

from src.simple_isa import Op

# ============================================================
# Core instruction object
# ============================================================

@dataclass
class simple_instruction:
    # basic identity
    pc: Optional[Bits] = None
    warp_id: Optional[int] = None
    # warp_group_id: Optional[int] = None

    # decode / execute information
    opcode: Optional[Op] = None
    intended_FU: Optional[str] = None

    rs1: Optional[Bits] = None
    rs2: Optional[Bits] = None
    rd: Optional[Bits] = None
    imm: Optional[Bits] = None

    src_pred: Optional[Bits] = None
    dest_pred: Optional[Bits] = None
    active_mask: Optional[Bits] = None

    # operand / result data
    rdat1: List[Any] = field(default_factory=list)
    rdat2: List[Any] = field(default_factory=list)
    wdat: List[Any] = field(default_factory=list)

    # lightweight tracing
    stage_entry: Dict[str, int] = field(default_factory=dict)
    stage_exit: Dict[str, int] = field(default_factory=dict)
    wb_cycle: Optional[int] = None

    def mark_stage_enter(self, stage: str, cycle: int):
        self.stage_entry.setdefault(stage, cycle)

    def mark_stage_exit(self, stage: str, cycle: int):
        self.stage_exit[stage] = cycle

    def mark_writeback(self, cycle: int):
        self.wb_cycle = cycle


# ============================================================
# Simple pipeline interfaces
# ============================================================

@dataclass
class ForwardingIF:
    payload: Optional[Any] = None
    wait: bool = False
    name: str = field(default="ForwardingIF", repr=False)

    def push(self, data: Any) -> None:
        self.payload = data
        self.wait = False

    def pop(self) -> Optional[Any]:
        data = self.payload
        self.payload = None
        return data

    def set_wait(self, flag: bool) -> None:
        self.wait = bool(flag)

    def __repr__(self) -> str:
        has_payload = self.payload is not None
        return f"<{self.name} has_payload={has_payload} wait={self.wait} payload={self.payload!r}>"


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

    def clear_all(self) -> None:
        self.payload = None
        self.valid = False

    def __repr__(self) -> str:
        return f"<{self.name} valid={self.valid} payload={self.payload!r}>"


@dataclass
class Stage:
    name: str
    behind_latch: Optional[LatchIF] = None
    ahead_latch: Optional[LatchIF] = None
    forward_ifs_read: Dict[str, ForwardingIF] = field(default_factory=dict)
    forward_ifs_write: Dict[str, ForwardingIF] = field(default_factory=dict)

    def get_data(self) -> Any:
        self.behind_latch.pop()

    def send_output(self, data: Any) -> None:
        self.ahead_latch.push(data)

    def forward_signals(self, forward_if: str, data: Any) -> None:
        self.forward_ifs_write[forward_if].push(data)

    def compute(self, input_data: Any) -> Any:
        return input_data