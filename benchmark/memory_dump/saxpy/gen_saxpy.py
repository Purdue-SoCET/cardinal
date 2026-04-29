import struct
import random

# ==========================================
# Configuration
# ==========================================
# File names
FILENAME_INPUT = "saxpy_data.hex"
FILENAME_EXPECTED = "saxpy_exp_t1024_b1.hex"

# Simulation Parameters
SEED = 42           # Fixed seed for deterministic output
N = 1024            # Number of elements
A_VAL = 2.0         # Scalar multiplier

# Memory Layout (Must match your assembly hardcodes)
ADDR_ARGS = 0x20000000
ADDR_X    = 0x30000000
ADDR_Y    = 0x40000000

# ==========================================
# Helpers
# ==========================================
def float_to_hex(f):
    """Pack a python float into a 32-bit IEEE 754 hex string (0xXXXXXXXX)."""
    # struct.pack('f', f) packs as 32-bit float
    packed = struct.pack('>f', f) 
    return f"0x{packed.hex().upper()}"

def write_line(f_handle, addr, val_str):
    """Writes a line in the format: 0xADDR 0xDATA"""
    f_handle.write(f"0x{addr:08X} {val_str}\n")

# ==========================================
# Main Generation
# ==========================================
def main():
    print(f"Generating {N} vectors with Seed {SEED}...")
    random.seed(SEED)
    
    # 1. Generate Input Data (Python floats)
    X_floats = []
    Y_floats = []
    Y_result = []
    
    print("Computing vectors...")
    for _ in range(N):
        # Generate random values between 0.0 and 100.0
        x_raw = random.uniform(0.0, 100.0)
        y_raw = random.uniform(0.0, 100.0)
        
        # Truncate to 32-bit float precision to match hardware behavior
        # (Python uses 64-bit doubles by default)
        x_32 = struct.unpack('f', struct.pack('f', x_raw))[0]
        y_32 = struct.unpack('f', struct.pack('f', y_raw))[0]
        
        X_floats.append(x_32)
        Y_floats.append(y_32)

        # Compute Expected Output (SAXPY) in 32-bit domain
        # Y[i] = A * X[i] + Y[i]
        res = (A_VAL * x_32) + y_32
        res_32 = struct.unpack('f', struct.pack('f', res))[0]
        Y_result.append(res_32)

    # 2. Write Files
    print(f"Writing to {FILENAME_INPUT} and {FILENAME_EXPECTED}...")
    
    with open(FILENAME_INPUT, 'w') as f_in, open(FILENAME_EXPECTED, 'w') as f_exp:
        
        # --- Section A: Arguments (0x2000...) ---
        # 0x20...00 = N
        # 0x20...04 = A
        # 0x20...08 = &X
        # 0x20...0C = &Y
        
        # Helper to write to both files since args don't change
        def write_arg(offset, val, is_float=False):
            addr = ADDR_ARGS + offset
            if is_float:
                hex_val = float_to_hex(val)
            else:
                hex_val = f"0x{val:08X}"
            write_line(f_in, addr, hex_val)
            write_line(f_exp, addr, hex_val)

        write_arg(0, N, is_float=False)
        write_arg(4, A_VAL, is_float=True)
        write_arg(8, ADDR_X, is_float=False)
        write_arg(12, ADDR_Y, is_float=False)

        # --- Section B: Array X (0x3000...) ---
        # X is read-only, so it is identical in Input and Expected
        curr_addr = ADDR_X
        for val in X_floats:
            hex_val = float_to_hex(val)
            write_line(f_in, curr_addr, hex_val)
            write_line(f_exp, curr_addr, hex_val)
            curr_addr += 4

        # --- Section C: Array Y (0x4000...) ---
        # Input File gets Initial Y
        # Expected File gets Result Y
        curr_addr = ADDR_Y
        for i in range(N):
            # Input File: Initial Y value
            hex_in = float_to_hex(Y_floats[i])
            write_line(f_in, curr_addr, hex_in)
            
            # Expected File: Calculated Result
            hex_out = float_to_hex(Y_result[i])
            write_line(f_exp, curr_addr, hex_out)
            
            curr_addr += 4

    print(f"Success! Files generated.")

if __name__ == "__main__":
    main()