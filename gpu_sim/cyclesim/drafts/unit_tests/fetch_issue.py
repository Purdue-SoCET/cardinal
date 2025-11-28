# test_scheduler_icache_mem.py — Fully Connected Pipeline Test
import sys
from pathlib import Path

parent = Path(__file__).resolve().parent.parent
sys.path.append(str(parent))

from base import LatchIF, ForwardingIF, Instruction, DecodeType
from units.scheduler import SchedulerStage
from units.icache import ICacheStage
from units.decode import DecodeStage
from units.issue import IssueStage
from regfile import RegisterFile
from units.pred_reg_file import PredicateRegFile
from units.mem import MemStage
from Memory import Mem
from bitstring import Bits


# --------------------------------------------
# Helper wrapper: one simulation cycle
# --------------------------------------------
def cycle(scheduler, icache, memstage, decode_stage, issue_stage,
          fetch_ic_if, memreq_if, memresp_if, de_ibuff_if, ibuff_ns_if):

    # 1) scheduler may issue
    issue = scheduler.compute()
    print(f"[Sched] got={issue}\n")
    if issue is not None:
        new_inst = issue
        print(f"[Sched] ISSUE: warp {new_inst.warp} group {new_inst.warpGroup} pc=0x{new_inst.pc:X}")
        # push fetch request into ICache
        fetch_ic_if.push(new_inst)

    # 2) ICache runs
    icache.compute()

    # 3) MemStage runs (takes memreq, eventually produces memresp)
    memstage.compute()

    # 4) ICache might process new memory return on next cycle
    icache.compute()

    # 5) Decode Stage runs
    decode_stage.compute()

    inst_for_issue = None
    if de_ibuff_if.valid:
        inst_for_issue = de_ibuff_if.pop()

    issue_stage.compute(inst_for_issue)


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
        warp_count=32  # 3 warp-groups
    )

    # ---- latches for ICache ----
    fetch_ic_if = LatchIF("Fetch→ICache")
    ic_de_if    = LatchIF("ICache→Decode")
    memreq_if   = LatchIF("ICache→MemReq")
    memresp_if  = LatchIF("MemResp→ICache")
    de_ibuff_if = LatchIF("Decode→Issue")
    ibuff_ns_if = LatchIF("Issue→NS")


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

    # ---- construct Predicate Reg File ----
    prf = PredicateRegFile(num_preds_per_warp=16, num_warps=32)

    # ---- construct Decode Stage ----
    decode_stage = DecodeStage(
        name="DecodeStage",
        behind_latch=ic_de_if,
        ahead_latch=de_ibuff_if,
        prf=prf,
        forward_ifs_read={"ICache_Decode_Ihit": icache_ihit},
        forward_ifs_write={"Decode_Scheduler": decode_if}
    )

    # ---- construct Regfile ----
    regfile = RegisterFile(banks=2, warps=32, regs_per_warp=64, threads_per_warp=32)
    
    # initialize some registers for testing

    regfile.write_warp_gran(0, 0, [2, 3])
    regfile.write_warp_gran(0, 1, [4, 5])
    regfile.write_warp_gran(0, 2, [6, 7])
    regfile.write_warp_gran(0, 3, [8, 9])

    regfile.write_warp_gran(1, 0, [42, 43])
    regfile.write_warp_gran(1, 1, [44, 45])
    regfile.write_warp_gran(1, 2, [46, 47])
    regfile.write_warp_gran(1, 3, [48, 49])

    regfile.write_warp_gran(2, 0, [70, 71])
    regfile.write_warp_gran(2, 1, [72, 73])
    regfile.write_warp_gran(2, 2, [74, 75])
    regfile.write_warp_gran(2, 3, [76, 77])

    regfile.write_warp_gran(3, 0, [900, 901])
    regfile.write_warp_gran(3, 1, [902, 903])
    regfile.write_warp_gran(3, 2, [904, 905])
    regfile.write_warp_gran(3, 3, [906, 907])
    # ---- construct Issue Stage ----
    issue_stage = IssueStage(
    fust_latency_cycles = 1,
    name = "IssueStage",
    behind_latch = de_ibuff_if,
    ahead_latch = ibuff_ns_if,
    forward_ifs_read = None,
    forward_ifs_write = {"Issue_Scheduler": issue_if},
    regfile = regfile
)
    
    # ------------- RUN TEST -------------
    for cyc in range(30):
        print(f"\n===== CYCLE {cyc} =====")
        cycle(sched, icache, memstage, decode_stage, issue_stage,
              fetch_ic_if, memreq_if, memresp_if, de_ibuff_if, ibuff_ns_if)

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
        warp_count=32  # 3 warp-groups
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
