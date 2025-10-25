import sys
from pathlib import Path
from reg_file import * 
from instr import *
from warp import *
from mem import *
from csr_file import *
sys.path.append(str(Path(__file__).parent.parent.parent))

from common import custom_enums

# thread block scheduler
def tbs(x, y, z):
    blocksize = x*y*z

    if blocksize > 1024:
        print("fuck you 3")
        sys.exit(1)

    csrs = []
    # Build coordinates once and slice into chunks
    X = [i % x for i in range(blocksize)]
    Y = [(i // x) % y for i in range(blocksize)]
    Z = [i // (x * y) for i in range(blocksize)]
    TID = list(range(blocksize))

    for w, start in enumerate(range(0, blocksize, 32)):
        end = min(start + 32, blocksize)
        chunk_x = X[start:end]
        chunk_y = Y[start:end]
        chunk_z = Z[start:end]
        chunk_t = TID[start:end]

        # Optional padding of the final partial warp
        if True and end - start < 32:
            pad_len = 32 - (end - start)
            chunk_x += [None] * pad_len
            chunk_y += [None] * pad_len
            chunk_z += [None] * pad_len
            chunk_t += [None] * pad_len

        csrs.append({
            "warp_id": w,
            "x": chunk_x,
            "y": chunk_y,
            "z": chunk_z,
            "tid": chunk_t,
            "lanes": list(range(len(chunk_x))) if not True else list(range(32)),
        })

    return csrs


# actual emulator
def emulator(input_file, warp, mem):
    with open(input_file, "r") as f:
        instructions = f.readlines()

    ### STARTING PC IS ASSUMED ZERO FOR NOW BUT UPDATE IT ACCORDING TO WHAT SOFTWARE GIVES US
    pc = warp.pc.int
    halt = False
    pred_reg_file = Predicate_Reg_File()
    while not halt and pc < len(instructions) * 4:
        for thread_id in range(64): 
            pc = warp.pc.int
            line = instructions[int(pc / 4)].strip()
            # remove inline comments before parsing
            for marker in ("//", "#"):
                idx = line.find(marker)
                if idx != -1:
                    line = line[:idx]
            line = line.strip()

            # skip empty/comment-only lines
            if not line:
                continue

            # decode
            opcode = Bits(bin=line[25:29], length=4) # bits 31:27
            funct3 = Bits(bin=line[29:32], length=3) # bits 26:24
            # print({line})
            # print(f'instr_type={instr_type}')
            # print(f'funct={funct.bin}')
            #(rs1, rs2, rd, imm) = parser.py
            # print({Instr_Type.R_TYPE.value})
            rs2 = Bits(bin=line[8:13], length=6) #24:19
            rs1 = Bits(bin=line[13:19], length=6) #18:13
            rd = Bits(bin=line[19:25], length=6) #12:7
            imm = Bits(bin=line[8:13], length=6) #default (I-Type). Make sure to shift for B-type
            pred = Bits(bin=line[2:8], length=5)
            match Instr_Type(opcode):
                case Instr_Type.R_TYPE_0:
                    op = R_Op_0(funct3)
                    instr = R_Instr_0(op=op, rs1=rs1, rs2=rs2, rd=rd)
                    print(f"rtype_0, funct={op}")  
                case Instr_Type.R_TYPE_1:
                    op = R_Op_1(funct3)
                    instr = R_Instr_1(op=op, rs1=rs1, rs2=rs2, rd=rd)
                    print(f"rtype_1, funct={op}")  
                case Instr_Type.I_TYPE_0:
                    op = I_Op_0(funct3)
                    instr = I_Instr_0(op=op, rs1=rs1, imm=imm, rd=rd)
                    print(f"itype_0, funct={op},imm={imm.int}")
                case Instr_Type.I_TYPE_1:
                    op = I_Op_1(funct3)
                    instr = I_Instr_1(op=op, rs1=rs1, imm=imm, rd=rd)
                    print(f"itype_1, funct={op},imm={imm.int}")
                case Instr_Type.I_TYPE_2:
                    op = I_Op_2(funct3)
                    instr = I_Instr_2(op=op, rs1=rs1, imm=imm, rd=rd, pc=pc)
                    print(f"itype_2, funct={op}")
                case Instr_Type.S_TYPE_0:
                    op = S_Op_0(funct3)
                    rs2 = imm #reads rs2 in imm spot
                    mem = rd #reads imm in the normal rd spot
                    instr = S_Instr_0(op=op, rs1=rs1, rs2=rs2, imm=mem)
                    print(f"stype_0, funct={op},imm={imm.int}")
                case Instr_Type.B_TYPE_0:
                    op = B_Op_0(funct3)
                    instr = B_Instr_0(op=op, rs1=rs1, rs2=rs2, pred_reg_file=rd)
                    print(f"btype, funct={op}")
                case Instr_Type.U_TYPE:
                    op = U_Op(funct3)
                    imm = imm + rs1 #concatenate
                    instr = U_Instr(op=op, imm=imm, rd=rd)
                    print(f"utype, funct={op},imm={imm.int}")
                case Instr_Type.J_TYPE:
                    op = J_Op(funct3)
                    imm = rs1 + rs2 + pred #concatenate
                    instr = J_Instr(op=op, rd=rd, imm=imm, pc=pc, pred_reg_file=pred_reg_file)
                    print("jtype")
                case Instr_Type.P_TYPE:
                    op = P_Op(funct3)
                    print("ptype")
                case Instr_Type.C_TYPE:
                    op = C_Op(funct3)
                    print("ctype")
                case Instr_Type.F_TYPE:
                    op = F_Op(funct3)
                    instr = F_Instr(op=op, rs1=rs1, rd=rd)
                    print(f"ftype, funct={op},imm={imm.int}")
                case Instr_Type.H_TYPE:
                    print(f"halt")
                case _:
                    print("Undefined opcode")
            # pc += 4 # NOTE: temporary until PC incrementing is figured out. How will this change with scheduling?
            warp.eval(instr=instr, pred_reg_file=pred_reg_file, thread_id=thread_id) #how to pass in mem, when different eval want/don't want it?
            # print(f"pc={warp.pc.int}")
        # return
    return

# main function
if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("fuck u lol")
        sys.exit(1)

    input_file = Path(sys.argv[1])

    if not input_file.exists():
        print("fuck u again lol")
        sys.exit(1)

    csrs = tbs(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    warp = Warp(0, Bits(int=int(sys.argv[5]), length=32), csrs[0])
    mem = Mem(0, sys.argv[1])
    emulator(sys.argv[1], warp, mem)
