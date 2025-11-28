class CompactQueue:
    def __init__(self, length: int, type_: type):
        self.queue: list[type_] = [None for i in range(length)]
        self.length = length
        self.capacity = length - 1  # For compatibility with buffer interface
        self.type_ = type_

    def compact(self, data=None) -> None:
        '''
        Compacts 'None' entries in queue without popping head
        '''
        self.check_type(data)

        if self.is_full:
            return
        
        # Add new data at the end
        self.queue[-1] = data
        
        # Compact by removing None entries and shifting everything forward
        non_none_entries = [entry for entry in self.queue if entry is not None]
        self.queue = non_none_entries + [None] * (self.length - len(non_none_entries))

    def advance(self, data=None):
        '''
        Advances all entries in queue
        Returns popped head
        '''
        self.check_type(data)

        out_data = self.queue[0]
        for idx, entry in enumerate(self.queue):
            if idx + 1 < self.length:
                self.queue[idx] = self.queue[idx+1]
        self.queue[-1] = data

        return out_data
    
    def push(self, data) -> None:
        """
        Add data to the queue using compact method.
        Wrapper for buffer interface compatibility.
        """
        self.compact(data)
    
    def pop(self):
        """
        Remove and return the head of the queue.
        Wrapper for buffer interface compatibility.
        """
        return self.advance(None)
    
    def snoop(self):
        '''
        Returns the head of the queue without advancing
        '''
        return self.queue[0]
    
    def pop(self, data=None):
        '''
        Pops the head of the queue (alias for advance)
        '''
        return self.advance(data)
    
    def is_empty(self):
        '''
        Indicates whether queue is empty
        '''
        return self.queue[0] is None
    
    @property
    def is_full(self):
        '''
        Indicates whether queue can compact and add a new entry
        '''
        return not any(entry is None for entry in self.queue)
    
    def __len__(self):
        """Return the number of non-None entries in the queue"""
        return sum(1 for entry in self.queue if entry is not None)

    def check_type(self, data):
        if not isinstance(data, self.type_) and data is not None:
            raise TypeError(f"Data type {type(data)} does not match queue type {self.type_}")

if __name__ == "__main__":
    # Example Usage
    cq = compact_queue(5)

    #One clock cycle of example queue behavior below
    input_data = input_if.data if input_if.valid else None
    #Set input data to None or the valid input data

    if output_if.ready:
        output_if.data = cq.advance(input_data)
        #If output isn't stalling, advance all entries
    else:
        if not cq.full():
            cq.compact(input_data)
            #If output is stalling, and there are entries in queue
            #compact and add input_data to new entry
            
            
