"""
Compare hex files in test_diffs by memory address.

For each prefix that has all three files (_gen.hex, _exp.hex, _meminit.hex):
  - [output_base]_diff.txt: gen vs exp (DATA1=gen, DATA2=exp)
  - [output_base]_actual_diff.txt: gen vs meminit (DATA1=gen, DATA2=meminit)
  - [output_base]_expected_diff.txt: exp vs meminit (DATA1=exp, DATA2=meminit)

Output format per differing address:
  [ADDRESS] [DATA1] [DATA2]
  - For _diff.txt: DATA1=gen, DATA2=exp
  - For _actual_diff.txt: DATA1=gen, DATA2=meminit
  - For _expected_diff.txt: DATA1=exp, DATA2=meminit
  - N/A if address does not exist in that file
"""

import re
from pathlib import Path


def load_hex(path: Path) -> dict[int, int]:
    """Load addr -> data mapping from hex file. Format: 0xADDR 0xDATA per line."""
    result: dict[int, int] = {}
    pattern = re.compile(r"^\s*(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s*")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.split("//")[0].split("#")[0].strip()
            if not line:
                continue
            m = pattern.match(line)
            if m:
                addr = int(m.group(1), 16)
                data = int(m.group(2), 16) & 0xFFFF_FFFF
                result[addr] = data
    return result


def format_hex(val: int) -> str:
    """Format as 0xXXXXXXXX uppercase."""
    return f"0x{val:08X}"


def diff_addrs(
    other: dict[int, int],
    meminit: dict[int, int],
) -> list[tuple[int, str, str]]:
    """
    Compare address-by-address. Return list of (addr, data1_str, data2_str)
    for addresses where data differs. data2 is always from meminit.
    """
    all_addrs = set(other.keys()) | set(meminit.keys())
    diffs: list[tuple[int, str, str]] = []
    for addr in sorted(all_addrs):
        d1 = other.get(addr)
        d2 = meminit.get(addr)
        if d1 is None and d2 is None:
            continue
        s1 = "N/A" if d1 is None else format_hex(d1)
        s2 = "N/A" if d2 is None else format_hex(d2)
        if d1 != d2:
            diffs.append((addr, s1, s2))
    return diffs


def collect_prefixes(diff_dir: Path) -> list[str]:
    """Find prefixes that have gen, exp, and meminit."""
    seen: set[str] = set()
    for f in diff_dir.iterdir():
        if not f.is_file() or f.suffix.lower() != ".hex":
            continue
        stem = f.stem
        if stem.endswith("_gen"):
            prefix = stem[:-4]
        elif stem.endswith("_exp"):
            prefix = stem[:-4]
        elif stem.endswith("_meminit"):
            prefix = stem[:-8]
        else:
            continue
        gen = diff_dir / f"{prefix}_gen.hex"
        exp = diff_dir / f"{prefix}_exp.hex"
        meminit = diff_dir / f"{prefix}_meminit.hex"
        if gen.exists() and exp.exists() and meminit.exists():
            seen.add(prefix)
    return sorted(seen)


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    emu_dir = script_dir.parent
    diff_dir = emu_dir / "test_diffs"
    if not diff_dir.is_dir():
        print(f"Error: test_diffs not found: {diff_dir}")
        return

    prefixes = collect_prefixes(diff_dir)
    if not prefixes:
        print("No prefixes with gen, exp, and meminit found in test_diffs.")
        return

    for prefix in prefixes:
        gen_path = diff_dir / f"{prefix}_gen.hex"
        exp_path = diff_dir / f"{prefix}_exp.hex"
        meminit_path = diff_dir / f"{prefix}_meminit.hex"

        gen_data = load_hex(gen_path)
        exp_data = load_hex(exp_path)
        meminit_data = load_hex(meminit_path)

        output_base = prefix.split("_", 1)[0]  # cut at first underscore
        # gen vs exp
        gen_exp_diffs = diff_addrs(gen_data, exp_data)
        gen_exp_out = diff_dir / f"{output_base}_diff.txt"
        with open(gen_exp_out, "w", encoding="utf-8") as f:
            for addr, d1, d2 in gen_exp_diffs:
                f.write(f"0x{addr:08X} {d1} {d2}\n")
        print(f"Wrote {gen_exp_out.name} ({len(gen_exp_diffs)} diffs)")

        # actual: gen vs meminit
        actual_diffs = diff_addrs(gen_data, meminit_data)
        actual_out = diff_dir / f"{output_base}_actual_diff.txt"
        with open(actual_out, "w", encoding="utf-8") as f:
            for addr, d1, d2 in actual_diffs:
                f.write(f"0x{addr:08X} {d1} {d2}\n")
        print(f"Wrote {actual_out.name} ({len(actual_diffs)} diffs)")

        # expected: exp vs meminit
        expected_diffs = diff_addrs(exp_data, meminit_data)
        expected_out = diff_dir / f"{output_base}_expected_diff.txt"
        with open(expected_out, "w", encoding="utf-8") as f:
            for addr, d1, d2 in expected_diffs:
                f.write(f"0x{addr:08X} {d1} {d2}\n")
        print(f"Wrote {expected_out.name} ({len(expected_diffs)} diffs)")


if __name__ == "__main__":
    main()
