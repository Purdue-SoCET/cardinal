# test_issue_stage.py
"""
Standalone test for IssueStage logic, ported from the bottom of issue.py.
This script can be run directly to test IssueStage behavior.
"""
from latch_forward_stage import ForwardingIF, Instruction
from regfile import RegisterFile
from issue import IssueStage

# Simulate FUST (Functional Unit Status Table)
fust = {"ADD": 0, "SUB": 0, "MUL": 0, "DIV": 0, "SQRT": 0, "LDST": 0}

Issue_forward_to_WS = ForwardingIF(name = "ForwardIssueToWS")

regfile = RegisterFile(
    banks = 2,
    warps = 4,
    regs_per_warp = 4,
    threads_per_warp = 2
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

instructions = [
    Instruction(pc=0x0, intended_FU="ADD", warp_id=0, warp_group_id=0, rs1=2, rs2=3, rd=1, opcode="0000000", rdat1=0, rdat2=0, wdat=0),
    Instruction(pc=0x0, intended_FU="ADD", warp_id=1, warp_group_id=0, rs1=2, rs2=3, rd=1, opcode="0000000", rdat1=0, rdat2=0, wdat=0),
    Instruction(pc=0x4, intended_FU="MUL", warp_id=0, warp_group_id=0, rs1=0, rs2=1, rd=2, opcode="0000010", rdat1=0, rdat2=0, wdat=0),
    Instruction(pc=0x4, intended_FU="MUL", warp_id=1, warp_group_id=0, rs1=0, rs2=1, rd=2, opcode="0000010", rdat1=0, rdat2=0, wdat=0),
    Instruction(pc=0x8, intended_FU="DIV", warp_id=0, warp_group_id=0, rs1=0, rs2=1, rd=2, opcode="1111111", rdat1=0, rdat2=0, wdat=0),
    Instruction(pc=0x8, intended_FU="DIV", warp_id=1, warp_group_id=0, rs1=0, rs2=1, rd=2, opcode="1111111", rdat1=0, rdat2=0, wdat=0),
    Instruction(pc=0xC, intended_FU="SQRT", warp_id=0, warp_group_id=0, rs1=0, rs2=1, rd=2, opcode="1010101", rdat1=0, rdat2=0, wdat=0),
    Instruction(pc=0xC, intended_FU="SQRT", warp_id=1, warp_group_id=0, rs1=0, rs2=1, rd=2, opcode="1010101", rdat1=0, rdat2=0, wdat=0),
    Instruction(pc=0x10, intended_FU="SUB", warp_id=0, warp_group_id=0, rs1=0, rs2=1, rd=2, opcode="1110111", rdat1=0, rdat2=0, wdat=0),
    Instruction(pc=0x10, intended_FU="SUB", warp_id=1, warp_group_id=0, rs1=0, rs2=1, rd=2, opcode="1110111", rdat1=0, rdat2=0, wdat=0),
]

for cycle in range(20):
    if cycle == 0:
        fust["ADD"] = 1  # busy
    elif cycle == 7:
        fust["ADD"] = 0  # free
    if cycle < len(instructions):
        issue_stage.compute(instructions[cycle])
    else:
        issue_stage.compute(None)

for i in range(len(instructions)):
    print(instructions[i].rdat1, instructions[i].rdat2)
