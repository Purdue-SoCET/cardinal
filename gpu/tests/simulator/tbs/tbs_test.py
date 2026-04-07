# ALL TESTING IS DONE WITH ONE SM
from simulator.latch_forward_stage import ForwardingIF, LatchIF
from simulator.tbs.tbs import ThreadBlockRecord, SMRecord, ThreadBlockScheduler

sm_tbs = ForwardingIF(name="Scheduler_TBS")
tbs_latch = LatchIF(name="tbs_ws_latch")

tbs = ThreadBlockScheduler(
    name="tbs",
    behind_latch=None,
    ahead_latch=tbs_latch,
    forward_ifs_read={sm_tbs.name: sm_tbs},
    forward_ifs_write=None
)

def one_block(bdim: int=1024):
    tbs.append_block(bdim=bdim, spc=0x1000, apc=0x1000_0000)
    tbs.compute()
    print(f"{tbs_latch.pop(), tbs.SMs[0].avail_warps}")
    tbs.compute()
    print(f"{tbs_latch.payload}")
    sm_tbs.push([0])
    tbs.compute()
    print(f"{tbs.blocks_done}\n")
    tbs.reset()

def x_full_blocks(x: int, bdim: int=1024):
    for x in range(x):
        tbs.append_block(bdim=bdim, spc=0x1000, apc=0x1000_0000)

    tbs.compute()
    print(f"(block_id, block_dim, start_pc): {tbs_latch.pop(), tbs.SMs[0].avail_warps}")
    tbs.compute()
    print(f"after pop {tbs_latch.pop(), tbs.SMs[0].avail_warps}")

    sm_tbs.push([0])
    tbs.compute()
    print(f"{tbs_latch.pop(), tbs.SMs[0].avail_warps}")
    tbs.compute()
    print(f"{tbs_latch.pop(), tbs.SMs[0].avail_warps}")
    tbs.compute()
    print(f"{tbs_latch.pop(), tbs.SMs[0].avail_warps}")
    sm_tbs.push([1])
    tbs.compute()
    print(f"{tbs.blocks_done}\n")
    tbs.reset()

def div_x_blocks(x: int):
    assert x <= 32, "FUCK YOU ENTER SOMETHING BELOW 32"

    for _ in range(x):
        tbs.append_block(bdim= 1024 // x, spc=0x1000, apc=0x1000_0000)

    for _ in range(x):
        tbs.compute()
        print(f"{tbs_latch.pop(), tbs.SMs[0].avail_warps}")

def main():
    tbs.add_SM()
    # tests 
    # one_block(bdim=1024)
    x_full_blocks(x=2)
    # div_x_blocks(4)

if __name__ == "__main__":
    main()