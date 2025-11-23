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
    print(f"blockdim = {blockdim}, gridsize = {gridsize}")
    if totalsize > 1024:
        print("fuck you 3")
        sys.exit(1)

    csrs = []

    for w, gid_start in enumerate(range(0, totalsize, 32)):
        tb_id = gid_start // blockdim
        tid = [id for id in range(w*32-tb_id*blockdim, w*32+32-tb_id*blockdim)]
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
    halt_count = 0 #number of warps that have halted
    
    for warp_id in range(32): #declare all warps in a threadblock, each with own csr and pred_rf
        threadblock[warp_id] = Warp(warp_id=warp_id, pc=Bits(int=int(sys.argv[4]), length=32), csr=csrs[warp_id])
        thread_pred_RFs[warp_id] = Predicate_Reg_File()
    #!WARP SCHEDULING! currently has SIMD/lockstep warps
    while(halt_count < 32): #assuming 32 warps must halt
        for warp_id in range(32): #execute one warp at a time
            warp = threadblock[warp_id]
            pred_reg_file = thread_pred_RFs[warp_id]
            if(warp.halt_status is False):
                assert(threadblock[warp_id].halt_status is False)
                print(f"warp_id={warp_id}")
                pc = warp.pc.int
                
                instr_bin = fetch(instructions, pc)
                
                instr = I_Instr_0(op=I_Op_0.ADDI, rd=Bits(uint=0, length=5), rs1=Bits(uint=0, length=5), imm=Bits(int=0, length=12)) #NOP
                instr = instr.decode(instruction=instr_bin,pc=warp.pc)
                
                threadblock[warp_id] = warp.eval(instr=instr, pred_reg_file=pred_reg_file, mem=mem, csr=csrs[warp_id]) #update threadblock warp
                
                print(f"Next_pc={warp.pc.int}")
                if(threadblock[warp_id].halt_status): #this gets updated and hit only after first halt
                    halt_count += 1
                    print(f"halt_count={halt_count}")
                print()
            # else:

    return

# main function
if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("fuck u lol") #dan's code
        sys.exit(1)

    input_file = Path(sys.argv[1])

    if not input_file.exists():
        print("fuck u again lol")
        sys.exit(1)
    mem = Mem(int(sys.argv[4]), sys.argv[1])
    print(mem.memory)
    emulator(sys.argv[1], mem)
