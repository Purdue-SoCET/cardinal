class compact_queue:
    def __init__(self, length):
        self.queue = [None for i in range(length)]
        self.length = length

    def compact(self, data=None) -> None:
        '''
        Compacts 'None' entries in queue without popping head
        '''
        if self.full():
            return
        for idx, entry in enumerate(self.queue):
            if self.queue[idx] == None and idx+1 < self.length:
                self.queue[idx] = self.queue[idx+1]
                self.queue[idx+1] = None
        self.queue[-1] = data

    def advance(self, data=None):
        '''
        Advances all entries in queue
        Returns popped head
        '''
        out_data = self.queue[0]
        for idx, entry in enumerate(self.queue):
            if idx + 1 < self.length:
                self.queue[idx] = self.queue[idx+1]
        self.queue[-1] = data

        return out_data
    
    def full(self):
        '''
        Indicates whether queue can compact and add a new entry
        '''
        return not any(self.queue)

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
            
            
