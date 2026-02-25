"""
Extract the hex column from a disassembly txt file and write to [filename].hex.

Input format (e.g., vertexShaderO2.txt):
  Addr     | Hex      | Instruction
  --------------------------------------------------
  00000000 | 000004D8 | csrr x9, 0, 0
  ...

Output: complex_tests/[filename]/[filename].hex with one hex value per line.
  - vertexShaderO2.txt -> complex_tests/vertexShader/vertexShader.hex
  - vertexShader.txt   -> complex_tests/vertexShader/vertexShader.hex
"""

import re
import sys
from pathlib import Path


def get_output_basename(input_path: Path) -> str:
    """Derive output basename: strip O2.txt or .txt from input filename."""
    name = input_path.stem  # e.g. "vertexShaderO2" or "vertexShader"
    if name.endswith("O2"):
        return name[:-2]  # "vertexShader"
    return name


def extract_hex_column(input_path: Path) -> list[str]:
    """Parse disassembly file and return list of hex values from the Hex column."""
    hex_values = []
    # Match data lines: Addr | Hex | Instruction
    line_pattern = re.compile(r"^[0-9A-Fa-f]+\s+\|\s+([0-9A-Fa-f]{8})\s+\|")
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            m = line_pattern.match(line.strip())
            if m:
                hex_values.append(m.group(1))
    return hex_values


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python toHex.py <input.txt>")
        sys.exit(1)
    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: file not found: {input_path}")
        sys.exit(1)
    base = get_output_basename(input_path)
    # Output to complex_tests/[filename]/[filename].hex
    script_dir = Path(__file__).resolve().parent
    tests_dir = script_dir
    while tests_dir != tests_dir.parent:
        if (tests_dir / "complex_tests").is_dir():
            break
        tests_dir = tests_dir.parent
    else:
        tests_dir = script_dir  # fallback: use script dir
    output_dir = tests_dir / "complex_tests" / base
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{base}.hex"
    hex_values = extract_hex_column(input_path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(hex_values))
    print(f"Wrote {len(hex_values)} hex values to {output_path}")


if __name__ == "__main__":
    main()
