#!/usr/bin/env python3

import argparse
from pathlib import Path


def add_byte_addresses_to_hex_file(input_file: str, output_file: str, start_pc: int) -> None:
    in_path = Path(input_file)
    out_path = Path(output_file)

    if not in_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    addr = start_pc

    with in_path.open("r") as fin, out_path.open("w") as fout:
        for line_num, line in enumerate(fin, start=1):
            value = line.strip()

            if not value:
                continue

            if value.lower().startswith("0x"):
                value = value[2:]

            try:
                int(value, 16)
            except ValueError as e:
                raise ValueError(f"Invalid hex value on line {line_num}: {line.strip()}") from e

            fout.write(f"0x{addr:08X} 0x{value.upper()}\n")
            addr += 4


def parse_int_auto_base(value: str) -> int:
    return int(value, 0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prefix each hex word in a file with byte addresses starting from start_pc."
    )
    parser.add_argument("input_file", help="Input file with one hex word per line")
    parser.add_argument("output_file", help="Output file")
    parser.add_argument("start_pc", help="Starting PC/address, e.g. 0x0 or 4096")

    args = parser.parse_args()

    start_pc = parse_int_auto_base(args.start_pc)
    add_byte_addresses_to_hex_file(args.input_file, args.output_file, start_pc)


if __name__ == "__main__":
    main()