import argparse
import re
import sys
from pathlib import Path

# --- CONFIGURATION ---
DUMP_FOLDER = "build/mem_dump"
ARGS_BASE_ADDR = 0x00100000
ARGS_SIZES = {"BFS": 0x40}

COMPILED_KERNELS = {
    "BFS_1": "compiled/BFS_1.hex",
    "BFS_2": "compiled/BFS_2.hex",
}

STAGES = [
    ("Input", "BFSInput"),
    ("Mid", "BFSMid"),
    ("Output", "BFSOutput"),
]

def parse_dimensions(file_path):
    grid_dims = []
    block_dims = []
    pattern = r"Grid:\s*(\d+),\s*Block:\s*(\d+)"

    try:
        if not Path(file_path).exists():
            print(f"Error: Thread log '{file_path}' not found.")
            return [], []
            
        with open(file_path, 'r') as file:
            for line in file:
                match = re.search(pattern, line)
                if match:
                    grid_dims.append(int(match.group(1)))
                    block_dims.append(int(match.group(2)))
    except Exception as e:
        print(f"Error parsing dimensions: {e}")
    return grid_dims, block_dims

def load_instructions(path):
    memory_map = {}
    try:
        with open(path, 'r') as f:
            addr = 0x24
            for line in f:
                clean_line = line.strip()
                if not clean_line: continue
                parts = clean_line.split()
                hex_val = parts[0].replace("0x", "")
                memory_map[addr] = hex_val.upper()
                addr += 4
    except FileNotFoundError:
        print(f"Warning: Missing instruction file: {path}")
    return memory_map

def stitch_system_memory(kernel_key, dump_dir, output_file, stage_prefix, pass_idx,
                         block_dim, grid_dim, args_addr, args_size):
    """Combines instructions and metadata with data matching specific stage and pass."""
    
    # 1. Start with base instructions
    memory_map = load_instructions(COMPILED_KERNELS[kernel_key])
    dump_path = Path(dump_dir)
    
    # 2. Strict Filter: Match prefix + pass index (e.g., BFSInput0)
    # This prevents BFSInput10 from matching BFSInput1
    match_pattern = f"{stage_prefix}{pass_idx}"
    
    # Look for files in the dump directory
    if dump_path.exists():
        for file_path in dump_path.iterdir():
            # Check if filename starts with our exact Stage+Pass combo
            # and is followed by either a digit, an underscore, or the end of string
            # This handles "BFSInput0_args.txt" and "BFSInput0_0.txt"
            if file_path.name.startswith(match_pattern):
                # Extra safety: Ensure it's not a different pass (e.g., BFSInput0 vs BFSInput01)
                # We check the character immediately following the match_pattern
                remainder = file_path.name[len(match_pattern):]
                if remainder == "" or not remainder.isdigit():
                    
                    try:
                        with open(file_path, "r") as f:
                            for line in f:
                                content = line.strip()
                                if not content: continue
                                
                                parts = content.split()
                                if len(parts) >= 2:
                                    addr = int(parts[0], 16)
                                    val = parts[1]
                                    memory_map[addr] = val.upper()
                    except Exception as e:
                        print(f"  [!] Error reading {file_path.name}: {e}")

    # 3. Inject Metadata (0x00 - 0x20)
    entry_point = 0x00000024
    total_threads = block_dim * grid_dim

    memory_map[0x00] = "00000000"
    memory_map[0x04] = "00000000"
    memory_map[0x08] = "00000000"
    memory_map[0x0C] = f"{entry_point:08X}"
    memory_map[0x10] = f"{block_dim:08X}"
    memory_map[0x14] = f"{grid_dim:08X}"
    memory_map[0x18] = f"{total_threads:08X}"
    memory_map[0x1C] = f"{args_addr:08X}"
    memory_map[0x20] = f"{args_size:08X}"

    # 4. Write final hex
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        for addr in sorted(memory_map.keys()):
            val_str = memory_map[addr]
            f.write(f"0x{addr:08X} 0x{val_str:0>8}\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kernel_name", help="BFS")
    parser.add_argument("thread_log", help="build/threads/BFSThreads.txt")
    parser.add_argument("-n", "--numPasses", type=int, default=None)
    args = parser.parse_args()

    k_grid, k_block = parse_dimensions(args.thread_log)
    num_to_process = args.numPasses if args.numPasses is not None else len(k_grid)

    if num_to_process == 0:
        print("No passes found to process.")
        return

    print(f"Processing {num_to_process} passes for kernel: {args.kernel_name}")

    for i in range(num_to_process):
        b_dim = k_block[i] if i < len(k_block) else k_block[-1]
        g_dim = k_grid[i] if i < len(k_grid) else k_grid[-1]

        for stage_name, prefix in STAGES:
            output_filename = f"build/{args.kernel_name}_{stage_name}_pass{i}_t{b_dim}_b{g_dim}.hex"
            
            # Select kernel instruction set
            kernel_key = f"{args.kernel_name}_1" if stage_name != "Output" else f"{args.kernel_name}_2"

            stitch_system_memory(
                kernel_key,
                DUMP_FOLDER,
                output_filename,
                prefix, # e.g. "BFSInput"
                i,      # e.g. 0
                b_dim,
                g_dim,
                ARGS_BASE_ADDR,
                ARGS_SIZES.get(args.kernel_name, 0x40)
            )
        print(f"  -> Finished Pass {i}")

    print("\nStitching complete.")

if __name__ == "__main__":
    main()