import argparse
import struct
from PIL import Image

# Memory Map Constants
ADDR_DEPTH_BUFF = 0x50000000
ADDR_TAG_BUFF   = 0x51000000
ADDR_COLOR_BUFF = 0x60000000 # NEW: Base address for color vector array

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

def hex_to_float(hex_str):
    """Converts a 32-bit hex string (e.g., '0x3F800000') to a Python float."""
    try:
        return struct.unpack('>f', bytes.fromhex(hex_str.replace('0x', '')))[0]
    except ValueError:
        return 0.0

def hex_to_int(hex_str):
    """Converts a 32-bit hex string to an integer, handling -1 (0xFFFFFFFF)."""
    val = int(hex_str, 16)
    if val == 0xFFFFFFFF:
        return -1
    return val

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
    color_buffer = [[0.0, 0.0, 0.0] for _ in range(w * h)] # Default black
    
    print(f"Parsing {args.input_hex} at {w}x{h}...")
    
    # Parse the hex file
    with open(args.input_hex, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or len(line.split()) < 2:
                continue
                
            parts = line.split()
            addr_str = parts[0]
            val_str = parts[1]
            
            # Skip diff artifacts if viewing a verifier log directly
            if val_str == "MISSING" or val_str.startswith("("): 
                continue
                
            addr = int(addr_str, 16)
            
            # Map Address -> Pixel Index
            if ADDR_DEPTH_BUFF <= addr < (ADDR_DEPTH_BUFF + w * h * 4):
                idx = (addr - ADDR_DEPTH_BUFF) // 4
                depth_buffer[idx] = hex_to_float(val_str)
                
            elif ADDR_TAG_BUFF <= addr < (ADDR_TAG_BUFF + w * h * 4):
                idx = (addr - ADDR_TAG_BUFF) // 4
                tag_buffer[idx] = hex_to_int(val_str)

            elif ADDR_COLOR_BUFF <= addr < (ADDR_COLOR_BUFF + w * h * 12):
                # 12 bytes per pixel (3 floats). Find which pixel and which channel (R/G/B)
                offset = addr - ADDR_COLOR_BUFF
                pixel_idx = offset // 12
                channel_idx = (offset % 12) // 4 # 0=R, 1=G, 2=B
                color_buffer[pixel_idx][channel_idx] = hex_to_float(val_str)

    # Render Image
    img = Image.new('RGB', (w, h), color=(0, 0, 0)) # Black background
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