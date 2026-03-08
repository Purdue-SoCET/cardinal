from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional
import math

from bitstring import Bits

FILE_ROOT = Path(__file__).resolve().parent
GPU_SIM_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(GPU_SIM_ROOT))

from config_loader import load_sm_config, initialize_memory, initialize_register_file
from simulator.sm import SM, SMConfig
from simulator.issue.regfile import RegisterFile

BLOCK_SIZE_WORDS = 32
# ==============================================================================
# Program Loader
# ==============================================================================

def load_program(file_path: Path, fmt: str = "bin") -> List[int]:

    program = []

    with file_path.open("r") as fh:

        for line_no, raw in enumerate(fh, start=1):

            # strip comments
            for marker in ("//", "#"):
                idx = raw.find(marker)
                if idx != -1:
                    raw = raw[:idx]

            line = raw.strip().replace("_", "")
            if not line:
                continue

            parts = line.split()

            if len(parts) != 2:
                raise ValueError(
                    f"Line {line_no}: expected format 'addr data'"
                )

            addr_str, data_str = parts

            addr = int(addr_str, 0)

            if addr % 4 != 0:
                raise ValueError(
                    f"Line {line_no}: address {addr:#x} not word aligned"
                )

            if fmt == "bin":

                if len(data_str) != 32:
                    raise ValueError(
                        f"Line {line_no}: expected 32-bit binary"
                    )

                word = int(data_str, 2)

            elif fmt == "hex":

                word = int(data_str, 16)

            else:
                raise ValueError("format must be bin or hex")

            program.append((addr, word & 0xFFFFFFFF))

    # --------------------------------------------------
    # Sort by address so pipeline executes correctly
    # --------------------------------------------------

    program.sort(key=lambda x: x[0])

    words = [w for _, w in program]

    return words

# ==============================================================================
# Register-file comparison
# ==============================================================================

def compare_register_files(pipeline_rf, golden_rf, warp_id=0, reg_list=None, verbose=False):

    mismatches = []

    if reg_list is None:
        reg_range = range(pipeline_rf.regs_per_warp)
    else:
        reg_range = reg_list

    for reg_num in reg_range:

        for thread_id in range(pipeline_rf.threads_per_warp):

            pipeline_val = pipeline_rf.read_thread_gran(
                warp_id=warp_id,
                src_operand=Bits(uint=reg_num, length=32),
                thread_id=thread_id,
            )

            golden_val = golden_rf.read_thread_gran(
                warp_id=warp_id,
                src_operand=Bits(uint=reg_num, length=32),
                thread_id=thread_id,
            )

            if pipeline_val != golden_val:

                mismatches.append({
                    "reg": reg_num,
                    "thread": thread_id,
                    "pipeline": pipeline_val,
                    "golden": golden_val
                })

    if verbose and mismatches:

        print(f"\n❌ Found {len(mismatches)} mismatches:")

        for m in mismatches:

            print(
                f"  Reg[{m['reg']}][{m['thread']}]: "
                f"Pipe={m['pipeline'].uint if m['pipeline'] else None} "
                f"Gold={m['golden'].uint if m['golden'] else None}"
            )

    return len(mismatches) == 0


# REG FILE SETUP AND COMPARISON

def write_reg_warp(regfile, warp_id, reg_num, values, as_float=False):
    threads = regfile.threads_per_warp
    if len(values) == 1:
        values = values * threads
    if as_float:
        data = [Bits(float=v, length=32) for v in values]
    else:
        data = [Bits(int=v, length=32) for v in values]
    regfile.write_warp_gran(
        warp_id=warp_id,
        dest_operand=Bits(uint=reg_num, length=32),
        data=data
    )

def write_mem_word(mem, addr, value, allow_instr_mem=False):
    if addr >= mem.start_pc and not allow_instr_mem:
        raise ValueError(f"Refusing to write instruction memory at {addr:#x}")
    mem.write(addr, Bits(uintle=value & 0xFFFFFFFF, length=32), 4)

def apply_local_setup(sm, setup_name):
    if setup_name == "default":
        warp = 0
        threads = sm.regfile.threads_per_warp
        write_reg_warp(sm.regfile, warp, 1, [31 - i for i in range(threads)])
        write_reg_warp(sm.regfile, warp, 2, [i for i in range(threads)])
        write_reg_warp(sm.regfile, warp, 8, [100])
        write_reg_warp(sm.regfile, warp, 9, [100])

        for i in range(threads):
            write_mem_word(sm.mem, i * 32, 1)
            write_mem_word(sm.mem, 0x400 + i * 32, 2)
    elif setup_name == "sw_basic":
        threads = sm.regfile.threads_per_warp

        for warp in range(4):
            addr_vals = [0x100 + i * 4 for i in range(threads)]
            data_vals = [24 for _ in range(threads)]

            write_reg_warp(sm.regfile, warp, 1, addr_vals)
            write_reg_warp(sm.regfile, warp, 2, data_vals)

        for i in range(threads):
            write_mem_word(sm.mem, 0x100 + i * 4, 42)
    else:
        raise ValueError(f"Unknown setup: {setup_name}")

# ==============================================================================
# Verification Wrapper
# ==============================================================================

def verify_register_files(pipeline_rf, golden_rf, warp_ids, regs_to_check=None):

    all_passed = True

    for warp_id in warp_ids:

        passed = compare_register_files(
            pipeline_rf=pipeline_rf,
            golden_rf=golden_rf,
            warp_id=warp_id,
            reg_list=regs_to_check,
            verbose=True
        )

        if passed:
            print(f"  ✅ Warp {warp_id} PASSED")
        else:
            print(f"  ❌ Warp {warp_id} FAILED")
            all_passed = False

    if all_passed:
        print("\n✅ SUCCESS: All warps passed.")
    else:
        print("\n❌ FAILURE: Register mismatches detected.")

    return all_passed

# CLI
def _parse_args():
    parser = argparse.ArgumentParser(
        description="Run SM test with selectable program file and local setup."
    )

    parser.add_argument(
        "program",
        nargs="?",
        default=None,
        help="Path to the program file. If omitted, uses program from sm_config.yaml."
    )

    parser.add_argument(
        "--fmt", "-f",
        choices=["bin", "hex"],
        default=None,
        help="Program file format. If omitted, uses format from sm_config.yaml."
    )

    parser.add_argument(
        "--setup", "-s",
        default="default",
        help="Local handwritten setup selection."
    )

    return parser.parse_args()

# ==============================================================================
# Golden RF creation
# ==============================================================================

def create_golden_rf(reference_rf):

    golden_rf = RegisterFile()

    for warp in range(reference_rf.warps):

        for reg in range(reference_rf.regs_per_warp):

            values = []

            for thread in range(reference_rf.threads_per_warp):

                val = reference_rf.read_thread_gran(
                    warp_id=warp,
                    src_operand=Bits(uint=reg, length=32),
                    thread_id=thread
                )

                values.append(val)

            golden_rf.write_warp_gran(
                warp_id=warp,
                dest_operand=Bits(uint=reg, length=32),
                data=values
            )

    return golden_rf


def print_banks(dCache):
    # --- 1. Calculate Bit Widths for Reconstruction ---
    # Offset: 32 words * 4 bytes = 128 bytes -> 7 bits (usually)
    offset_bits = int(math.log2(BLOCK_SIZE_WORDS * 4))
    
    # Bank Bits: log2(number of banks)
    num_banks = len(dCache.banks)
    bank_bits = int(math.log2(num_banks)) if num_banks > 1 else 0
    
    # Set Bits: log2(number of sets per bank)
    num_sets = len(dCache.banks[0].sets)
    set_bits = int(math.log2(num_sets))

    # Calculate Shift Amounts (Assuming Addr Structure: [ Tag | Set | Bank | Offset ])
    shift_bank = offset_bits
    shift_set = offset_bits + bank_bits
    shift_tag = offset_bits + bank_bits + set_bits
    # --------------------------------------------------

    for bank_id, bank in enumerate(dCache.banks):
        print(f"\n======== Bank {bank_id} ========")
        found_valid_line = False

        for set_id, cache_set in enumerate(bank.sets):
            set_has_valid_lines = any(frame.valid for frame in cache_set)

            if set_has_valid_lines:
                found_valid_line = True
                print(f"  ---- Set {set_id} ----")

                lru_list = bank.lru[set_id]
                print(f"    LRU Order: {lru_list} (Front=MRU, Back=LRU)")

                for way_id, frame in enumerate(cache_set):
                    if frame.valid:
                        tag_hex = f"0x{frame.tag:X}"
                        dirty_str = "D" if frame.dirty else " "
                        
                        # --- 2. Reconstruct the Address ---
                        # (Tag << shifts) | (Set << shifts) | (Bank << shifts)
                        full_addr = (frame.tag << shift_tag) | (set_id << shift_set) | (bank_id << shift_bank)
                        addr_hex = f"0x{full_addr:08X}" # Format as 8-digit Hex
                        # ----------------------------------

                        # Print Tag AND Address
                        print(f"    [Way {way_id}] V:1 {dirty_str} Tag: {tag_hex:<6} (Addr: {addr_hex})")

                        for i in range(0, BLOCK_SIZE_WORDS, 4):
                            # FIX: Add '& 0xFFFFFFFF' to force unsigned 32-bit representation
                            w0 = f"0x{(frame.block[i] & 0xFFFFFFFF):08X}"
                            w1 = f"0x{(frame.block[i+1] & 0xFFFFFFFF):08X}"
                            w2 = f"0x{(frame.block[i+2] & 0xFFFFFFFF):08X}"
                            w3 = f"0x{(frame.block[i+3] & 0xFFFFFFFF):08X}"
                            
                            print(f"        Block[{i:02d}:{i+3:02d}]: {w0} {w1} {w2} {w3}")

        if not found_valid_line:
            print(f"  (Bank is empty)")

# ==============================================================================
# Runner
# ==============================================================================

def run_SM(program_file: Path | None = None, fmt: str | None = None, setup_name: str = "default"):
    uninit_regfile_out = FILE_ROOT / "pipeline_regfile_uninitialized_state.txt"
    init_regfile_out = FILE_ROOT / "pipeline_regfile_initialized_state.txt"
    fin_regfile_out = FILE_ROOT / "pipeline_regfile_final_state.txt"

    uninit_mem_out = FILE_ROOT / "pipeline_mem_uninitialized_state.txt"
    init_mem_out = FILE_ROOT / "pipeline_mem_initialized_state.txt"
    fin_mem_out = FILE_ROOT / "pipeline_mem_final_state.txt"
    fin_prf_out = FILE_ROOT / "predicate_regfile_final_state.txt"

    sm_config = load_sm_config("configs/sm_config.yaml")

    if program_file is None:
        program_file = FILE_ROOT / sm_config.test_file
    else:
        program_file = Path(program_file)

    if fmt is None:
        fmt = sm_config.test_file_type

    sm_config.test_file = program_file
    sm_config.test_file_type = fmt

    print("Loading program:", program_file)
    print("Using setup:", setup_name)
    print("Format:", fmt)

    words = load_program(program_file, fmt)
    print("Instructions loaded:", len(words))

    sm = SM(sm_config)

    with open(uninit_regfile_out, "w") as f:
        sm.regfile.dump(file=f)
        print(f"Dumped uninitialized register file to {uninit_regfile_out}")

    sm.mem.dump(uninit_mem_out)
    print(f"Dumped uninitialized mem file to {uninit_mem_out}")

    apply_local_setup(sm, setup_name)

    with open(init_regfile_out, "w") as f:
        sm.regfile.dump(file=f)
        print(f"Dumped initialized register file to {init_regfile_out}")

    sm.mem.dump(init_mem_out)
    print(f"Dumped initialized memory to {init_mem_out}")

    cycles = len(words)

    print("Running pipeline for", cycles, "cycles")
    for _ in range(cycles):
        sm.compute()

    flush = cycles + 2000
    print("Flushing pipeline", flush)
    for _ in range(flush):
        sm.compute()

    with open(fin_regfile_out, "w") as f:
        sm.regfile.dump(file=f)
        print(f"Dumped regfile final state to {fin_regfile_out}")

    with open(fin_prf_out, "w") as f:
        sm.prf.dump(file=f)
        print(f"Dumped predicate rf final state to {fin_prf_out}")

    sm.mem.dump(fin_mem_out)
    print(f"Dumped memory final state to {fin_mem_out}")

    print_banks(sm.dcache)
    print(sm.scheduler.warp_table)

    return sm.regfile

# ==============================================================================
# Main
# ==============================================================================

if __name__ == "__main__":
    args = _parse_args()

    pipeline_rf = run_SM(
        program_file=args.program,
        fmt=args.fmt,
        setup_name=args.setup,
    )