"""
Generate SAXPY input data file with 32-character binary lines (one 4-byte value per line).

Format:
- Line 1: n (int32)
- Line 2: a (float32)
- Next n lines: x array (float32 each)
- Next n lines: y array (float32 each)

Defaults (varied values):
  n = 10000, a = 2.0
  x[i] = i
  y[i] = 2*i

Output file: data.txt (in current working directory)

Examples:
  python generate_saxpy_data.py --out data.txt
  python generate_saxpy_data.py --n 8192 --a 1.5 --x linear:0:0.5 --y linear:10:3
  python generate_saxpy_data.py --x const:1.0 --y const:2.0
"""

import struct
import argparse
import os

def bits32_le(val, fmt):
    b = struct.pack('<' + fmt, val)  # little-endian
    return ''.join(f'{byte:08b}' for byte in b)

def parse_pattern(spec, n, default_kind, default_start, default_step):
    """
    spec: "linear:<start>:<step>" or "const:<value>"
    returns a generator yielding n float values
    """
    if spec is None:
        # defaults
        if default_kind == "linear":
            start = float(default_start)
            step = float(default_step)
            for i in range(n):
                yield start + step * i
        elif default_kind == "const":
            val = float(default_start)
            for _ in range(n):
                yield val
        else:
            raise ValueError("Unknown default pattern")
        return

    parts = spec.split(":")
    kind = parts[0].lower()
    if kind == "linear":
        start = float(parts[1]) if len(parts) > 1 else 0.0
        step = float(parts[2]) if len(parts) > 2 else 1.0
        for i in range(n):
            yield start + step * i
    elif kind == "const":
        val = float(parts[1]) if len(parts) > 1 else 0.0
        for _ in range(n):
            yield val
    else:
        raise ValueError(f"Unknown pattern '{kind}'. Use 'linear' or 'const'.")

def write_file(out_path, n, a, x_pattern, y_pattern):
    with open(out_path, "w", newline="\n") as f:
        # n (int32)
        f.write(bits32_le(n, 'i') + "\n")
        # a (float32)
        f.write(bits32_le(a, 'f') + "\n")
        # x array
        for v in parse_pattern(x_pattern, n, default_kind="linear", default_start=0.0, default_step=1.0):
            f.write(bits32_le(float(v), 'f') + "\n")
        # y array
        for v in parse_pattern(y_pattern, n, default_kind="linear", default_start=0.0, default_step=2.0):
            f.write(bits32_le(float(v), 'f') + "\n")

    logical_bytes = (1 + 1 + n + n) * 4
    print(f"Wrote file: {out_path}")
    print(f"Logical data size (no newlines): {logical_bytes} bytes")
    try:
        print(f"File size on disk (includes newlines): {os.path.getsize(out_path)} bytes")
    except OSError:
        pass

    # Memory layout (byte offsets from 0)
    print("\nMemory Offsets (byte addresses starting at 0):")
    print(f"n      @ 0")
    print(f"a      @ 4")
    print(f"x[0]   @ 8        (x[i] @ 8 + 4*i)")
    x_end = 8 + 4*n
    print(f"y[0]   @ {x_end}    (y[i] @ {x_end} + 4*i)")
    y_last = x_end + 4*(n-1)
    print(f"y[{n-1}] @ {y_last} .. {y_last+3}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=str, default="data.txt", help="Output file path")
    parser.add_argument("--n", type=int, default=1024, help="Length of x and y arrays")
    parser.add_argument("--a", type=float, default=2.0, help="Scalar a")
    parser.add_argument("--x", type=str, default=None, help="Pattern for x: 'linear:start:step' or 'const:value'")
    parser.add_argument("--y", type=str, default=None, help="Pattern for y: 'linear:start:step' or 'const:value'")
    args = parser.parse_args()

    write_file(args.out, args.n, args.a, args.x, args.y)

if __name__ == "__main__":
    main()
