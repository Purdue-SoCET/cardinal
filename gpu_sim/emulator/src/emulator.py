import sys
from pathlib import Path

# Add project root to path for imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from common.custom_enums import *
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
    while not halt and warp.pc.int < 29 * 4:#len(instructions) * 4:
        pc = warp.pc.int
        line = instructions[int(pc / 4)].strip()
        # remove inline comments before parsing
        for marker in ("//", "#"):
            idx = line.find(marker)
            if idx != -1:
                line = line[:idx]
        line = line.strip()
        if(sys.argv[6] == "hex"):
            line = Bits(hex=line, length=32)
        else:
            line = Bits(bin=line, length=32)
        # skip empty/comment-only lines
        if not line:
            continue

        # decode
        instr = I_Instr_0(op=I_Op_0.ADDI, rd=Bits(uint=0, length=5), rs1=Bits(uint=0, length=5), imm=Bits(int=0, length=12)) #NOP
        instr.decode(instruction=line,pc=warp.pc.int)
        # pc += 4 # NOTE: temporary until PC incrementing is figured out. How will this change with scheduling?
        halt = warp.eval(instr=instr, pred_reg_file=pred_reg_file, mem=mem) #how to pass in mem, when different eval want/don't want it?
        print(f"pc={warp.pc.int}, pred={pred_reg_file.arr}")
        if(halt):
            print("halted")
            break
    return

#pretty up code goal:
        
        #instr.fetch 
        #instr.decode
        #warp.eval(instr=instr)

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
    mem = Mem(int(sys.argv[5]), sys.argv[1])
    emulator(sys.argv[1], warp, mem)
