from pathlib import Path
import argparse
import re

def parse_dimensions(file_path):
    """
    Parses a text file and returns two separate lists for 
    Grid Dimensions and Block Dimensions.
    """
    grid_dims = []
    block_dims = []
    
    pattern = r"Grid Dim:\s*(\d+),\s*Block Dim:\s*(\d+)"
    
    try:
        with open(file_path, 'r') as file:
            for line in file:
                match = re.search(pattern, line)
                if match:
                    grid_dims.append(int(match.group(1)))
                    block_dims.append(int(match.group(2)))
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return [], []
    
    return grid_dims, block_dims

parser1 = argparse.ArgumentParser()

parser1.add_argument("kernel", type=str)  
parser1.add_argument("kernel_t", type=str)  
parser1.add_argument("--big_endian", type=bool)
args = parser1.parse_args()

kernel_grid, kernel_block = parse_dimensions(args.kernel_t)


# --- Configuration ---
compiled = {
    args.kernel: f"compiled/{args.kernel}.bin",
}

args_sizes = {args.kernel: 0x0C} #need to fix this
block_dims = {args.kernel: kernel_block} 
grid_dims  = {args.kernel: kernel_grid} 
big_endian_values = args.big_endian if args.big_endian is not None else False

ARGS_BASE_ADDR = 0x00100000 
DUMP_FOLDER = "build/mem_dump"

def stitch_system_memory(kernel_key, dump_dir, output_file, filter_prefix, is_input, block_dim, grid_dim, args_addr, args_size):
    memory_map = {} 

    # 1. Load Instructions
    path = compiled[kernel_key]
    try:
        with open(path, 'r') as f:
            addr = 0x24  
            
            for line in f:
                val = line.strip()
                
                if not val:
                    continue
                    
                memory_map[addr] = val.upper()
            
                addr += 4
    except FileNotFoundError:
        print(f"Warning: Could not find text file for {kernel_key} at {path}")

    dump_path = Path(dump_dir)
    found_files = list(dump_path.glob(f"{filter_prefix}*"))
        
    for file_path in found_files:
        with open(file_path, "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) == 2:
                    addr = int(parts[0], 16)
                    val = parts[1]
                    if big_endian_values:
                        chunks = [val[i:i+8] for i in range(0, len(val), 8)]
                        val = "".join(chunks[::-1]) 
                    memory_map[addr] = val.upper()

    # 3. Setup MMIO (Registers 0x00 to 0x20)
    entry_point = 0x00000024 # Standard entry
    total_threads = block_dim * grid_dim
    
    # We write these to the map. If it's an output dump, status is "Done"
    status  = "00000000000000000000000000000011" if not is_input else "00000000000000000000000000000000"
    control = "00000000000000000000000000000000" if not is_input else "00000000000000000000000000000001"

    memory_map[0x00] = control
    memory_map[0x04] = status
    memory_map[0x08] = "00000000000000000000000000000000" 
    memory_map[0x0C] = f"{entry_point:032b}"
    memory_map[0x10] = f"{block_dim:032b}"
    memory_map[0x14] = f"{grid_dim:032b}"
    memory_map[0x18] = f"{total_threads:032b}"
    memory_map[0x1C] = f"{args_addr:032b}"
    memory_map[0x20] = f"{args_size:032b}"

    # 4. Write sorted output
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        for addr in sorted(memory_map.keys()):
            f.write(f"0x{addr:08X} {memory_map[addr]}\n")

    print(f"Done: {output_file}")

# --- Execution Loop ---
# j=0: Input (Ready to run), j=1: Output (Post-simulation state)
for j in range(2):
    args_addr = ARGS_BASE_ADDR
    is_input = (j == 0)
    mode_str = "Input" if is_input else "Output"
    
    s_prefix = f"{args.kernel}{mode_str}"
    stitch_system_memory(args.kernel, DUMP_FOLDER, f"build/{s_prefix}_memDump_{block_dims[args.kernel]}.txt", 
                         s_prefix, is_input, block_dims[args.kernel][0], grid_dims[args.kernel][0], 
                         args_addr, args_sizes[args.kernel])

  