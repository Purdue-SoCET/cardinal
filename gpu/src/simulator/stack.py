from typing import Any, Optional

class Stack:
    def __init__(self, capacity: int = None, type_: type = None):
        self.items = []
        self.capacity = capacity
        self.type_ = type_
    
    def push(self, item: Any) -> None:
        """Add an item to the top of the stack."""
        self.check_type(item)
        if self.capacity is not None and len(self.items) >= self.capacity:
            raise OverflowError("Stack is full")
        self.items.append(item)
    
    def pop(self) -> Optional[Any]:
        """Remove and return the top item."""
        if self.is_empty():
            return None
        return self.items.pop()
    
    def snoop(self) -> Optional[Any]:
        """Return the top item without removing it."""
        if self.is_empty():
            return None
        return self.items[-1]
    
    def is_empty(self) -> bool:
        return len(self.items) == 0
    
    def is_full(self) -> bool:
        if self.capacity is None:
            return False
        return len(self.items) >= self.capacity
    
    def __len__(self) -> int:
        return len(self.items)
    
    def check_type(self, data):
        if self.type_ is not None and not isinstance(data, self.type_):
            raise TypeError(f"Data type {type(data)} does not match stack type {self.type_}")