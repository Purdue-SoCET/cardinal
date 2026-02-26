from dataclasses import dataclass, field
from typing import Optional, Any

@dataclass
class Latch_IF:
    payload: Optional[Any] = None
    valid: int = 0
    name: str = field(default=None, repr=False)

    def soft_push(self, data: Any) -> int:
        if not self.valid:
            return 0
        self.payload = data
        self.valid = 1
        return 1
    
    def forced_push(self, data: Any) -> None:
        self.payload = data
        self.valid = 1

    def snoop(self) -> Optional[Any]:
        return self.payload if self.valid else None
    
    def pop(self) -> Optional[Any]:
        if not self.valid:
            return None
        data = self.payload
        self.payload = None
        self.valid = 0
        return data



@dataclass
class Feedback_IF:
    payload: Optional[Any] = None
    valid: int = 0
    name: str = field(default=None, repr=False)

    def push(self, data: Any) -> None:
        self.payload = data
        self.valid = 1
    
    def pop(self) -> Optional[Any]:
        data = self.payload
        self.payload = None
        self.valid = 0
        return data



@dataclass
class Stall_IF:
    stall: int = 0

    def signal_stall(self) -> None:
        self.stall = 1

    def signal_free(self) -> None:
        self.stall = 0