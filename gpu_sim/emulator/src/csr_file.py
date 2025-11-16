from bitstring import Bits

class CSR_File:
    def __init__(self, warp_id: int, block_id: int) -> None:
        self.warp_id = warp_id
        self.local_thread_ids = [Bits(int=i, length=32) for i in range(32)]
        self.global_thread_ids = [Bits(int=(i + 32 * warp_id), length=32) for i in range(32)]
        self.block_id = block_id  # Example block ID

    def read(self, addr) -> int:
        pass # do we need this?

    def write(self, addr, data) -> None:
        pass # do we need this?