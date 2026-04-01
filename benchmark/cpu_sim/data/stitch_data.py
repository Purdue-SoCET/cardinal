from pathlib import Path
import json

# Set Values to Run:
filter_prefix = "vertexOutput"
is_input = False
json_file = "vs" 
dump_folder = "build/mem_dump"
final_dump = "build/vertexOutput_memDump.txt"
block_dim = 8
grid_dim = 1
args_addr = 0x00100000 
args_size = 24

def stitch_system_memory(json_path, dump_dir, output_file, filter_prefix="vertexInput", is_input=True):
    """
    Stitches MMIO, Instructions, Args, and Heap into a single sorted memory dump.
    """
    memory_map = {} # Maps Address -> Value String

    # 1. Load Instructions from Twig JSON
    with open(json_path, 'r') as f:
        twig_data = json.load(f)
    
    code_section = next((s for s in twig_data['sections'] if s['name'] == 'code'), None)
    if code_section:
        addr = int(code_section['address'], 16) # Should be 0x24
        for val in code_section['data']:
            if val != "00000000": 
                memory_map[addr] = val.upper()
            addr += 4

    # 2. Load Args and Heap from the dump directory
    dump_path = Path(dump_dir)
    found_files = list(dump_path.glob(f"{filter_prefix}*"))
        
    for file_path in found_files:
        with open(file_path, "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) == 2:
                    addr = int(parts[0], 16)
                    val = parts[1]
                    memory_map[addr] = val.upper()
                    

    entry_point = 0x24 
    total_threads = block_dim * grid_dim

    if is_input:
        input_MMIO(memory_map, block_dim, grid_dim, total_threads, entry_point, args_addr, args_size)
    else:
        output_MMIO(memory_map, block_dim, grid_dim, total_threads, entry_point, args_addr, args_size)

    # 4. Write sorted output
    with open(output_file, 'w') as f:
        for addr in sorted(memory_map.keys()):
            # Use upper to match your requested format
            f.write(f"0x{addr:08x} {memory_map[addr]}\n")

    print(f"Stitched memory image saved to: {output_file}")

def input_MMIO(memory_map, block_dim, grid_dim, threads, entry, args_addr, args_size):
    """
    Sets registers for a START/RUN state.
    """
    memory_map[0x00] = "00000001" # Control: Start GPU
    memory_map[0x04] = "00000000" # Status: Clear
    memory_map[0x08] = "00000000" # Device ID: 0
    memory_map[0x0C] = f"{entry:08x}"      # Entry
    memory_map[0x10] = f"{block_dim:08x}" # Block
    memory_map[0x14] = f"{grid_dim:08x}"  # Grid
    memory_map[0x18] = f"{threads:08x}"   # Total Threads
    memory_map[0x1C] = f"{args_addr:08x}"  # Args Addr
    memory_map[0x20] = f"{args_size:08x}"  # Args Size

def output_MMIO(memory_map, block_dim, grid_dim, threads, entry, args_addr, args_size):
    """
    Sets registers for a DONE/IDLE state.
    """
    memory_map[0x00] = "00000000" # Control: Stop
    memory_map[0x04] = "00000003" # Status: DONE (bit 0) and IDLE (bit 1)
    memory_map[0x08] = "00000000" # Device ID
    memory_map[0x0C] = f"{entry:08x}"
    memory_map[0x10] = f"{block_dim:08x}"
    memory_map[0x14] = f"{grid_dim:08x}"
    memory_map[0x18] = f"{threads:08x}"
    memory_map[0x1C] = f"{args_addr:08x}"
    memory_map[0x20] = f"{args_size:08x}"

stitch_system_memory(json_file, dump_folder, final_dump, filter_prefix, is_input)