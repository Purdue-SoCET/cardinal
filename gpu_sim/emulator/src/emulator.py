import sys
from pathlib import Path
from reg_file import * 
from instr import *
from warp import *
from mem import *

sys.path.append(str(Path(__file__).resolve().parents[2]))

from custom_enums import *
# print csr helper
def print_csr(csr):
    for i in range(len(csr["x"])):
        print(f"lane {i:2d}: (z={csr['z'][i]}, y={csr['y'][i]}, x={csr['x'][i]})")


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

    while not halt and pc < len(instructions):
        line = instructions[pc].strip()

        print(line)
        #compiler is big endian:MSB at smallest addr. That, or you can consider
        #no, compiler just put opcode, LSB, at the left for the teal card. So it is small endian...
        #python parses with highest index at the left 
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
        # imm = Bits(bin=line[]) #
        match Instr_Type(instr_type):
            case Instr_Type.R_TYPE_0:
                op = R_Op_0(funct3)
                instr = R_Instr_0(op=op, rs1=rs1, rs2=rs2, rd=rd)
                print(f"rtype_0, funct={op}={funct3}")  
            case Instr_Type.R_TYPE_1:
                op = R_Op_1(funct3)
                instr = R_Instr_1(op=op, rs1=rs1, rs2=rs2, rd=rd)
                print(f"rtype_1, {op}")  
            case Instr_Type.I_TYPE_0:
                op = I_Op_0(funct3)
                # instr = I_Type_0(op=op, rs1, imm=imm, rd=rd)
                print("itype_0")
            case Instr_Type.I_TYPE_1:
                print("itype_1")
            case Instr_Type.I_TYPE_2:
                print("itype_2")
            case Instr_Type.S_TYPE_0:
                print("stype_0")
            case Instr_Type.S_TYPE_1:
                print("stype_1")
            case Instr_Type.B_TYPE_0:
                print("btype")
            case Instr_Type.B_TYPE_1:
                print("btype")
            case Instr_Type.U_TYPE:
                print("utype")
            case Instr_Type.J_TYPE:
                print("jtype")
            case Instr_Type.P_TYPE:
                print("ptype")
            case Instr_Type.C_TYPE:
                print("ctype")
            case _:
                print("Undefined opcode")

        return
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
    mem = Mem()
    emulator(sys.argv[1], warp, mem)
