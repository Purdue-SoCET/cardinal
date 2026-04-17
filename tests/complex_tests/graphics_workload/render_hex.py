import argparse
import struct
from PIL import Image

# Memory Map Constants
ADDR_DEPTH_BUFF = 0x50000000
ADDR_TAG_BUFF   = 0x51000000
ADDR_COLOR_BUFF = 0x70000000 

# Distinct colors for up to 16 different triangles/tags
TAG_COLORS = [
    (230, 25, 75),   # Red
    (60, 180, 75),   # Green
    (255, 225, 25),  # Yellow
    (67, 99, 216),   # Blue
    (245, 130, 49),  # Orange
    (145, 30, 180),  # Purple
    (66, 212, 244),  # Cyan
    (240, 50, 230),  # Magenta
    (191, 239, 69),  # Lime
    (250, 190, 212), # Pink
    (70, 240, 240),  # Teal
    (220, 190, 255), # Lavender
]

def read_word(memory, addr):
    """Reads 4 consecutive bytes from the memory map and returns them as a bytes object."""
    b0 = memory.get(addr, 0)
    b1 = memory.get(addr + 1, 0)
    b2 = memory.get(addr + 2, 0)
    b3 = memory.get(addr + 3, 0)
    return bytes([b0, b1, b2, b3])

def main():
    parser = argparse.ArgumentParser(description="Render emulator memory dump to PNG")
    parser.add_argument("input_hex", help="Path to the hex file (e.g., pixel_out.hex)")
    parser.add_argument("--out", default="render.png", help="Output PNG filename")
    parser.add_argument("--mode", choices=["depth", "tag", "color"], required=True, help="Render mode")
    parser.add_argument("--res", type=int, nargs=2, default=[800, 800], help="Resolution (W H)")
    
    args = parser.parse_args()
    w, h = args.res[0], args.res[1]
    
    # Initialize buffers 
    depth_buffer = [-1.0] * (w * h)
    tag_buffer = [-1] * (w * h)
    color_buffer = [[0.0, 0.0, 0.0] for _ in range(w * h)]
    
    print(f"Parsing {args.input_hex} at {w}x{h}...")
    
    memory = {}
    
    # Parse the hex file
    with open(args.input_hex, 'r') as f:
        for line in f:
            # Strip both ';' and '#' comments
            line = line.split(';')[0].split('#')[0].strip()
            if not line:
                continue
                
            parts = line.split()
            if len(parts) < 2:
                continue
                
            addr_str = parts[0]
            val_str = parts[1]
            
            # Skip diff artifacts if viewing a verifier log directly
            if val_str == "MISSING" or val_str.startswith("("): 
                continue
                
            addr = int(addr_str, 16)
            val_hex = val_str.replace('0x', '')
            
            # Support both byte-addressable and word-level entries
            if len(val_hex) <= 2:
                memory[addr] = int(val_hex, 16)
            else:
                val_hex = val_hex.zfill(8)
                memory[addr] = int(val_hex[0:2], 16)
                memory[addr+1] = int(val_hex[2:4], 16)
                memory[addr+2] = int(val_hex[4:6], 16)
                memory[addr+3] = int(val_hex[6:8], 16)

    # Reconstruct buffers from the memory map
    for idx in range(w * h):
        # Depth Buffer Update
        d_addr = ADDR_DEPTH_BUFF + (idx * 4)
        if any(a in memory for a in range(d_addr, d_addr + 4)):
            depth_buffer[idx] = struct.unpack('>f', read_word(memory, d_addr))[0]
            
        # Tag Buffer Update
        t_addr = ADDR_TAG_BUFF + (idx * 4)
        if any(a in memory for a in range(t_addr, t_addr + 4)):
            tag_buffer[idx] = struct.unpack('>i', read_word(memory, t_addr))[0]
            
        # Color Buffer Update
        c_addr = ADDR_COLOR_BUFF + (idx * 12)
        if any(a in memory for a in range(c_addr, c_addr + 12)):
            r = struct.unpack('>f', read_word(memory, c_addr))[0]
            g = struct.unpack('>f', read_word(memory, c_addr + 4))[0]
            b = struct.unpack('>f', read_word(memory, c_addr + 8))[0]
            color_buffer[idx] = [r, g, b]

    # Render Image
    img = Image.new('RGB', (w, h), color=(0, 0, 0))
    pixels = img.load()
    
    rendered_pixels = 0

    if args.mode == "depth":
        valid_depths = [d for d in depth_buffer if d >= 0.0]
        if not valid_depths:
            print("No valid depth data found!")
            return
            
        min_z, max_z = min(valid_depths), max(valid_depths)
        z_range = max_z - min_z if max_z != min_z else 1.0
        
        for idx in range(w * h):
            d = depth_buffer[idx]
            if d >= 0.0:
                intensity = int(((d - min_z) / z_range) * 255)
                intensity = max(0, min(255, intensity))
                x, y = idx % w, idx // w
                pixels[x, y] = (intensity, intensity, intensity)
                rendered_pixels += 1

    elif args.mode == "tag":
        for idx in range(w * h):
            t = tag_buffer[idx]
            if t != -1:
                color = TAG_COLORS[t % len(TAG_COLORS)]
                x, y = idx % w, idx // w
                pixels[x, y] = color
                rendered_pixels += 1

    elif args.mode == "color":
        for idx in range(w * h):
            r_f, g_f, b_f = color_buffer[idx]
            
            # Convert float (0.0 -> 1.0) to int (0 -> 255) and clamp just in case
            r = int(max(0.0, min(1.0, r_f)) * 255)
            g = int(max(0.0, min(1.0, g_f)) * 255)
            b = int(max(0.0, min(1.0, b_f)) * 255)
            
            x, y = idx % w, idx // w
            pixels[x, y] = (r, g, b)
            rendered_pixels += 1

    img.save(args.out)
    print(f"Success! Rendered {rendered_pixels} pixels to {args.out}")

if __name__ == "__main__":
    main()