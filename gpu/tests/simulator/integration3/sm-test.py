from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from bitstring import Bits

FILE_ROOT = Path(__file__).resolve().parent
GPU_SIM_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(GPU_SIM_ROOT))

from simulator.sm import SM, SMConfig


# ==============================================================================
# Program Loader
# ==============================================================================

def load_program(file_path: Path, fmt: str = "bin") -> List[int]:

    words: List[int] = []

    with file_path.open("r") as fh:
        for line_no, raw in enumerate(fh, start=1):

            for marker in ("//", "#"):
                idx = raw.find(marker)
                if idx != -1:
                    raw = raw[:idx]

            line = raw.strip().replace("_", "")
            if not line:
                continue

            if fmt == "bin":

                if len(line) != 32:
                    raise ValueError(f"line {line_no} invalid binary")

                words.append(int(line, 2))

            elif fmt == "hex":

                parts = line.split()

                if len(parts) == 2:
                    words.append(int(parts[1], 16) & 0xFFFFFFFF)

                elif len(parts) == 1:
                    words.append(int(parts[0], 16) & 0xFFFFFFFF)

                else:
                    raise ValueError(f"line {line_no} invalid")

            else:
                raise ValueError("format must be bin or hex")

    return words


# ==============================================================================
# Runner
# ==============================================================================

def run_SM(program_file: Path, fmt: str):

    sm_config = SMConfig(
        sm_no=1,
        test_file=program_file,
        test_file_type=fmt,
        num_warps=32,
        num_preds=16,
        threads_per_warp=32,

        mem_start_pc=0x1000,
        mem_lat=5,
        mem_mod=None,
        memc_policy="rr",

        kern_init={"Kern_per_SM": 1, "Kern_ID": 9203930},

        icache_config={
            "cache_size": 32 * 1024,
            "block_size": 4,
            "associativity": 1
        },

        fu_config=None,
        wb_config=None,
        rf_config=None,
        prf_rf_config=None,

        custom_regfile_init=None,
        custom_prf_init=None,

        stage_order=None
    )

    print("Loading program:", program_file)

    words = load_program(program_file, fmt)

    print("Instructions loaded:", len(words))

    sm = SM(sm_config)

    cycles = len(words)

    print("Running pipeline for", cycles, "cycles")

    for _ in range(cycles):
        sm.compute()

    flush = cycles + 1100

    print("Flushing pipeline", flush)

    for _ in range(flush):
        sm.compute()

    regfile_out = FILE_ROOT / "regfile_dump.txt"
    prf_out = FILE_ROOT / "predicate_regfile_dump.txt"

    with open(regfile_out, "w") as f:
        sm.regfile.dump(file=f)

    with open(prf_out, "w") as f:
        sm.prf.dump(file=f)

    print("Dumped register files")


# ==============================================================================
# CLI
# ==============================================================================

def _parse_args():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "program",
        nargs="?",
        default=str(FILE_ROOT / "test_binaries/predicated_halt.bin")
    )

    parser.add_argument(
        "--fmt",
        "-f",
        default="bin",
        choices=["bin", "hex"]
    )

    return parser.parse_args()


if __name__ == "__main__":

    args = _parse_args()

    run_SM(Path(args.program), args.fmt)