#!/usr/bin/env python3
"""
Hex-Bin Converter: Convert between hex and binary formats for GPU simulator

Usage:
    python3 hex_bin_converter.py h2b input.hex output.bin
    python3 hex_bin_converter.py b2h input.bin output.hex

Hex format: address (hex) value (hex)
    Example: 0x10000000 0x00000001

Binary format: address (hex) value (binary 32-bit)
    Example: 0x00000000 11000000000000000000000111011000
"""

import sys
from pathlib import Path


def b2h(input_file, output_file):
    """Convert binary format to hex format.
    
    Binary format: address (hex) value (binary 32-bit)
    Hex format: address (hex) value (hex)
    """
    try:
        with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
            for line in infile:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                if len(parts) != 2:
                    print(f"Warning: Skipping malformed line: {line}", file=sys.stderr)
                    continue
                
                addr_str = parts[0]
                binary_str = parts[1]
                
                try:
                    # Parse address (hex)
                    if addr_str.startswith('0x') or addr_str.startswith('0X'):
                        addr = int(addr_str, 16)
                    else:
                        addr = int(addr_str, 10)
                    
                    # Parse value (binary)
                    if len(binary_str) == 32:
                        value = int(binary_str, 2)
                    else:
                        print(f"Warning: Invalid binary value length (expected 32, got {len(binary_str)}): {line}", file=sys.stderr)
                        continue
                    
                    # Write as hex
                    outfile.write(f"0x{addr:08x} 0x{value:08x}\n")
                except ValueError as e:
                    print(f"Warning: Error parsing line: {line} ({e})", file=sys.stderr)
                    continue
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def h2b(input_file, output_file):
    """Convert hex format to binary format.
    
    Hex format: address (hex) value (hex)
    Binary format: address (hex) value (binary 32-bit)
    """
    try:
        with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
            for line in infile:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                if len(parts) != 2:
                    print(f"Warning: Skipping malformed line: {line}", file=sys.stderr)
                    continue
                
                addr_str = parts[0]
                hex_str = parts[1]
                
                try:
                    # Parse address (hex)
                    if addr_str.startswith('0x') or addr_str.startswith('0X'):
                        addr = int(addr_str, 16)
                    else:
                        addr = int(addr_str, 10)
                    
                    # Parse value (hex)
                    if hex_str.startswith('0x') or hex_str.startswith('0X'):
                        value = int(hex_str, 16)
                    else:
                        value = int(hex_str, 16)
                    
                    # Validate value is 32-bit
                    if value > 0xFFFFFFFF:
                        print(f"Warning: Value out of 32-bit range: {line}", file=sys.stderr)
                        continue
                    
                    # Write as binary (32-bit)
                    binary_str = format(value, '032b')
                    outfile.write(f"0x{addr:08x} {binary_str}\n")
                except ValueError as e:
                    print(f"Warning: Error parsing line: {line} ({e})", file=sys.stderr)
                    continue
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 hex_bin_converter.py <mode> <input_file> <output_file>")
        print("       where mode is 'h2b' (hex to binary) or 'b2h' (binary to hex)")
        sys.exit(1)
    
    mode = sys.argv[1]
    input_file = sys.argv[2]
    output_file = sys.argv[3]
    
    if mode == "b2h":
        b2h(input_file, output_file)
        print(f"Converted {input_file} to {output_file} (binary to hex)")
    elif mode == "h2b":
        h2b(input_file, output_file)
        print(f"Converted {input_file} to {output_file} (hex to binary)")
    else:
        print(f"Error: Unknown mode '{mode}'. Use 'b2h' or 'h2b'")
        sys.exit(1)


if __name__ == "__main__":
    main()
