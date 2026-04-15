import struct
import random
import argparse
import sys

# ==========================================
# Helpers
# ==========================================
def float_to_hex(f):
    """Pack a python float into a 32-bit IEEE 754 hex string (0xXXXXXXXX)."""
    packed = struct.pack('>f', f) 
    return f"0x{packed.hex().upper()}"

def write_line(f_handle, addr, val_str):
    """Writes a line in the format: 0xADDR 0xDATA"""
    f_handle.write(f"0x{addr:08X} {val_str}\n")

def auto_int(x):
    """Helper to allow both decimal (1024) and hex (0x400) inputs."""
    return int(x, 0)

# ==========================================
# Main Generation
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Parameterized SAXPY Data Generator")
    
    # Files
    parser.add_argument("--out_in", default="saxpy_data.hex", help="Input hex file name")
    parser.add_argument("--out_exp", default="saxpy_exp.hex", help="Expected hex file name")
    
    # Simulation Parameters
    parser.add_argument("-n", "--elements", type=int, default=1024, help="Number of elements (N)")
    parser.add_argument("-a", "--scalar", type=float, default=2.0, help="Scalar multiplier (A)")
    parser.add_argument("-s", "--seed", type=int, default=42, help="Random seed for reproducibility")
    
    # Memory Layout
    parser.add_argument("--addr_args", type=auto_int, default=0x20000000, help="Base address for arguments")
    parser.add_argument("--addr_x", type=auto_int, default=0x30000000, help="Base address for Array X")
    parser.add_argument("--addr_y", type=auto_int, default=0x40000000, help="Base address for Array Y")

    args = parser.parse_args()

    print(f"Generating {args.elements} elements (Seed: {args.seed}, A: {args.scalar})")
    random.seed(args.seed)
    
    x_floats = []
    y_floats = []
    y_result = []
    
    # 1. Compute Data
    for _ in range(args.elements):
        x_raw = random.uniform(0.0, 100.0)
        y_raw = random.uniform(0.0, 100.0)
        
        # Ensure 32-bit precision
        x_32 = struct.unpack('f', struct.pack('f', x_raw))[0]
        y_32 = struct.unpack('f', struct.pack('f', y_raw))[0]
        
        x_floats.append(x_32)
        y_floats.append(y_32)

        res = (args.scalar * x_32) + y_32
        res_32 = struct.unpack('f', struct.pack('f', res))[0]
        y_result.append(res_32)

    # 2. Write Files
    with open(args.out_in, 'w') as f_in, open(args.out_exp, 'w') as f_exp:
        
        # --- Section A: Arguments ---
        def write_arg(offset, val, is_float=False):
            addr = args.addr_args + offset
            hex_val = float_to_hex(val) if is_float else f"0x{val:08X}"
            write_line(f_in, addr, hex_val)
            write_line(f_exp, addr, hex_val)

        write_arg(0, args.elements, is_float=False)
        write_arg(4, args.scalar, is_float=True)
        write_arg(8, args.addr_x, is_float=False)
        write_arg(12, args.addr_y, is_float=False)

        # --- Section B: Array X ---
        curr_x = args.addr_x
        for val in x_floats:
            h = float_to_hex(val)
            write_line(f_in, curr_x, h)
            write_line(f_exp, curr_x, h)
            curr_x += 4

        # --- Section C: Array Y ---
        curr_y = args.addr_y
        for i in range(args.elements):
            write_line(f_in, curr_y, float_to_hex(y_floats[i]))
            write_line(f_exp, curr_y, float_to_hex(y_result[i]))
            curr_y += 4

    print(f"Success! Files generated: {args.out_in}, {args.out_exp}")

if __name__ == "__main__":
    main()