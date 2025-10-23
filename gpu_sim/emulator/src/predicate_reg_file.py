class Predicate_Reg_File(Reg_File):
    def __init__(self) -> None:
        super().__init__(32)

    def read(self, addr: Bits) -> Bits:
        return super().read(addr)

    def write(self, addr: Bits, data: Bits) -> None:
        super().write(addr, data)