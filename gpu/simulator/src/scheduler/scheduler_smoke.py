import sys
from base import DecodeType, WarpState, WarpGroup, ForwardingIF, LatchIF
from scheduler import SchedulerStage

# initializing parameters/latches/forwarding stages
START_PC = 0
WARP_COUNT = 6

decode_scheduler = ForwardingIF(name = "decode_forward_if")
issue_scheduler = ForwardingIF(name = "issue_forward_if")
branch_scheduler = ForwardingIF(name = "branch_forward_if")
writeback_scheduler = ForwardingIF(name = "Writeback_forward_if")

scheduler_stage = SchedulerStage(
    name = "Scheduler",
    behind_latch = None,
    ahead_latch = None,
    forward_ifs_read = {"Decode_Scheduler" : decode_scheduler, "Issue_Scheduler": issue_scheduler, "Branch_Scheduler": branch_scheduler, "Writeback_Scheduler": writeback_scheduler},
    forward_ifs_write = None,
    start_pc = START_PC,
    warp_count = WARP_COUNT
)

# helper functions for cycling
def cycle(cycles = scheduler_stage.warp_count):
    for i in range(cycles):
        group, warp, pc = scheduler_stage.compute()
    return group, warp, pc

def label(test):
    print(f"##################### {test} #####################")

def log():
    print(f"\n-----------\n")
    for warp_group in scheduler_stage.warp_table:
        print(f"warp group: {warp_group.group_id} || pc: {warp_group.pc} || state: {warp_group.state} || in-flight: {warp_group.in_flight}\n")
    print(f"\n-----------\n")
    return

# unit tests
def init():
    label("INITIALIZATION CHECK")
    log()
    return

def uninterrupted_cycling():
    # initializing interfaces
    decode_scheduler.push({"type": DecodeType.MOP, "warp_id": 0, "pc": 0})
    issue_scheduler.push([0] * scheduler_stage.num_groups)
    branch_scheduler.push(None)
    writeback_scheduler.push(None)

    label("NORMAL CYCLING CHECK")

    cycle()
    print(f"After first iteration")
    log()

    cycle()
    print(f"After second iteration")
    log()

def end_of_packet():
    label("END OF PACKET TESTS")

    # turning on eop for warp 0
    group, warp, pc = cycle(1)
    decode_scheduler.push({"type": DecodeType.EOP, "warp_id": 0, "pc": 16})

    # turning on eop for warp 1
    group, warp, pc = cycle(1)
    decode_scheduler.push({"type": DecodeType.EOP, "warp_id": 1, "pc": 16})

    # turning off eop
    cycle(1)
    decode_scheduler.push({"type": DecodeType.MOP, "warp_id": 0, "pc": 0})
    
    cycle(scheduler_stage.warp_count-3)
    print(f"After group 0 stalls at PC = 8 -- first iteration")
    log()

    cycle()
    print(f"After group 0 stalls at PC = 8 -- second iteration")
    log()
    return

def in_flight_clear():
    label("WRITEBACK TESTS")
    writeback_scheduler.push({"warp_group": 0})

    for i in range(6):
        cycle(1)
        print(f"After {i + 1} instructions written back")
        log()

    writeback_scheduler.push(None)
    cycle(6)
    print("After one additional iteration")
    log()
    return

def i_buffer_full():
    label("I BUFFER TESTS")
    issue_scheduler.push([0] + [1] * (scheduler_stage.num_groups - 1))
    cycle(scheduler_stage.warp_count - 2)
    print(f"All groups except 0 stalling due to Ibuffer full")
    log()

    issue_scheduler.push([0] * scheduler_stage.num_groups)
    cycle()
    print(f"Stalls cleared -> one iteration")
    log()

    return

def branch():
    label("BRANCH TEST")
    branch_scheduler.push({"warp_group": 2, "dest": 300})
    cycle(1)
    branch_scheduler.push(None)
    cycle(scheduler_stage.warp_count - 1)
    print("After first iteration")
    log()

    cycle()
    print("After second iteration")
    log()
    return

def halt():
    label("HALT TEST")
    for i in range(7):
        cycle(1)
        decode_scheduler.push({"warp_id": (i + 2) % scheduler_stage.warp_count, "type": DecodeType.halt, "pc": 0})

    log()
    return

def main():
    # output logging
    original_stdout = sys.stdout
    with open("output.txt", "w") as f:
        sys.stdout = f
        init()
        uninterrupted_cycling()
        end_of_packet()
        in_flight_clear()
        i_buffer_full()
        branch()
        halt()

    sys.stdout = original_stdout
    return

if __name__ == "__main__":
    main()