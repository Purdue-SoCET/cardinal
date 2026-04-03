import sys

def parse_line(line):
    parts = line.strip().split()
    if len(parts) != 2:
        return None
    try:
        first = int(parts[0], 16)
        second = int(parts[1], 16)
        return first, second
    except ValueError:
        return None

def format_hex(value):
    return f"0x{value:08x}"

def main():
    if len(sys.argv) != 2:
        print("Usage: python sort_triangle.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = "output_triangle.hex"

    rows = []

    with open(input_file, "r") as infile:
        for line_num, line in enumerate(infile, 1):
            if not line.strip():
                continue
            parsed = parse_line(line)
            if parsed is None:
                print(f"Skipping invalid line {line_num}: {line.strip()}")
                continue
            rows.append(parsed)

    rows.sort(key=lambda x: x[0])

    with open(output_file, "w") as outfile:
        for first, second in rows:
            outfile.write(f"{format_hex(first)} {format_hex(second)}\n")

    print(f"Sorted output written to {output_file}")

if __name__ == "__main__":
    main()