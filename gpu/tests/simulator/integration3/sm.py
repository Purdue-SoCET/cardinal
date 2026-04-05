from dataclasses import dataclass
from pathlib import Path
from copy import deepcopy
from typing import Any, Dict, List, Optional
from contextlib import redirect_stdout
import argparse

# IMPORTANT:
# This must be a valid Python module name.
# Rename the file to sm_from_bin_tbs.py if needed.
from sm_from_bin_tbs import build_pipeline, tick_all, print_banks, deep_update


DEFAULT_SM_CONFIG = {
    "sim": {
        "start_pc": 0x1000,
        "warp_count": 32,
        "bdim": 1024,
        "max_cycles": 10000,
        "dump_root": "sweep_dumps",
    },
    "mem": {
        "latency": 2,
        "policy": "rr",
    },
    "icache": {
        "cache_size": 32 * 1024,
        "block_size": 4,
        "associativity": 1,
    },
    "dcache": {
        "num_banks": 2,
        "num_sets_per_bank": 16,
        "num_ways": 8,
        "block_size_words": 32,
        "word_size_bytes": 4,
        "uuid_size": 8,
        "mshr_buffer_len": 16,
        "hit_latency": 2,
    },
    "predicates": {
        "num_preds_per_warp": 16,
    },
}


@dataclass
class SM:
    sm_id: int
    program_file: Path
    fmt: str = "bin"
    config: Optional[dict] = None

    def __post_init__(self):
        self.config = deep_update(DEFAULT_SM_CONFIG, self.config or {})
        self.pipeline = build_pipeline(
            input_file=self.program_file,
            fmt=self.fmt,
            sm_config=self.config,
            sm_id=self.sm_id,
        )
        self.cycle = 0
        self.finished = False

        self.pipeline["tbs"].add_SM()
        self.pipeline["tbs"].append_block(
            bdim=self.config["sim"]["bdim"],
            spc=self.config["sim"]["start_pc"],
            apc=0x1000_0000,
        )

    def tick(self):
        if self.finished:
            return
        tick_all(self.pipeline)
        self.cycle += 1
        self.finished = self.pipeline["scheduler"].system_finished

    def run_to_completion(self, max_cycles: Optional[int] = None):
        limit = max_cycles or self.config["sim"]["max_cycles"]
        while not self.finished and self.cycle < limit:
            self.tick()

        self.dump_files()

        return {
            "sm_id": self.sm_id,
            "finished": self.finished,
            "cycles": self.cycle,
            "icache": deepcopy(self.config["icache"]),
            "dcache": deepcopy(self.config["dcache"]),
        }

    def dump_files(self, dump_root: Optional[Path] = None):
        root = Path(dump_root) if dump_root else Path(self.config["sim"]["dump_root"])
        sm_dir = root / f"sm_{self.sm_id:02d}"
        sm_dir.mkdir(parents=True, exist_ok=True)

        output_file = sm_dir / "output.txt"

        with output_file.open("w", encoding="utf-8") as f:
            with redirect_stdout(f):
                print(f"===== SM {self.sm_id:02d} DUMP =====")
                print(f"Program   : {self.program_file}")
                print(f"Finished  : {self.finished}")
                print(f"Cycles    : {self.cycle}")
                print(f"I$ config : {self.config['icache']}")
                print(f"D$ config : {self.config['dcache']}")
                print()

                print("===== DCACHE =====")
                print_banks(self.pipeline["dcache"])
                print()

                print("===== PIPELINE RF =====")
                self.pipeline["pipeline_rf"].dump()
                print()

                print("===== PRF =====")
                self.pipeline["prf"].dump()
                print()

        return output_file


def build_sweep_configs() -> List[Dict[str, Any]]:
    sweep_points: List[Dict[str, Any]] = []

    # Example sweep points
    # for ic_assoc in [1, 2]:
    #     for dc_ways in [4, 8]:
    #         sweep_points.append({
    #             "icache": {
    #                 "cache_size": 32 * 1024,
    #                 "block_size": 4,
    #                 "associativity": ic_assoc,
    #             },
    #             "dcache": {
    #                 "num_banks": 2,
    #                 "num_sets_per_bank": 16,
    #                 "num_ways": dc_ways,
    #                 "block_size_words": 32,
    #                 "word_size_bytes": 4,
    #                 "uuid_size": 8,
    #                 "mshr_buffer_len": 16,
    #                 "hit_latency": 2,
    #             },
    #         })
    sweep_points.append(DEFAULT_SM_CONFIG)  # Add the default config as one of the sweep points
    sweep_points.append(DEFAULT_SM_CONFIG)  # Add the default config as one of the sweep points, but just change the mem latency to 4
    sweep_points.append(DEFAULT_SM_CONFIG)  # Add the default config as one of the sweep points, but just change the mem latency to 6
    sweep_points.append(DEFAULT_SM_CONFIG)  # Add the default config as one of the sweep points, but just change the mem latency to 10
    sweep_points[-3]["mem"]["latency"] = 
    sweep_points[-2]["mem"]["latency"] = 6
    sweep_points[-1]["mem"]["latency"] = 10
    return sweep_points


def run_sweep(
    program_file: Path,
    fmt: str = "bin",
    sweep_configs: Optional[List[Dict[str, Any]]] = None,
    max_global_cycles: int = 10000,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    configs = sweep_configs or build_sweep_configs()

    sms: List[SM] = [
        SM(sm_id=i, program_file=program_file, fmt=fmt, config=cfg)
        for i, cfg in enumerate(configs)
    ]

    global_cycle = 0
    while global_cycle < max_global_cycles:
        unfinished = [sm for sm in sms if not sm.finished]
        if not unfinished:
            break

        for sm in unfinished:
            sm.tick()

        global_cycle += 1

        if verbose and global_cycle % 100 == 0:
            done = sum(1 for sm in sms if sm.finished)
            print(f"[sweep] global_cycle={global_cycle} done={done}/{len(sms)}")

    # dump every SM after the sweep loop
    dump_paths = {}
    for sm in sms:
        dump_paths[sm.sm_id] = sm.dump_files()

    results = []
    for sm in sms:
        results.append(
            {
                "sm_id": sm.sm_id,
                "finished": sm.finished,
                "cycles": sm.cycle,
                "icache_assoc": sm.config["icache"]["associativity"],
                "dcache_ways": sm.config["dcache"]["num_ways"],
                "dcache_hit_latency": sm.config["dcache"]["hit_latency"],
                "dcache_num_banks": sm.config["dcache"]["num_banks"],
                "dump_file": str(dump_paths[sm.sm_id]),
            }
        )

    results.sort(key=lambda x: (not x["finished"], x["cycles"]))
    return results


def print_sweep_results(results: List[Dict[str, Any]]) -> None:
    print("\n===== SWEEP RESULTS =====")
    for r in results:
        status = "DONE" if r["finished"] else "TIMEOUT"
        print(
            f"SM {r['sm_id']:02d} | {status:7s} | "
            f"cycles={r['cycles']:5d} | "
            f"I$ assoc={r['icache_assoc']} | "
            f"D$ ways={r['dcache_ways']} | "
            f"D$ hit_lat={r['dcache_hit_latency']} | "
            f"D$ banks={r['dcache_num_banks']} | "
            f"dump={r['dump_file']}"
        )


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "program",
        nargs="?",
        default="gpu/tests/simulator/integration3/test_binaries/ldst_sequence.bin",
    )
    parser.add_argument("--fmt", choices=["bin", "hex"], default="bin")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    results = run_sweep(
        program_file=Path(args.program),
        fmt=args.fmt,
        sweep_configs=build_sweep_configs(),
        max_global_cycles=10000,
        verbose=not args.quiet,
    )
    print_sweep_results(results)