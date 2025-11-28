from typing import Any, Optional

class CircularBuffer:
    def __init__(self, capacity: int, type_: type = None):
        self.capacity = capacity
        self.buffer = [None] * capacity
        self.head = 0
        self.tail = 0
        self.size = 0
        self.type_ = type_
    
    def push(self, item: Any) -> None:
        """Add an item to the buffer. Overwrites oldest if full."""
        self.check_type(item)
        if self.size == self.capacity:
            # Buffer is full, overwrite oldest item
            self.tail = (self.tail + 1) % self.capacity
        else:
            self.size += 1
        
        self.buffer[self.head] = item
        self.head = (self.head + 1) % self.capacity
    
    def pop(self) -> Optional[Any]:
        """Remove and return the oldest item."""
        if self.size == 0:
            return None
        
        item = self.buffer[self.tail]
        self.buffer[self.tail] = None
        self.tail = (self.tail + 1) % self.capacity
        self.size -= 1
        return item
    
    def snoop(self) -> Optional[Any]:
        """Return the oldest item without removing it."""
        if self.size == 0:
            return None
        return self.buffer[self.tail]
    
    def is_empty(self) -> bool:
        return self.size == 0
    
    def is_full(self) -> bool:
        return self.size == self.capacity
    
    def __len__(self) -> int:
        return self.size
    
    def check_type(self, data):
        if self.type_ is not None and not isinstance(data, self.type_):
            raise TypeError(f"Data type {type(data)} does not match buffer type {self.type_}")