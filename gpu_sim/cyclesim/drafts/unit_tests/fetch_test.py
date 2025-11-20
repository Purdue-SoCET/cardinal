# test_scheduler_icache_mem.py — Fully Connected Pipeline Test
import sys
from pathlib import Path

parent = Path(__file__).resolve().parent.parent
sys.path.append(str(parent))

from base import LatchIF, ForwardingIF, Instruction, DecodeType
from units.scheduler import SchedulerStage
from units.icache import ICacheStage
from units.mem import MemStage
from Memory import Mem
from bitstring import Bits


# --------------------------------------------
# Helper wrapper: one simulation cycle
# --------------------------------------------
def cycle(scheduler, icache, memstage,
          fetch_ic_if, memreq_if, memresp_if):

    # 1) scheduler may issue
    issue = scheduler.compute()

    if issue is not None:
        group, warp, pc = issue
        print(f"[Sched] ISSUE: warp {warp} group {group} pc=0x{pc:X}")
        # push fetch request into ICache
        fetch_ic_if.push({"pc": pc})

    # 2) ICache runs
    icache.compute()

    # 3) MemStage runs (takes memreq, eventually produces memresp)
    memstage.compute()

    # 4) ICache might process new memory return on next cycle
    icache.compute()


# --------------------------------------------
# MAIN TEST
# --------------------------------------------
def test_scheduler_icache_mem():

    print("\n======== FULL PIPE TEST: Scheduler + ICache + MemStage ========\n")

    # ---- scheduler forwarding IFs ----
    decode_if = ForwardingIF("Decode→Sched")
    issue_if  = ForwardingIF("Issue→Sched")
    branch_if = ForwardingIF("Branch→Sched")
    wb_if     = ForwardingIF("WB→Sched")
    icache_ihit = ForwardingIF("CACHE->Scheduler")

    # Initialize scheduler inputs to safe values
    decode_if.push({"type": DecodeType.MOP, "warp_id": 0, "pc": 0})
    issue_if.push([0, 0, 0])    # all ibuffers empty
    branch_if.push(None)
    wb_if.push(None)
    

    # ---- construct scheduler ----
    sched = SchedulerStage(
        name="Scheduler",
        behind_latch=None,
        ahead_latch=None,
        forward_ifs_read={
            "Decode_Scheduler": decode_if,
            "Issue_Scheduler": issue_if,
            "Branch_Scheduler": branch_if,
            "Writeback_Scheduler": wb_if,
            "ihit": icache_ihit
        },
        forward_ifs_write={},
        start_pc=0x1000,
        warp_count=6  # 3 warp-groups
    )

    # ---- latches for ICache ----
    fetch_ic_if = LatchIF("Fetch→ICache")
    ic_de_if    = LatchIF("ICache→Decode")
    memreq_if   = LatchIF("ICache→MemReq")
    memresp_if  = LatchIF("MemResp→ICache")

    # ---- instantiate backend Mem ----
    # fill the memory with DEADBEEF block
    mem_backend = Mem(
        start_pc=0x1000,
        input_file=str(parent / "test.bin"),  # your input file
        fmt="bin",
        block_size=32
    )

    # ---- construct ICache ----
    icache = ICacheStage(
        name="ICache",
        behind_latch=fetch_ic_if,
        ahead_latch=ic_de_if,
        mem_req_if=memreq_if,
        mem_resp_if=memresp_if,
        cache_config={
            "cache_size": 1024,
            "block_size": 32,
            "associativity": 2,
        },
        forward_ifs_write={"ihit": icache_ihit}   # no ihit forwarding needed for now
    )

    # ---- construct MemStage ----
    memstage = MemStage(
        name="MemStage",
        behind_latch=memreq_if,
        ahead_latch=memresp_if,
        mem_backend=mem_backend,
        latency=5     # Mem latency = 5 cycles
    )

    # ------------- RUN TEST -------------
    for cyc in range(15):
        print(f"\n===== CYCLE {cyc} =====")
        cycle(sched, icache, memstage,
              fetch_ic_if, memreq_if, memresp_if)

        if ic_de_if.valid:
            out = ic_de_if.pop()
            print(f"[ICache→Decode] pc=0x{out['pc']:X}, bytes={list(out['packet'])}")
            

    print("\n========== DONE ==========\n")

def block_size_4():
    print("\n======== FULL PIPE TEST: Scheduler + ICache (4 BLOCKS) + MemStage ========\n")

    # ---- scheduler forwarding IFs ----
    decode_if = ForwardingIF("Decode→Sched")
    issue_if  = ForwardingIF("Issue→Sched")
    branch_if = ForwardingIF("Branch→Sched")
    wb_if     = ForwardingIF("WB→Sched")
    icache_ihit = ForwardingIF("CACHE->Scheduler")

    # Initialize scheduler inputs to safe values
    decode_if.push({"type": DecodeType.MOP, "warp_id": 0, "pc": 0})
    issue_if.push([0, 0, 0])    # all ibuffers empty
    branch_if.push(None)
    wb_if.push(None)
    

    # ---- construct scheduler ----
    sched = SchedulerStage(
        name="Scheduler",
        behind_latch=None,
        ahead_latch=None,
        forward_ifs_read={
            "Decode_Scheduler": decode_if,
            "Issue_Scheduler": issue_if,
            "Branch_Scheduler": branch_if,
            "Writeback_Scheduler": wb_if,
            "ihit": icache_ihit
        },
        forward_ifs_write={},
        start_pc=0x1000,
        warp_count=6  # 3 warp-groups
    )

    # ---- latches for ICache ----
    fetch_ic_if = LatchIF("Fetch→ICache")
    ic_de_if    = LatchIF("ICache→Decode")
    memreq_if   = LatchIF("ICache→MemReq")
    memresp_if  = LatchIF("MemResp→ICache")

    # ---- instantiate backend Mem ----
    # fill the memory with DEADBEEF block
    mem_backend = Mem(
        start_pc=0x1000,
        input_file=str(parent / "test.bin"),  # your input file
        fmt="bin",
        block_size=32
    )

    # ---- construct ICache ----
    icache = ICacheStage(
        name="ICache",
        behind_latch=fetch_ic_if,
        ahead_latch=ic_de_if,
        mem_req_if=memreq_if,
        mem_resp_if=memresp_if,
        cache_config={
            "cache_size": 1024,
            "block_size": 4,
            "associativity": 2,
        },
        forward_ifs_write={"ihit": icache_ihit}   # no ihit forwarding needed for now
    )

    # ---- construct MemStage ----
    memstage = MemStage(
        name="MemStage",
        behind_latch=memreq_if,
        ahead_latch=memresp_if,
        mem_backend=mem_backend,
        latency=5     # Mem latency = 5 cycles
    )

    # ------------- RUN TEST -------------
    for cyc in range(20):
        print(f"\n===== CYCLE {cyc} =====")
        cycle(sched, icache, memstage,
              fetch_ic_if, memreq_if, memresp_if)

        if ic_de_if.valid:
            out = ic_de_if.pop()
            print(f"[ICache→Decode] pc=0x{out['pc']:X}, bytes={list(out['packet'])}")
            

    print("\n========== DONE ==========\n")
if __name__ == "__main__":
    test_scheduler_icache_mem()
    block_size_4()
