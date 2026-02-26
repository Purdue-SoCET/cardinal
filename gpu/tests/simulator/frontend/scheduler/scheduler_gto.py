import sys

from simulator.scheduler.scheduler import SchedulerStage
from simulator.scheduler.csrtable import CsrTable
from simulator.latch_forward_stage import DecodeType, LatchIF, ForwardingIF

TBS_SIZE = 192

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
    forward_ifs_write = None,
    policy = "GTO"
)

def cycle(log = False):
    scheduler_stage.compute()
    value = ws_latch.pop()
    if log:
        print(f"Latch: {value}")

def label(test):
    print(f"##################### {test} #####################")

def log():
    print(f"\n-----------\n")
    for warp_group in scheduler_stage.warp_table:
        if warp_group.pc != 0:
            print(f"warp group: {warp_group.group_id} || pc: {warp_group.pc} || state: {warp_group.state} || in-flight: {warp_group.in_flight}\n")
    print(f"-----------\n")
    return

# unit tests
def init():
    label("INITIALIZATION")
    
    tbs_latch.push([0, TBS_SIZE, 0x1000])
    icache_scheduler.push(True)
    decode_scheduler.push({"type": DecodeType.MOP, "warp_id": 0, "pc": 0x1000})
    issue_scheduler.push([0] * scheduler_stage.num_groups)
    branch_scheduler.push(None)
    writeback_scheduler.push(None)

    cycle()
    log()
    return

def normal_cycle():
    label("CYCLING")

    for _ in range(2 * TBS_SIZE // scheduler_stage.warp_size):
        icache_scheduler.push(True)
        decode_scheduler.push({"type": DecodeType.MOP, "warp_id": 0, "pc": 0x1000})
        issue_scheduler.push([0] * scheduler_stage.num_groups)
        cycle()
    log()

def eop():
    label("EOP")

    icache_scheduler.push(True)
    decode_scheduler.push({"type": DecodeType.EOP, "warp_id": 1, "pc": 0x1018})
    issue_scheduler.push([0] * scheduler_stage.num_groups)
    cycle()

    for _ in range((TBS_SIZE // scheduler_stage.warp_size) - 1):
        icache_scheduler.push(True)
        issue_scheduler.push([0] * scheduler_stage.num_groups)
        cycle()
    log()

def wb():
    label("WB")

    for _ in range(2 * TBS_SIZE // scheduler_stage.warp_size):
        icache_scheduler.push(True)
        decode_scheduler.push({"type": DecodeType.MOP, "warp_id": 2, "pc": 0x1000})
        issue_scheduler.push([0] * scheduler_stage.num_groups)
        writeback_scheduler.push({"warp_group": 0})
        cycle()
    log()

def swap():
    label("SWAP")

    icache_scheduler.push(True)
    decode_scheduler.push({"type": DecodeType.EOP, "warp_id": 3, "pc": 0x1024})
    issue_scheduler.push([0] * scheduler_stage.num_groups)
    cycle()

    for _ in range((TBS_SIZE // scheduler_stage.warp_size) - 1):
        icache_scheduler.push(True)
        issue_scheduler.push([0] * scheduler_stage.num_groups)
        cycle()
    log()

def main():
    original_stdout = sys.stdout
    with open("output.txt", "w") as f:
        sys.stdout = f
        init()
        normal_cycle()
        eop()
        wb()
        swap()

    sys.stdout = original_stdout
    return

if __name__ == "__main__":
    main()
