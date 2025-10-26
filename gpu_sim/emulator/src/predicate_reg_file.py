from functools import singledispatchmethod

from reg_file import *

class Predicate_Reg_File(Reg_File):
    def __init__(self) -> None:
        super().__init__(num_regs=32, num_bits_per_reg=1, init_value=1)
        
        
    @singledispatchmethod
    def read(self, addr):
        """
        This method can be called using an address (type Bits with length of 5 bits),
        or it can be called using a thread ID (type int).

        See implementations below: (@read.register)
        """

        raise NotImplementedError(f"Unsupported type for read: {type(addr)}")

    @read.register
    def _(self, addr: Bits) -> Bits:
        return super().read(addr)
    
    @read.register
    def _(self, thread_id: int) -> Bits:
        if thread_id > 31:
            global_thread_id = thread_id
            local_thread_id = self._get_local_thread_id_from(global_thread_id)
        else:
            local_thread_id = thread_id

        addr = Bits(uint=local_thread_id, length=5)
        return super().read(addr)

    @singledispatchmethod
    def write(self, addr, data) -> None:
        """
        This method can be called using an address (type Bits with length of 5 bits),
        or it can be called using a thread ID (type int).

        See implementations below: (@write.register)
        """
        raise NotImplementedError(f"Unsupported type for write: {type(addr)}")

    @write.register
    def _(self, addr: Bits, data: Bits) -> None:
        super().write(addr, data)

    @write.register
    def _(self, thread_id: int, data: Bits) -> None:
        if thread_id > self.num_regs - 1:
            global_thread_id = thread_id
            local_thread_id = self._get_local_thread_id_from(global_thread_id)
        else:
            local_thread_id = thread_id

        addr = Bits(uint=local_thread_id, length=5)
        super().write(addr, data)

    def write_all(self, data) -> None:
        for i in range(self.num_regs):
            self.write(i, data)