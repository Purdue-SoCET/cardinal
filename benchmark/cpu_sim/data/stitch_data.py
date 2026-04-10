from pathlib import Path

# --- Configuration ---
compiled = {
    "vs": "compiled/vs.bin",
    "tri": "compiled/tri.bin",
    "pix": "compiled/pix.bin"
}

args_sizes = {"vs": 0x28, "tri": 108, "pix": 0x34} 
block_dims = {"vs": 8, "tri": [1024] * 12, "pix": 1024} #[81,81,65,85,65,85,289,289,65,85,65,85]
# [12,12,10,12,10,12,30,30,8,10,8,10]
grid_dims  = {"vs": 1, "tri": 1, "pix": 1}

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

    # 2. Load Args and Heap from the C-dump files
    dump_path = Path(dump_dir)
    # We look for files like "vertexInput_args_dump.txt" or "triangleInput0_args_dump.txt"
    found_files = list(dump_path.glob(f"{filter_prefix}*"))
        
    for file_path in found_files:
        with open(file_path, "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) == 2:
                    addr = int(parts[0], 16)
                    val = parts[1]
                    memory_map[addr] = val.upper()

    # 3. Setup MMIO (Registers 0x00 to 0x20)
    entry_point = 0x00000024 # Standard entry
    total_threads = block_dim * grid_dim
    
    # We write these to the map. If it's an output dump, status is "Done"
    status = "00000000000000000000000000000011" if not is_input else "00000000000000000000000000000000"
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
    
    # --- 1. Vertex Stage ---
    v_prefix = f"vertex{mode_str}"
    stitch_system_memory("vs", DUMP_FOLDER, f"build/{v_prefix}_memDump_{block_dims["vs"]}.txt", 
                         v_prefix, is_input, block_dims["vs"], grid_dims["vs"], 
                         args_addr, args_sizes["vs"])

    # --- 2. Triangle Stage ---
    # We assume each triangle has its own dump file (triangleInput0, triangleInput1...)
    t_prefix_base = f"triangle{mode_str}"
    args_addr += args_sizes["vs"] # Vertex stage args come first, then triangle stage
    for i in range(12):
        stitch_system_memory("tri", DUMP_FOLDER, f"build/{t_prefix_base}{i}_memDump_{grid_dims["tri"]}_{block_dims["tri"][i]}.txt", 
                             f"{t_prefix_base}{i}", is_input, block_dims["tri"][i], grid_dims["tri"], 
                             args_addr, args_sizes["tri"])

    # --- 3. Pixel Stage ---
    p_prefix = f"pixel{mode_str}"
    args_addr += args_sizes["tri"] # Triangle stage args come after vertex stage
    stitch_system_memory("pix", DUMP_FOLDER, f"build/{p_prefix}_memDump_{block_dims["pix"]}.txt", 
                         p_prefix, is_input, block_dims["pix"], grid_dims["pix"], 
                         args_addr, args_sizes["pix"])