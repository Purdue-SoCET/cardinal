import sys
import argparse
from pathlib import Path

# --- Path Setup ---
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# --- Imports ---
from common.custom_enums import *
from reg_file import *
from instr import *
from mem import *
from state import *
from thread import *

# --- Argument Parsing Helper ---
def parse_args():
    parser = argparse.ArgumentParser(
        description="RISC-V/GPU Emulator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Adding Arguments
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to the input binary or hex file"
    )
    parser.add_argument(
        "-t", "--threads-per-block",
        type=int,
        default=32,
        help="Number of threads per block (or per warp)"
    )
    parser.add_argument(
        "-b", "--num-blocks",
        type=int,
        default=1,
        help="Number of thread blocks to simulate"
    )
    parser.add_argument(
        "--start-pc",
        type=lambda x: int(x, 0), 
        default=0x0,
        help="Starting Program Counter address (hex or int)"
    )
    parser.add_argument(
        "--mem-format",
        choices=['bin', 'hex'],
        default='bin',
        help="Format of the input memory file"
    )
    parser.add_argument(
        "--arg-pointer",
        type=lambda x: int(x, 0),
        default=0x0,
        help="Pointer to arguments in memory"
    )

    return parser.parse_args()


# --- Main Execution ---
if __name__ == "__main__":
    args = parse_args()

    # Validation: Check if input file exists
    if not args.input_file.exists():
        print(f"Error: Input file '{args.input_file}' not found.")
        sys.exit(1)

    print(f"Starting Simulation: {args.input_file}")
    print(f"Threads: {args.threads_per_block} | Blocks: {args.num_blocks} | Start PC: {hex(args.start_pc)}")
    warps_per_block = (args.threads_per_block + 31) // 32

    # Shared State
    mem = Mem(args.start_pc, str(args.input_file), args.mem_format)

    for block_id, warp_id in [(b, w) for b in range(args.num_blocks) for w in range(warps_per_block)]:
        pfile = PredicateRegFile(threads_per_warp=32)

        rfiles = []
        states = []
        csr_files = []
        threads = []

        # Setup Warp
        for tid in range(32):
            rfiles.append(RegFile())
            states.append(State(memory=mem, rfile=rfiles[tid], pfile=pfile))
            csr_files.append(CsrRegFile(thread_id=(32*warp_id + tid), block_id=block_id, arg_ptr=args.arg_pointer))
            threads.append(Thread(state_data=states[tid], start_pc=args.start_pc, csr_file=csr_files[tid]))

        # Run Warp
        print(f"\n --- Starting Warp: {warp_id} in Block: {block_id} --- ")
        has_halted = False
        while(not has_halted):
            for thread in threads:
                thread_halted = thread.step_instruction()
                if(has_halted): assert(thread_halted) # Ensure once one halts all do
                has_halted = thread_halted

    mem.dump()

    print("Simulation Complete.")