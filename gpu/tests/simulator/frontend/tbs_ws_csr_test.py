from simulator.scheduler.scheduler import SchedulerStage
from simulator.scheduler.csrtable import CsrTable
from simulator.latch_forward_stage import DecodeType, LatchIF, ForwardingIF

icache_scheduler = ForwardingIF(name = "i$_forward_if")
decode_scheduler = ForwardingIF(name = "decode_forward_if")
issue_scheduler = ForwardingIF(name = "issue_forward_if")
branch_scheduler = ForwardingIF(name = "branch_forward_if")
writeback_scheduler = ForwardingIF(name = "writeback_forward_if")

csrtable = CsrTable(warps = 32)

tbs_latch = LatchIF(name = "tbs_ws_latch")
ws_latch = LatchIF(name = "ws_i$_latch")

scheduler_stage = SchedulerStage(
    name = "Scheduler",
    csrtable = csrtable,
    behind_latch = tbs_latch,
    ahead_latch = ws_latch,
    forward_ifs_read = {"ICache_Scheduler": icache_scheduler, "Decode_Scheduler": decode_scheduler, "Issue_Scheduler": issue_scheduler, "Branch_Scheduler": branch_scheduler, "Writeback_Scheduler": writeback_scheduler},
    forward_ifs_write = None
)

def test_startup():
    # pushing to sm
    tbs_latch.push([0, 256, 0x1000])

    # setting foward interfaces
    icache_scheduler.push(False)
    decode_scheduler.push({"type": DecodeType.MOP, "warp_id": 0, "pc": 0})
    issue_scheduler.push([0] * scheduler_stage.num_groups)
    branch_scheduler.push(None)
    writeback_scheduler.push(None)

    # computing/populating
    scheduler_stage.compute()
    return

def main():
    test_startup()
    csrtable.dump()

if __name__ == "__main__":
    main()
