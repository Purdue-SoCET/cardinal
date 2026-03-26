#!/usr/bin/env python3
import sys

if len(sys.argv) != 4:
    print("Usage: python3 hex_bin_converter.py <mode: h2b or b2h> <input_file> <output_file>")
    sys.exit(1)

mode = sys.argv[1]
input_file = sys.argv[2]
output_file = sys.argv[3]

with open(input_file, 'r') as f_in, open(output_file, 'w') as f_out:
    for line in f_in:
        parts = line.strip().split()
        if len(parts) == 2:
            addr = parts[0]
            data_val = parts[1]
            
            if mode == "h2b":
                # Convert Hex to 32-bit Binary
                converted_data = f"{int(data_val, 16):032b}"
            elif mode == "b2h":
                # Convert Binary to 32-bit Hex (8 hex digits)
                # Adding the '0x' prefix to match your emulator's expected format
                converted_data = f"0x{int(data_val, 2):08x}"
            else:
                print(f"Error: Unknown mode '{mode}'. Use 'h2b' or 'b2h'.")
                sys.exit(1)
                
            f_out.write(f"{addr} {converted_data}\n")