from dataclasses import dataclass, field
from typing import Any, List
from bitstring import Bits

@dataclass
class CsrTable:
    # Hierarchy: Warp(List): Data(List). Data = [base_id, tb_id, tb_size]
    warps: int = 32
    table: List[List[Any]] = field(init=False)

    def __post_init__(self):
        self.table = [[0, 0, 0] for _ in range(self.warps)]

    def write_data(self, warp_id, base_id, tb_id, tb_size) -> None:
        self.table[warp_id] = [base_id, tb_id, tb_size]

    def read_base_id(self, warp_id) -> Any:
        return self.table[warp_id][0]

    def read_tb_id(self, warp_id) -> Any:
        return self.table[warp_id][1]
    
    def read_tb_size(self, warp_id) -> Any:
        return self.table[warp_id][2]

    def dump(self):
        print(f"\n{'='*80}")
        print(f"{'CSR TABLE DUMP':^80}")
        print(f"{'='*80}")
        print(f"---------\n")
        print(f"Warp id: base_id | tb_id | tb_size")

        for w in range(self.warps):
            print(f"Warp {w}: {self.table[w][0]} | {self.table[w][1]} | {self.table[w][2]}\n")

        print(f"\n")
        