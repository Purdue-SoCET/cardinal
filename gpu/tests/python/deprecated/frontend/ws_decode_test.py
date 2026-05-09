import sys
from pathlib import Path
from simulator.latch_forward_stage import LatchIF, ForwardingIF, Instruction, Stage, DecodeType
from simulator.scheduler.scheduler import SchedulerStage
from simulator.scheduler.csrtable import CsrTable
from simulator.mem.icache_stage import ICacheStage
from simulator.mem.mem_controller import MemController
from simulator.mem.Memory import Mem
from simulator.decode.decode_class import DecodeStage
from simulator.decode.predicate_reg_file import PredicateRegFile
from simulator.execute.stage import FunctionalUnitConfig
from simulator.kernel_base_pointers import KernelBasePointers
from bitstring import Bits

FILE_ROOT = Path(__file__).resolve().parent
START_PC = 0x1000
LAT = 2
WARP_COUNT = 32


# latches
tbs_ws_if = LatchIF("Thread Block Scheudler - Warp Scheduler Latch")
ws_icache_if = LatchIF("Scheduler - ICache Latch")
icache_mem_req_if = LatchIF("ICache - Mem Latch")
dummy_dcache_mem_req_if = LatchIF("Dummy DCache-Mem Latch")
mem_icache_resp_if = LatchIF("Mem-ICache Latch")
dummy_dcache_mem_resp_if = LatchIF("Mem-Dummy DCache Latch")
icache_decode_if = LatchIF("ICache-Decode Latch")
decode_issue_if = LatchIF("Decode-Issue Latch")

# forwarding units
icache_scheduler_fwif = ForwardingIF(name = "icache_forward_if")
decode_scheduler_fwif = ForwardingIF(name = "decode_forward_if")
issue_scheduler_fwif = ForwardingIF(name = "issue_forward_if")
branch_scheduler_fwif = ForwardingIF(name = "branch_forward_if")
writeback_scheduler_fwif = ForwardingIF(name = "Writeback_forward_if")

# structures
prf = PredicateRegFile(
    num_preds_per_warp = 16,
    num_warps=WARP_COUNT
)

csrtable = CsrTable()

functional_unit_config = FunctionalUnitConfig.get_default_config()
fust = functional_unit_config.generate_fust_dict()

kernel_base_ptrs = KernelBasePointers(max_kernels_per_SM = 1)
kernel_base_ptrs.write(0, Bits(uint=9203920, length=32))

# units
mem = Mem(
    start_pc = 0x1000,
    input_file = FILE_ROOT / "test.bin",
    fmt = "bin"
)

memc = MemController(
    name = "Mem Controller",
        ic_req_latch=icache_mem_req_if,
        dc_req_latch=dummy_dcache_mem_req_if,
        ic_serve_latch=mem_icache_resp_if,
        dc_serve_latch=dummy_dcache_mem_resp_if,
        mem_backend=mem, 
        latency=LAT,
        policy="rr"
)

scheduler_stage = SchedulerStage(
    name = "SchedulerStage",
    csrtable = csrtable,
    behind_latch = tbs_ws_if,
    ahead_latch = ws_icache_if,
    forward_ifs_read = {"ICache_Scheduler" : icache_scheduler_fwif, "Decode_Scheduler": decode_scheduler_fwif, 
                        "Issue_Scheduler": issue_scheduler_fwif, "Branch_Scheduler": branch_scheduler_fwif, 
                        "Writeback_Scheduler": writeback_scheduler_fwif},
    forward_ifs_write = None,
    warp_count = WARP_COUNT,
    policy = "GTO"
)

icache_stage = ICacheStage(
    name="ICache_Stage",
    behind_latch=ws_icache_if,
    ahead_latch=icache_decode_if,
    mem_req_if=icache_mem_req_if,
    mem_resp_if=mem_icache_resp_if,
    cache_config={"cache_size": 32 * 1024, 
                    "block_size": 4, 
                    "associativity": 1},
    forward_ifs_write= {"ICache_Scheduler": icache_scheduler_fwif},
)

decode_stage = DecodeStage(
    name="Decode Stage",
    behind_latch=icache_decode_if,
    ahead_latch=decode_issue_if,
    prf=prf,
    fust=fust,
    csr_table=csrtable,
    kernel_base_ptrs=kernel_base_ptrs,
    forward_ifs_read=None,
    forward_ifs_write={"Decode_Scheduler_Pckt": decode_scheduler_fwif}
)

# Initialize all predicate registers to 1 (all threads active)
for warp in range(WARP_COUNT):
    for pred in range(16 * 2):  # num_preds_per_warp * 2
        for neg in range(2):  # both positive and negative versions
            prf.reg_file[warp][pred][neg] = [True] * 32  # all 32 threads active

def tbs_init():
    tbs_ws_if.push([0, 256, START_PC])

# cycling all stages
def cycle(cycles: int = 1):
    for cycle in range(cycles):
        print(f"\n------------cycle {cycle + 1}------------\n")
        # dummy push from issue
        issue_scheduler_fwif.push([0] * scheduler_stage.num_groups)

        updated_instruction = None
        if decode_issue_if.valid:
            updated_instruction = decode_issue_if.pop()

        if updated_instruction is None:
            print("[Issue] Did not receive any valid instruction in this cycle")
        else:
            print(f"[Issue] Received {updated_instruction}")

        decode_stage.compute()
        memc.compute()
        icache_stage.compute()
        scheduler_stage.compute()

# keep fetching test
def main():
    tbs_init()
    cycle(20)
    return

if __name__ == "__main__":
    main()
