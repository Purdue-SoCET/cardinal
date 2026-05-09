from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from simulator.interfaces import LatchIF, ForwardingIF

@dataclass
class Stage:
    name: str
    behind_latch: Optional[LatchIF] = None
    ahead_latch: Optional[LatchIF] = None
    # forward_if_read: Optional[ForwardingIF] = None
    forward_ifs_read: Dict[str, ForwardingIF] = field(default_factory=dict)
    # forward_if_write: Optional[ForwardingIF] = None
    forward_ifs_write: Dict[str, ForwardingIF] = field(default_factory=dict)
    
    def get_data(self) -> Any:
        self.behind_latch.pop()

    def send_output(self, data: Any) -> None:
        self.ahead_latch.push(data)

    def forward_signals(self, forward_if: str, data: Any) -> None:
        self.forward_ifs_write[forward_if].push(data)

    def compute(self, input_data: Any) -> Any:
        # default computation, subclassess will override this
        return input_data

# helper function for dumping memory
def dump_bytes(mem, base, n=4):
    for i in range(n):
        addr = base + i
        print(f"{addr:#06x}: {mem.memory.get(addr, 0):#04x}")
