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
def fetch(instructions, pc: int):
    line = instructions[int(pc / 4)].strip()
    for marker in ("//", "#"):
        idx = line.find(marker)
        if idx != -1:
            line = line[:idx]
        line = line.strip()
    if(sys.argv[5] == "hex"):
        line = Bits(hex=line, length=32)
    else:
        line = Bits(bin=line, length=32)
    return line
# thread block scheduler RIGHT NOT ONLY WORKS FOR TOTAL GLOBAL THREADS <= 1024, probably have to change main function to get that real functionality
#32 threads per warp, 32 warps per threadblock. currently 1 threadblock
def tbs(blockdim, gridsize): 
    totalsize = blockdim * gridsize #

    if totalsize > 1024:
        print("fuck you 3")
        sys.exit(1)

    csrs = []

    for w, gid_start in enumerate(range(0, totalsize, 32)):
        tb_id = gid_start // blockdim
        tid = [id for id in range(w-tb_id*blockdim, w+32-tb_id*blockdim)]
        # tb_id = global_tb_id // 1024 #assumes each threadblock has 1024 (max threads)
        # tid = global_tb_id % 32
        
        csrs.append({
            "warp_id": w,
            "tb_id": tb_id,
            "tid": tid
        })

    return csrs


# actual emulator
def emulator(input_file, mem):
    with open(input_file, "r") as f:
        instructions = f.readlines()
    csrs = tbs(int(sys.argv[2]), int(sys.argv[3]))

    threadblock = [0] * 32
    thread_pred_RFs = [0] * 32
    
    for warp_id in range(32): #declare all warps in a threadblock, each with own csr and pred_rf
        threadblock[warp_id] = Warp(warp_id=warp_id, pc=Bits(int=int(sys.argv[4]), length=32), csr=csrs[warp_id])
        thread_pred_RFs[warp_id] = Predicate_Reg_File()

    for warp_id in range(32): #execute one warp at a time
        warp = threadblock[warp_id]
        pred_reg_file = thread_pred_RFs[warp_id]
        print(warp_id)
        halt = False    
        while(halt is False and warp.pc.int < 29 * 4): #while one warp has not halted or past instr mem
            pc = warp.pc.int
            instr_bin = fetch(instructions, pc)

            # decode
            instr = I_Instr_0(op=I_Op_0.ADDI, rd=Bits(uint=0, length=5), rs1=Bits(uint=0, length=5), imm=Bits(int=0, length=12)) #NOP
            instr = instr.decode(instruction=instr_bin,pc=warp.pc)
            # pc += 4 # NOTE: temporary until PC incrementing is figured out. How will this change with scheduling?
            halt = warp.eval(instr=instr, pred_reg_file=pred_reg_file, mem=mem) #how to pass in mem, when different eval want/don't want it?
            print(f"pc={warp.pc.int}")
            if(halt):
                print("halted")
    return

# main function
if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("fuck u lol")
        sys.exit(1)

    input_file = Path(sys.argv[1])

    if not input_file.exists():
        print("fuck u again lol")
        sys.exit(1)
    mem = Mem(int(sys.argv[4]), sys.argv[1])
    emulator(sys.argv[1], mem)
