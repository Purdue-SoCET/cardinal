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
from warp import *
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

    # Creating the Common State
    mem = Mem(args.start_pc, str(args.input_file))
    pfile = PredicateRegFile(thread_per_warp=(args.threads_per_block * args.num_blocks)) # For now, creating one mega threadblock-warp for predicates
    rfile = RegFile() # Only for one thread, needs to be reset every new thread...
    state = State(memory=mem, reg_file=rfile, pred_file=pfile)

    # Go through each block and thread
    for block_id, thread_id in [(b, t) for b in range(args.num_blocks) for t in range(args.threads_per_block)]:
        csr_file = CsrRegFile(thread_id=thread_id, block_id=block_id, arg_ptr=args.arg_pointer)
        thread = Thread(state_data=state, start_pc=args.start_pc, csr_file=csr_file)
        thread.run_until_halt()

        # Reset the register file for the next thread
        state.reg_file = RegFile()

    print("Simulation Complete.")