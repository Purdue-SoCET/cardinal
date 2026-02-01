# test_issue_stage.py
"""
Standalone test for IssueStage logic, ported from the bottom of issue.py.
This script can be run directly to test IssueStage behavior.
"""

from simulator.latch_forward_stage import ForwardingIF, Instruction
from simulator.issue.regfile import RegisterFile
from simulator.issue.stage import IssueStage
import sys
from pathlib import Path
from bitstring import Bits
from gpu.common.custom_enums_multi import *

# Simulate FUST (Functional Unit Status Table)
fust = {"ADD": 0, "SUB": 0, "MUL": 0, "DIV": 0, "SQRT": 0, "LDST": 0}

Issue_forward_to_WS = ForwardingIF(name = "ForwardIssueToWS")

regfile = RegisterFile(
    banks = 2,
    warps = 32,
    regs_per_warp = 64,
    threads_per_warp = 32
)

issue_stage = IssueStage(
    fust_latency_cycles = 1,
    regfile = regfile,
    fust = fust,
    name = "IssueStage",
    behind_latch = None,
    ahead_latch = None,
    forward_ifs_read = None,
    forward_ifs_write = {Issue_forward_to_WS.name: Issue_forward_to_WS}
)

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

def reset_issue_stage(issue_stage, regfile, fust):
    for k in fust:
        fust[k] = 0
    for _ in range(10):
        issue_stage.compute(None)



### DEFINED SMOKE TESTS ###
# TEST1: Issue instruction stream for one warp group until full, as fust for ADD FU is full.
def test_SMOKE_1(i: int) -> int:
    fust["ADD"] = 1
    Instructions = [
        Instruction(pc=0x0, intended_FU="ADD", warp_id=0, warp_group_id=0, rs1=10, rs2=11, rd=12, opcode="0000000", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x0, intended_FU="ADD", warp_id=1, warp_group_id=0, rs1=10, rs2=11, rd=12, opcode="0000000", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x4, intended_FU="SUB", warp_id=0, warp_group_id=0, rs1=5, rs2=6, rd=7, opcode="0000001", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x4, intended_FU="SUB", warp_id=1, warp_group_id=0, rs1=5, rs2=6, rd=7, opcode="0000001", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x8, intended_FU="MUL", warp_id=0, warp_group_id=0, rs1=20, rs2=21, rd=30, opcode="0000010", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x8, intended_FU="MUL", warp_id=1, warp_group_id=0, rs1=20, rs2=21, rd=30, opcode="0000010", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0xC, intended_FU="DIV", warp_id=0, warp_group_id=0, rs1=40, rs2=41, rd=42, opcode="0000011", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0xC, intended_FU="DIV", warp_id=1, warp_group_id=0, rs1=40, rs2=41, rd=42, opcode="0000011", rdat1=0, rdat2=0, wdat=0)
    ]
    print("================================== SMOKE TEST1 ==================================")
    print("Issue instruction stream for one warp group until full, as fust for ADD FU is full.")
    print("---------------------------------------------------------------------------------")
    for cycle in range(len(Instructions)):
        issue_stage.compute(Instructions[cycle])
        if   (cycle==0):
            assert issue_stage.iBufferCapacity[0] == 1
            assert issue_stage.staged_even == None
            assert issue_stage.staged_odd == None
            assert len(issue_stage.ready_to_dispatch) == 0
        elif (cycle==1):
            assert issue_stage.iBufferCapacity[0] == 1
            assert issue_stage.staged_even.pc == 0x0
            assert issue_stage.staged_even.intended_FU == "ADD"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 10
            assert issue_stage.staged_even.rs2 == 11
            assert issue_stage.staged_even.rd == 12
            assert issue_stage.staged_odd == None
            assert len(issue_stage.ready_to_dispatch) == 0
        elif (cycle==2):
            assert issue_stage.iBufferCapacity[0] == 1
            assert issue_stage.staged_even.pc == 0x0
            assert issue_stage.staged_even.intended_FU == "ADD"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 10
            assert issue_stage.staged_even.rs2 == 11
            assert issue_stage.staged_even.rd == 12
            assert issue_stage.staged_odd.pc == 0x0
            assert issue_stage.staged_odd.intended_FU == "ADD"
            assert issue_stage.staged_odd.warp_id == 1
            assert issue_stage.staged_odd.warp_group_id == 0
            assert issue_stage.staged_odd.rs1 == 10
            assert issue_stage.staged_odd.rs2 == 11
            assert issue_stage.staged_odd.rd == 12
            assert len(issue_stage.ready_to_dispatch) == 0
        elif (cycle==3):
            assert issue_stage.iBufferCapacity[0] == 1
            assert issue_stage.staged_even.pc == 0x4
            assert issue_stage.staged_even.intended_FU == "SUB"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 5
            assert issue_stage.staged_even.rs2 == 6
            assert issue_stage.staged_even.rd == 7
            assert issue_stage.staged_odd.pc == 0x0
            assert issue_stage.staged_odd.intended_FU == "ADD"
            assert issue_stage.staged_odd.warp_id == 1
            assert issue_stage.staged_odd.warp_group_id == 0
            assert issue_stage.staged_odd.rs1 == 10
            assert issue_stage.staged_odd.rs2 == 11
            assert issue_stage.staged_odd.rd == 12
            assert issue_stage.ready_to_dispatch[0].pc == 0x0
            assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
            assert issue_stage.ready_to_dispatch[0].warp_id == 0
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 10
            assert issue_stage.ready_to_dispatch[0].rs2 == 11
            assert issue_stage.ready_to_dispatch[0].rd == 12
        elif (cycle==4):
            assert issue_stage.iBufferCapacity[0] == 2
            assert issue_stage.staged_even.pc == 0x4
            assert issue_stage.staged_even.intended_FU == "SUB"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 5
            assert issue_stage.staged_even.rs2 == 6
            assert issue_stage.staged_even.rd == 7
            assert issue_stage.staged_odd.pc == 0x0
            assert issue_stage.staged_odd.intended_FU == "ADD"
            assert issue_stage.staged_odd.warp_id == 1
            assert issue_stage.staged_odd.warp_group_id == 0
            assert issue_stage.staged_odd.rs1 == 10
            assert issue_stage.staged_odd.rs2 == 11
            assert issue_stage.staged_odd.rd == 12
            assert issue_stage.ready_to_dispatch[0].pc == 0x0
            assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
            assert issue_stage.ready_to_dispatch[0].warp_id == 0
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 10
            assert issue_stage.ready_to_dispatch[0].rs2 == 11
            assert issue_stage.ready_to_dispatch[0].rd == 12
        elif (cycle==5):
            assert issue_stage.iBufferCapacity[0] == 3
            assert issue_stage.staged_even.pc == 0x4
            assert issue_stage.staged_even.intended_FU == "SUB"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 5
            assert issue_stage.staged_even.rs2 == 6
            assert issue_stage.staged_even.rd == 7
            assert issue_stage.staged_odd.pc == 0x0
            assert issue_stage.staged_odd.intended_FU == "ADD"
            assert issue_stage.staged_odd.warp_id == 1
            assert issue_stage.staged_odd.warp_group_id == 0
            assert issue_stage.staged_odd.rs1 == 10
            assert issue_stage.staged_odd.rs2 == 11
            assert issue_stage.staged_odd.rd == 12
            assert issue_stage.ready_to_dispatch[0].pc == 0x0
            assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
            assert issue_stage.ready_to_dispatch[0].warp_id == 0
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 10
            assert issue_stage.ready_to_dispatch[0].rs2 == 11
            assert issue_stage.ready_to_dispatch[0].rd == 12
        elif (cycle==6):
            assert issue_stage.iBufferCapacity[0] == 4
            assert issue_stage.staged_even.pc == 0x4
            assert issue_stage.staged_even.intended_FU == "SUB"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 5
            assert issue_stage.staged_even.rs2 == 6
            assert issue_stage.staged_even.rd == 7
            assert issue_stage.staged_odd.pc == 0x0
            assert issue_stage.staged_odd.intended_FU == "ADD"
            assert issue_stage.staged_odd.warp_id == 1
            assert issue_stage.staged_odd.warp_group_id == 0
            assert issue_stage.staged_odd.rs1 == 10
            assert issue_stage.staged_odd.rs2 == 11
            assert issue_stage.staged_odd.rd == 12
            assert issue_stage.ready_to_dispatch[0].pc == 0x0
            assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
            assert issue_stage.ready_to_dispatch[0].warp_id == 0
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 10
            assert issue_stage.ready_to_dispatch[0].rs2 == 11
            assert issue_stage.ready_to_dispatch[0].rd == 12
        elif (cycle==7):
            assert issue_stage.iBufferCapacity[0] == 4
            assert issue_stage.staged_even.pc == 0x4
            assert issue_stage.staged_even.intended_FU == "SUB"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 5
            assert issue_stage.staged_even.rs2 == 6
            assert issue_stage.staged_even.rd == 7
            assert issue_stage.staged_odd.pc == 0x0
            assert issue_stage.staged_odd.intended_FU == "ADD"
            assert issue_stage.staged_odd.warp_id == 1
            assert issue_stage.staged_odd.warp_group_id == 0
            assert issue_stage.staged_odd.rs1 == 10
            assert issue_stage.staged_odd.rs2 == 11
            assert issue_stage.staged_odd.rd == 12
            assert issue_stage.ready_to_dispatch[0].pc == 0x0
            assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
            assert issue_stage.ready_to_dispatch[0].warp_id == 0
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 10
            assert issue_stage.ready_to_dispatch[0].rs2 == 11
            assert issue_stage.ready_to_dispatch[0].rd == 12
        print(f"Cycle {i}")
        print("---------------------------------------------------------------------------------")
        print(f"iBuffer[0] content: {issue_stage.iBuffer[0]}")
        print("---------------------------------------------------------------------------------")
        print(f"Head of iBuffer[0]: {issue_stage.iBufferHead[0]}")
        print("---------------------------------------------------------------------------------")
        print(f"Staged Even Instruction: {issue_stage.staged_even}")
        print("---------------------------------------------------------------------------------")
        print(f"Staged Odd Instruction: {issue_stage.staged_odd}")
        print("---------------------------------------------------------------------------------")
        print(f"Ready to dispatch slot: {issue_stage.ready_to_dispatch}")
        print("---------------------------------------------------------------------------------")
        print()
        i=i+1
    print("\n\n")
    return i



# TEST2: Issue instruction stream for another warp group while the one is full.
def test_SMOKE_2(i: int) -> int:
    Instructions = [
        Instruction(pc=0x0, intended_FU="ADD", warp_id=2, warp_group_id=1, rs1=10, rs2=11, rd=12, opcode="0000000", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x0, intended_FU="ADD", warp_id=3, warp_group_id=1, rs1=10, rs2=11, rd=12, opcode="0000000", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x4, intended_FU="SUB", warp_id=2, warp_group_id=1, rs1=5, rs2=6, rd=7, opcode="0000001", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x4, intended_FU="SUB", warp_id=3, warp_group_id=1, rs1=5, rs2=6, rd=7, opcode="0000001", rdat1=0, rdat2=0, wdat=0)
    ]
    print("================================== SMOKE TEST2 ==================================")
    print("Issue instruction stream for another warp group while the one is full.")
    print("---------------------------------------------------------------------------------")
    for cycle in range(len(Instructions)):
        issue_stage.compute(Instructions[cycle])
        if   (cycle==0):
            assert issue_stage.iBufferCapacity[0] == 4
            assert issue_stage.iBufferCapacity[1] == 1
            assert issue_stage.staged_even.pc == 0x4
            assert issue_stage.staged_even.intended_FU == "SUB"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 5
            assert issue_stage.staged_even.rs2 == 6
            assert issue_stage.staged_even.rd == 7
            assert issue_stage.staged_odd.pc == 0x0
            assert issue_stage.staged_odd.intended_FU == "ADD"
            assert issue_stage.staged_odd.warp_id == 1
            assert issue_stage.staged_odd.warp_group_id == 0
            assert issue_stage.staged_odd.rs1 == 10
            assert issue_stage.staged_odd.rs2 == 11
            assert issue_stage.staged_odd.rd == 12
            assert issue_stage.ready_to_dispatch[0].pc == 0x0
            assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
            assert issue_stage.ready_to_dispatch[0].warp_id == 0
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 10
            assert issue_stage.ready_to_dispatch[0].rs2 == 11
            assert issue_stage.ready_to_dispatch[0].rd == 12
        elif (cycle==1):
            assert issue_stage.iBufferCapacity[0] == 4
            assert issue_stage.iBufferCapacity[1] == 2
            assert issue_stage.staged_even.pc == 0x4
            assert issue_stage.staged_even.intended_FU == "SUB"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 5
            assert issue_stage.staged_even.rs2 == 6
            assert issue_stage.staged_even.rd == 7
            assert issue_stage.staged_odd.pc == 0x0
            assert issue_stage.staged_odd.intended_FU == "ADD"
            assert issue_stage.staged_odd.warp_id == 1
            assert issue_stage.staged_odd.warp_group_id == 0
            assert issue_stage.staged_odd.rs1 == 10
            assert issue_stage.staged_odd.rs2 == 11
            assert issue_stage.staged_odd.rd == 12
            assert issue_stage.ready_to_dispatch[0].pc == 0x0
            assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
            assert issue_stage.ready_to_dispatch[0].warp_id == 0
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 10
            assert issue_stage.ready_to_dispatch[0].rs2 == 11
            assert issue_stage.ready_to_dispatch[0].rd == 12
        elif (cycle==2):
            assert issue_stage.iBufferCapacity[0] == 4
            assert issue_stage.iBufferCapacity[1] == 3
            assert issue_stage.staged_even.pc == 0x4
            assert issue_stage.staged_even.intended_FU == "SUB"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 5
            assert issue_stage.staged_even.rs2 == 6
            assert issue_stage.staged_even.rd == 7
            assert issue_stage.staged_odd.pc == 0x0
            assert issue_stage.staged_odd.intended_FU == "ADD"
            assert issue_stage.staged_odd.warp_id == 1
            assert issue_stage.staged_odd.warp_group_id == 0
            assert issue_stage.staged_odd.rs1 == 10
            assert issue_stage.staged_odd.rs2 == 11
            assert issue_stage.staged_odd.rd == 12
            assert issue_stage.ready_to_dispatch[0].pc == 0x0
            assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
            assert issue_stage.ready_to_dispatch[0].warp_id == 0
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 10
            assert issue_stage.ready_to_dispatch[0].rs2 == 11
            assert issue_stage.ready_to_dispatch[0].rd == 12
        elif (cycle==3):
            assert issue_stage.iBufferCapacity[0] == 4
            assert issue_stage.iBufferCapacity[1] == 4
            assert issue_stage.staged_even.pc == 0x4
            assert issue_stage.staged_even.intended_FU == "SUB"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 5
            assert issue_stage.staged_even.rs2 == 6
            assert issue_stage.staged_even.rd == 7
            assert issue_stage.staged_odd.pc == 0x0
            assert issue_stage.staged_odd.intended_FU == "ADD"
            assert issue_stage.staged_odd.warp_id == 1
            assert issue_stage.staged_odd.warp_group_id == 0
            assert issue_stage.staged_odd.rs1 == 10
            assert issue_stage.staged_odd.rs2 == 11
            assert issue_stage.staged_odd.rd == 12
            assert issue_stage.ready_to_dispatch[0].pc == 0x0
            assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
            assert issue_stage.ready_to_dispatch[0].warp_id == 0
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 10
            assert issue_stage.ready_to_dispatch[0].rs2 == 11
            assert issue_stage.ready_to_dispatch[0].rd == 12
        print(f"Cycle {i}")
        print("---------------------------------------------------------------------------------")
        print(f"iBuffer[0] content: {issue_stage.iBuffer[0]}")
        print("---------------------------------------------------------------------------------")
        print(f"Head of iBuffer[0]: {issue_stage.iBufferHead[0]}")
        print("---------------------------------------------------------------------------------")
        print(f"iBuffer[1] content: {issue_stage.iBuffer[1]}")
        print("---------------------------------------------------------------------------------")
        print(f"Head of iBuffer[1]: {issue_stage.iBufferHead[1]}")
        print("---------------------------------------------------------------------------------")
        print(f"Staged Even Instruction: {issue_stage.staged_even}")
        print("---------------------------------------------------------------------------------")
        print(f"Staged Odd Instruction: {issue_stage.staged_odd}")
        print("---------------------------------------------------------------------------------")
        print(f"Ready to dispatch slot: {issue_stage.ready_to_dispatch}")
        print("---------------------------------------------------------------------------------")
        print()
        i=i+1
    print("\n\n")
    return i



# TEST3: Allow instruction buffers to empty and all enqueued instructions to be dispatched.
def test_SMOKE_3(i: int) -> int:
    fust["ADD"] = 0
    print("================================== SMOKE TEST3 ==================================")
    print("Allow instruction buffers to empty and all enqueued instructions to be dispatched.")
    print("---------------------------------------------------------------------------------")
    for cycle in range(11):
        issue_stage.compute(None)
        if   (cycle==0):
            assert issue_stage.iBufferCapacity[0] == 3
            assert issue_stage.iBufferCapacity[1] == 4
            assert issue_stage.staged_even.pc == 0x4
            assert issue_stage.staged_even.intended_FU == "SUB"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 5
            assert issue_stage.staged_even.rs2 == 6
            assert issue_stage.staged_even.rd == 7
            assert issue_stage.staged_odd.pc == 0x4
            assert issue_stage.staged_odd.intended_FU == "SUB"
            assert issue_stage.staged_odd.warp_id == 1
            assert issue_stage.staged_odd.warp_group_id == 0
            assert issue_stage.staged_odd.rs1 == 5
            assert issue_stage.staged_odd.rs2 == 6
            assert issue_stage.staged_odd.rd == 7
            assert issue_stage.ready_to_dispatch[0].pc == 0x0
            assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
            assert issue_stage.ready_to_dispatch[0].warp_id == 1
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 10
            assert issue_stage.ready_to_dispatch[0].rs2 == 11
            assert issue_stage.ready_to_dispatch[0].rd == 12
        elif (cycle==1):
            assert issue_stage.iBufferCapacity[0] == 3
            assert issue_stage.iBufferCapacity[1] == 3
            assert issue_stage.staged_even.pc == 0x0
            assert issue_stage.staged_even.intended_FU == "ADD"
            assert issue_stage.staged_even.warp_id == 2
            assert issue_stage.staged_even.warp_group_id == 1
            assert issue_stage.staged_even.rs1 == 10
            assert issue_stage.staged_even.rs2 == 11
            assert issue_stage.staged_even.rd == 12
            assert issue_stage.staged_odd.pc == 0x4
            assert issue_stage.staged_odd.intended_FU == "SUB"
            assert issue_stage.staged_odd.warp_id == 1
            assert issue_stage.staged_odd.warp_group_id == 0
            assert issue_stage.staged_odd.rs1 == 5
            assert issue_stage.staged_odd.rs2 == 6
            assert issue_stage.staged_odd.rd == 7
            assert issue_stage.ready_to_dispatch[0].pc == 0x4
            assert issue_stage.ready_to_dispatch[0].intended_FU == "SUB"
            assert issue_stage.ready_to_dispatch[0].warp_id == 0
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 5
            assert issue_stage.ready_to_dispatch[0].rs2 == 6
            assert issue_stage.ready_to_dispatch[0].rd == 7
        elif (cycle==2):
            assert issue_stage.iBufferCapacity[0] == 3
            assert issue_stage.iBufferCapacity[1] == 2
            assert issue_stage.staged_even.pc == 0x0
            assert issue_stage.staged_even.intended_FU == "ADD"
            assert issue_stage.staged_even.warp_id == 2
            assert issue_stage.staged_even.warp_group_id == 1
            assert issue_stage.staged_even.rs1 == 10
            assert issue_stage.staged_even.rs2 == 11
            assert issue_stage.staged_even.rd == 12
            assert issue_stage.staged_odd.pc == 0x0
            assert issue_stage.staged_odd.intended_FU == "ADD"
            assert issue_stage.staged_odd.warp_id == 3
            assert issue_stage.staged_odd.warp_group_id == 1
            assert issue_stage.staged_odd.rs1 == 10
            assert issue_stage.staged_odd.rs2 == 11
            assert issue_stage.staged_odd.rd == 12
            assert issue_stage.ready_to_dispatch[0].pc == 0x4
            assert issue_stage.ready_to_dispatch[0].intended_FU == "SUB"
            assert issue_stage.ready_to_dispatch[0].warp_id == 1
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 5
            assert issue_stage.ready_to_dispatch[0].rs2 == 6
            assert issue_stage.ready_to_dispatch[0].rd == 7
        elif (cycle==3):
            assert issue_stage.iBufferCapacity[0] == 3
            assert issue_stage.iBufferCapacity[1] == 1
            assert issue_stage.staged_even.pc == 0x4
            assert issue_stage.staged_even.intended_FU == "SUB"
            assert issue_stage.staged_even.warp_id == 2
            assert issue_stage.staged_even.warp_group_id == 1
            assert issue_stage.staged_even.rs1 == 5
            assert issue_stage.staged_even.rs2 == 6
            assert issue_stage.staged_even.rd == 7
            assert issue_stage.staged_odd.pc == 0x0
            assert issue_stage.staged_odd.intended_FU == "ADD"
            assert issue_stage.staged_odd.warp_id == 3
            assert issue_stage.staged_odd.warp_group_id == 1
            assert issue_stage.staged_odd.rs1 == 10
            assert issue_stage.staged_odd.rs2 == 11
            assert issue_stage.staged_odd.rd == 12
            assert issue_stage.ready_to_dispatch[0].pc == 0x0
            assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
            assert issue_stage.ready_to_dispatch[0].warp_id == 2
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 1
            assert issue_stage.ready_to_dispatch[0].rs1 == 10
            assert issue_stage.ready_to_dispatch[0].rs2 == 11
            assert issue_stage.ready_to_dispatch[0].rd == 12
        elif (cycle==4):
            assert issue_stage.iBufferCapacity[0] == 3
            assert issue_stage.iBufferCapacity[1] == 0
            assert issue_stage.staged_even.pc == 0x4
            assert issue_stage.staged_even.intended_FU == "SUB"
            assert issue_stage.staged_even.warp_id == 2
            assert issue_stage.staged_even.warp_group_id == 1
            assert issue_stage.staged_even.rs1 == 5
            assert issue_stage.staged_even.rs2 == 6
            assert issue_stage.staged_even.rd == 7
            assert issue_stage.staged_odd.pc == 0x4
            assert issue_stage.staged_odd.intended_FU == "SUB"
            assert issue_stage.staged_odd.warp_id == 3
            assert issue_stage.staged_odd.warp_group_id == 1
            assert issue_stage.staged_odd.rs1 == 5
            assert issue_stage.staged_odd.rs2 == 6
            assert issue_stage.staged_odd.rd == 7
            assert issue_stage.ready_to_dispatch[0].pc == 0x0
            assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
            assert issue_stage.ready_to_dispatch[0].warp_id == 3
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 1
            assert issue_stage.ready_to_dispatch[0].rs1 == 10
            assert issue_stage.ready_to_dispatch[0].rs2 == 11
            assert issue_stage.ready_to_dispatch[0].rd == 12
        elif (cycle==5):
            assert issue_stage.iBufferCapacity[0] == 2
            assert issue_stage.iBufferCapacity[1] == 0
            assert issue_stage.staged_even.pc == 0x8
            assert issue_stage.staged_even.intended_FU == "MUL"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 20
            assert issue_stage.staged_even.rs2 == 21
            assert issue_stage.staged_even.rd == 30
            assert issue_stage.staged_odd.pc == 0x4
            assert issue_stage.staged_odd.intended_FU == "SUB"
            assert issue_stage.staged_odd.warp_id == 3
            assert issue_stage.staged_odd.warp_group_id == 1
            assert issue_stage.staged_odd.rs1 == 5
            assert issue_stage.staged_odd.rs2 == 6
            assert issue_stage.staged_odd.rd == 7
            assert issue_stage.ready_to_dispatch[0].pc == 0x4
            assert issue_stage.ready_to_dispatch[0].intended_FU == "SUB"
            assert issue_stage.ready_to_dispatch[0].warp_id == 2
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 1
            assert issue_stage.ready_to_dispatch[0].rs1 == 5
            assert issue_stage.ready_to_dispatch[0].rs2 == 6
            assert issue_stage.ready_to_dispatch[0].rd == 7
        elif (cycle==6):
            assert issue_stage.iBufferCapacity[0] == 1
            assert issue_stage.iBufferCapacity[1] == 0
            assert issue_stage.staged_even.pc == 0x8
            assert issue_stage.staged_even.intended_FU == "MUL"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 20
            assert issue_stage.staged_even.rs2 == 21
            assert issue_stage.staged_even.rd == 30
            assert issue_stage.staged_odd.pc == 0x8
            assert issue_stage.staged_odd.intended_FU == "MUL"
            assert issue_stage.staged_odd.warp_id == 1
            assert issue_stage.staged_odd.warp_group_id == 0
            assert issue_stage.staged_odd.rs1 == 20
            assert issue_stage.staged_odd.rs2 == 21
            assert issue_stage.staged_odd.rd == 30
            assert issue_stage.ready_to_dispatch[0].pc == 0x4
            assert issue_stage.ready_to_dispatch[0].intended_FU == "SUB"
            assert issue_stage.ready_to_dispatch[0].warp_id == 3
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 1
            assert issue_stage.ready_to_dispatch[0].rs1 == 5
            assert issue_stage.ready_to_dispatch[0].rs2 == 6
            assert issue_stage.ready_to_dispatch[0].rd == 7
        elif (cycle==7):
            assert issue_stage.iBufferCapacity[0] == 0
            assert issue_stage.iBufferCapacity[1] == 0
            assert issue_stage.staged_even.pc == 0xC
            assert issue_stage.staged_even.intended_FU == "DIV"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 40
            assert issue_stage.staged_even.rs2 == 41
            assert issue_stage.staged_even.rd == 42
            assert issue_stage.staged_odd.pc == 0x8
            assert issue_stage.staged_odd.intended_FU == "MUL"
            assert issue_stage.staged_odd.warp_id == 1
            assert issue_stage.staged_odd.warp_group_id == 0
            assert issue_stage.staged_odd.rs1 == 20
            assert issue_stage.staged_odd.rs2 == 21
            assert issue_stage.staged_odd.rd == 30
            assert issue_stage.ready_to_dispatch[0].pc == 0x8
            assert issue_stage.ready_to_dispatch[0].intended_FU == "MUL"
            assert issue_stage.ready_to_dispatch[0].warp_id == 0
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 20
            assert issue_stage.ready_to_dispatch[0].rs2 == 21
            assert issue_stage.ready_to_dispatch[0].rd == 30
        elif (cycle==8):
            assert issue_stage.iBufferCapacity[0] == 0
            assert issue_stage.iBufferCapacity[1] == 0
            assert issue_stage.staged_even.pc == 0xC
            assert issue_stage.staged_even.intended_FU == "DIV"
            assert issue_stage.staged_even.warp_id == 0
            assert issue_stage.staged_even.warp_group_id == 0
            assert issue_stage.staged_even.rs1 == 40
            assert issue_stage.staged_even.rs2 == 41
            assert issue_stage.staged_even.rd == 42
            assert issue_stage.staged_odd == None
            assert issue_stage.ready_to_dispatch[0].pc == 0x8
            assert issue_stage.ready_to_dispatch[0].intended_FU == "MUL"
            assert issue_stage.ready_to_dispatch[0].warp_id == 1
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 20
            assert issue_stage.ready_to_dispatch[0].rs2 == 21
            assert issue_stage.ready_to_dispatch[0].rd == 30
        elif (cycle==9):
            assert issue_stage.iBufferCapacity[0] == 0
            assert issue_stage.iBufferCapacity[1] == 0
            assert issue_stage.staged_even == None
            assert issue_stage.staged_odd == None
            assert issue_stage.ready_to_dispatch[0].pc == 0xC
            assert issue_stage.ready_to_dispatch[0].intended_FU == "DIV"
            assert issue_stage.ready_to_dispatch[0].warp_id == 0
            assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            assert issue_stage.ready_to_dispatch[0].rs1 == 40
            assert issue_stage.ready_to_dispatch[0].rs2 == 41
            assert issue_stage.ready_to_dispatch[0].rd == 42
        elif (cycle==10):
            assert issue_stage.iBufferCapacity[0] == 0
            assert issue_stage.iBufferCapacity[1] == 0
            assert issue_stage.staged_even == None
            assert issue_stage.staged_odd == None
            assert len(issue_stage.ready_to_dispatch) == 0
        print(f"Cycle {i}")
        print("---------------------------------------------------------------------------------")
        print(f"iBuffer[0] content: {issue_stage.iBuffer[0]}")
        print("---------------------------------------------------------------------------------")
        print(f"Head of iBuffer[0]: {issue_stage.iBufferHead[0]}")
        print("---------------------------------------------------------------------------------")
        print(f"iBuffer[1] content: {issue_stage.iBuffer[1]}")
        print("---------------------------------------------------------------------------------")
        print(f"Head of iBuffer[1]: {issue_stage.iBufferHead[1]}")
        print("---------------------------------------------------------------------------------")
        print(f"Staged Even Instruction: {issue_stage.staged_even}")
        print("---------------------------------------------------------------------------------")
        print(f"Staged Odd Instruction: {issue_stage.staged_odd}")
        print("---------------------------------------------------------------------------------")
        print(f"Ready to dispatch slot: {issue_stage.ready_to_dispatch}")
        print("---------------------------------------------------------------------------------")
        print()
        i=i+1
    print("\n\n")
    return i


# TEST4: Allow instruction buffers for all warp groups to fill up until no more instructions can be accepted, then drain all instruction buffers until empty.
def test_SMOKE_4():
    fust["ADD"] = 1
    Instructions = [
        Instruction(pc=0x0, intended_FU="ADD", warp_id=0, warp_group_id=0, rs1=10, rs2=11, rd=12, opcode="0000000", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x0, intended_FU="ADD", warp_id=1, warp_group_id=0, rs1=10, rs2=11, rd=12, opcode="0000000", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x4, intended_FU="SUB", warp_id=0, warp_group_id=0, rs1=5, rs2=6, rd=7, opcode="0000001", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x4, intended_FU="SUB", warp_id=1, warp_group_id=0, rs1=5, rs2=6, rd=7, opcode="0000001", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x8, intended_FU="MUL", warp_id=0, warp_group_id=0, rs1=20, rs2=21, rd=30, opcode="0000010", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x8, intended_FU="MUL", warp_id=1, warp_group_id=0, rs1=20, rs2=21, rd=30, opcode="0000010", rdat1=0, rdat2=0, wdat=0)
        # Instruction(pc=0xC, intended_FU="DIV", warp_id=0, warp_group_id=0, rs1=40, rs2=41, rd=42, opcode="0000011", rdat1=0, rdat2=0, wdat=0),
        # Instruction(pc=0xC, intended_FU="DIV", warp_id=1, warp_group_id=0, rs1=40, rs2=41, rd=42, opcode="0000011", rdat1=0, rdat2=0, wdat=0)
    ]
    ops = [
        (0x0, "ADD", 10, 11, 12, "0000000"),
        (0x4, "SUB", 5, 6, 7, "0000001"),
    ]
    for wg in range(1,16):
        for pc, fu, rs1, rs2, rd, opcode in ops:
            for warp_offset in range(2):
                warp_id = 2 * wg + warp_offset
                Instructions.append(
                    Instruction(
                        pc=pc, 
                        intended_FU=fu,
                        warp_id=warp_id,
                        warp_group_id=wg,
                        rs1=rs1, rs2=rs2, rd=rd,
                        opcode=opcode,
                        rdat1=0, rdat2=0, wdat=0
                    )
                )
    warp_num = 2
    warp_group_num = 1
    print("================================== SMOKE TEST4 ==================================")
    print("Allow instruction buffers for all warp groups to fill up until no more instructions ")
    print("can be accepted, then drain all instruction buffers until empty.")
    print("---------------------------------------------------------------------------------")
    for cycle in range(len(Instructions)*2):
        if cycle < len(Instructions):
            issue_stage.compute(Instructions[cycle])
        else:
            fust["ADD"] = 0
            issue_stage.compute(None)
        if (cycle >= len(Instructions)):
            if   (cycle == len(Instructions)):
                assert issue_stage.ready_to_dispatch[0].pc == 0x0
                assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
                assert issue_stage.ready_to_dispatch[0].warp_id == 1
                assert issue_stage.ready_to_dispatch[0].warp_group_id == 0 
            elif (cycle == len(Instructions)+1):
                assert issue_stage.ready_to_dispatch[0].pc == 0x4
                assert issue_stage.ready_to_dispatch[0].intended_FU == "SUB"
                assert issue_stage.ready_to_dispatch[0].warp_id == 0
                assert issue_stage.ready_to_dispatch[0].warp_group_id == 0 
            elif (cycle == len(Instructions)+2):
                assert issue_stage.ready_to_dispatch[0].pc == 0x4
                assert issue_stage.ready_to_dispatch[0].intended_FU == "SUB"
                assert issue_stage.ready_to_dispatch[0].warp_id == 1
                assert issue_stage.ready_to_dispatch[0].warp_group_id == 0 
            elif (cycle == len(Instructions)+3):
                assert issue_stage.ready_to_dispatch[0].pc == 0x0
                assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
                assert issue_stage.ready_to_dispatch[0].warp_id == 30
                assert issue_stage.ready_to_dispatch[0].warp_group_id == 15
            elif (cycle == len(Instructions)+4):
                assert issue_stage.ready_to_dispatch[0].pc == 0x0
                assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
                assert issue_stage.ready_to_dispatch[0].warp_id == 31
                assert issue_stage.ready_to_dispatch[0].warp_group_id == 15
            elif (cycle == len(Instructions)+5):
                assert issue_stage.ready_to_dispatch[0].pc == 0x4
                assert issue_stage.ready_to_dispatch[0].intended_FU == "SUB"
                assert issue_stage.ready_to_dispatch[0].warp_id == 30
                assert issue_stage.ready_to_dispatch[0].warp_group_id == 15
            elif (cycle == len(Instructions)+6):
                assert issue_stage.ready_to_dispatch[0].pc == 0x4
                assert issue_stage.ready_to_dispatch[0].intended_FU == "SUB"
                assert issue_stage.ready_to_dispatch[0].warp_id == 31
                assert issue_stage.ready_to_dispatch[0].warp_group_id == 15
            elif (cycle == len(Instructions)+7):
                assert issue_stage.ready_to_dispatch[0].pc == 0x8
                assert issue_stage.ready_to_dispatch[0].intended_FU == "MUL"
                assert issue_stage.ready_to_dispatch[0].warp_id == 0
                assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            elif (cycle == len(Instructions)+8):
                assert issue_stage.ready_to_dispatch[0].pc == 0x8
                assert issue_stage.ready_to_dispatch[0].intended_FU == "MUL"
                assert issue_stage.ready_to_dispatch[0].warp_id == 1
                assert issue_stage.ready_to_dispatch[0].warp_group_id == 0
            elif (cycle >= len(Instructions)+9 and cycle <= 2*len(Instructions)-2):
                if   (cycle % 4 == 0):
                    assert issue_stage.ready_to_dispatch[0].pc == 0x0
                    assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
                    assert issue_stage.ready_to_dispatch[0].warp_id == warp_num
                    assert issue_stage.ready_to_dispatch[0].warp_group_id == warp_group_num
                    warp_num = warp_num - 1
                elif (cycle % 4 == 1):
                    assert issue_stage.ready_to_dispatch[0].pc == 0x4
                    assert issue_stage.ready_to_dispatch[0].intended_FU == "SUB"
                    assert issue_stage.ready_to_dispatch[0].warp_id == warp_num
                    assert issue_stage.ready_to_dispatch[0].warp_group_id == warp_group_num
                    warp_num = warp_num + 1
                elif (cycle % 4 == 2):
                    assert issue_stage.ready_to_dispatch[0].pc == 0x4
                    assert issue_stage.ready_to_dispatch[0].intended_FU == "SUB"
                    assert issue_stage.ready_to_dispatch[0].warp_id == warp_num
                    assert issue_stage.ready_to_dispatch[0].warp_group_id == warp_group_num
                    warp_num = warp_num + 1
                    warp_group_num = warp_group_num + 1
                elif (cycle % 4 == 3):
                    assert issue_stage.ready_to_dispatch[0].pc == 0x0
                    assert issue_stage.ready_to_dispatch[0].intended_FU == "ADD"
                    assert issue_stage.ready_to_dispatch[0].warp_id == warp_num
                    assert issue_stage.ready_to_dispatch[0].warp_group_id == warp_group_num
                    warp_num = warp_num + 1

        print(f"Cycle {cycle}")
        print("---------------------------------------------------------------------------------")
        for i in range(16):
            print(f"iBuffer[{i}] content: {issue_stage.iBuffer[i]}")
            print("---------------------------------------------------------------------------------")
            print(f"Head of iBuffer[{i}]: {issue_stage.iBufferHead[i]}")
            print("---------------------------------------------------------------------------------")
        print(f"Staged Even Instruction: {issue_stage.staged_even}")
        print("---------------------------------------------------------------------------------")
        print(f"Staged Odd Instruction: {issue_stage.staged_odd}")
        print("---------------------------------------------------------------------------------")
        print(f"Ready to dispatch slot: {issue_stage.ready_to_dispatch}")
        print("---------------------------------------------------------------------------------")
        print(f"iBuffer Full Bit Vector: {issue_stage.iBuff_Full_Flags}")
        print("---------------------------------------------------------------------------------")
        print()
    print("\n\n")


# TEST5: Ensure that issue stage can handle back to back even and odd instructions in iBuffers.
def test_SMOKE_5():
    fust["ADD"] = 1
    Instructions = [
        Instruction(pc=0x0, intended_FU="ADD", warp_id=0, warp_group_id=0, rs1=10, rs2=11, rd=12, opcode="0000000", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x0, intended_FU="ADD", warp_id=1, warp_group_id=0, rs1=10, rs2=11, rd=12, opcode="0000000", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x4, intended_FU="SUB", warp_id=0, warp_group_id=0, rs1=5, rs2=6, rd=7, opcode="0000001", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x4, intended_FU="SUB", warp_id=1, warp_group_id=0, rs1=5, rs2=6, rd=7, opcode="0000001", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x8, intended_FU="MUL", warp_id=0, warp_group_id=0, rs1=20, rs2=21, rd=30, opcode="0000010", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x8, intended_FU="MUL", warp_id=1, warp_group_id=0, rs1=20, rs2=21, rd=30, opcode="0000010", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0xC, intended_FU="DIV", warp_id=0, warp_group_id=0, rs1=40, rs2=41, rd=42, opcode="0000011", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0xC, intended_FU="DIV", warp_id=1, warp_group_id=0, rs1=40, rs2=41, rd=42, opcode="0000011", rdat1=0, rdat2=0, wdat=0),

        Instruction(pc=0x0, intended_FU="ADD", warp_id=3, warp_group_id=1, rs1=10, rs2=11, rd=12, opcode="0000000", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x0, intended_FU="ADD", warp_id=2, warp_group_id=1, rs1=10, rs2=11, rd=12, opcode="0000000", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x4, intended_FU="SUB", warp_id=2, warp_group_id=1, rs1=5, rs2=6, rd=7, opcode="0000001", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x4, intended_FU="SUB", warp_id=3, warp_group_id=1, rs1=5, rs2=6, rd=7, opcode="0000001", rdat1=0, rdat2=0, wdat=0),

        Instruction(pc=0x0, intended_FU="ADD", warp_id=4, warp_group_id=2, rs1=10, rs2=11, rd=12, opcode="0000000", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x0, intended_FU="ADD", warp_id=5, warp_group_id=2, rs1=10, rs2=11, rd=12, opcode="0000000", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x4, intended_FU="SUB", warp_id=5, warp_group_id=2, rs1=5, rs2=6, rd=7, opcode="0000001", rdat1=0, rdat2=0, wdat=0),
        Instruction(pc=0x4, intended_FU="SUB", warp_id=4, warp_group_id=2, rs1=5, rs2=6, rd=7, opcode="0000001", rdat1=0, rdat2=0, wdat=0),
    ]
    print("================================== SMOKE TEST5 ==================================")
    print("Ensure that issue stage can handle back to back even and odd instructions in iBuffers.")
    print("Instructions 8 and 9 scrambled to create back to back evens in wg1's iBuffer.")
    print("Instructions 14 and 15 scrambled to create back to back evens in wg2's iBuffer.")
    print("---------------------------------------------------------------------------------")
    for cycle in range(len(Instructions)*2):
        if cycle == len(Instructions):
            fust["ADD"] = 0
        if cycle < len(Instructions):
            issue_stage.compute(Instructions[cycle])
        else:
            issue_stage.compute(None)
        print(f"Cycle {cycle}")
        print("---------------------------------------------------------------------------------")
        print(f"iBuffer[0] content: {issue_stage.iBuffer[0]}")
        print("---------------------------------------------------------------------------------")
        print(f"Head of iBuffer[0]: {issue_stage.iBufferHead[0]}")
        print("---------------------------------------------------------------------------------")
        print(f"iBuffer[1] content: {issue_stage.iBuffer[1]}")
        print("---------------------------------------------------------------------------------")
        print(f"Head of iBuffer[1]: {issue_stage.iBufferHead[1]}")
        print("---------------------------------------------------------------------------------")
        print(f"iBuffer[2] content: {issue_stage.iBuffer[2]}")
        print("---------------------------------------------------------------------------------")
        print(f"Head of iBuffer[2]: {issue_stage.iBufferHead[2]}")
        print("---------------------------------------------------------------------------------")
        print(f"Staged Even Instruction: {issue_stage.staged_even}")
        print("---------------------------------------------------------------------------------")
        print(f"Staged Odd Instruction: {issue_stage.staged_odd}")
        print("---------------------------------------------------------------------------------")
        print(f"Ready to dispatch slot: {issue_stage.ready_to_dispatch}")
        print("---------------------------------------------------------------------------------")
        print()
    print("\n\n")



def main(): 
    #ROOT = Path(__file__).resolve().parents[5]
    #out_path = ROOT / "gpu_sim/cyclesim/src/core/frontend/smoketest_issue_output.txt"
    #sys.stdout = open(out_path, "w")
    i=0
    i=test_SMOKE_1(i)
    i=test_SMOKE_2(i)
    i=test_SMOKE_3(i)
    test_SMOKE_4()
    test_SMOKE_5()
    print("All smoke tests concluded.")

if __name__ == "__main__":
    main()