#!/bin/bash

# ==========================================
# test_hex.sh - Run emulator tests with .hex input directly (no assembler)
# Windows Git Bash compatible - uses python instead of make
# ==========================================

# ==========================================
# Configuration
# ==========================================
TEST_ROOT="tests"
DIFF_DIR="test_diffs"
EMULATOR="src/emulator.py"
DATA_START=0x20000000  # Address threshold: below = instructions, above = data

# Intermediate files (we never delete the user's input .hex)
MEMINIT="meminit.hex"                 # Working copy for emulator (may be temp)
EMU_OUTPUT="memsim.hex"
FINAL_EXPECTED="final_expected_combined.hex"
TEMP_CMD_LOG="temp_command_output.txt"
INSTR_PART="temp_instr_part.hex"       # Instruction section for comparison

# Python: prefer python3, fallback to python (Windows)
PYTHON=""
for p in python3 python; do
    if command -v "$p" &>/dev/null; then
        PYTHON="$p"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "Error: Neither python3 nor python found."
    exit 1
fi

# Counters
PASS_COUNT=0
FAIL_COUNT=0
MISSING_COUNT=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ==========================================
# Get first data-region address from hex file (addr >= DATA_START)
# Used as default argptr when -a not specified.
# ==========================================
get_first_data_addr() {
    local file="$1"
    "$PYTHON" -c "
import sys
data_start = 0x20000000
with open(sys.argv[1]) as f:
    for line in f:
        line = line.split('//')[0].split('#')[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 1 and parts[0].startswith('0x'):
            addr = int(parts[0], 16)
            if addr >= data_start:
                print(f'0x{addr:08X}')
                sys.exit(0)
print('0x20000000')
" "$file"
}

# ==========================================
# Sort hex file by address (ascending) for stable diff comparison
# Format: 0xADDR 0xDATA per line
# ==========================================
sort_hex_by_addr() {
    local file="$1"
    [ ! -f "$file" ] && return 0
    "$PYTHON" -c "
import sys
import re
path = sys.argv[1]
pattern = re.compile(r'^\s*(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s*')
lines = []
with open(path) as f:
    for line in f:
        line = line.rstrip('\n\r')
        m = pattern.match(line.split('//')[0].split('#')[0].strip())
        if m:
            addr = int(m.group(1), 16)
            lines.append((addr, line))
        else:
            lines.append((-1, line))  # non-addr lines sort first
lines.sort(key=lambda x: (0 if x[0] < 0 else 1, x[0] if x[0] >= 0 else 0))
with open(path, 'w') as f:
    for _, ln in lines:
        f.write(ln + '\n')
" "$file"
}

# ==========================================
# Run emulator (replaces: make run INPUT=... THREADS=... BLOCKS=...)
# ==========================================
run_emulator() {
    local input_path="$1"
    local threads="$2"
    local blocks="$3"
    local extra_args=()
    [ -n "$LOG_THREAD" ] && extra_args+=(--log-thread "$LOG_THREAD")
    "$PYTHON" "$EMULATOR" -t "$threads" -b "$blocks" --start-pc 0 --mem-format hex --arg-pointer "$ARGPTR" "${extra_args[@]}" "$input_path"
}

# ==========================================
# Setup - change to script directory (Windows-friendly)
# ==========================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# ==========================================
# Parse arguments: -t/--threads (1-1024), -a/--argptr, -l/--log-thread
# ==========================================
THREADS_OVERRIDE=""
ARGPTR=""  # default: first data-region addr in input file
LOG_THREAD=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -t|--threads)
            THREADS_OVERRIDE="$2"
            shift 2
            ;;
        -a|--argptr)
            ARGPTR="$2"
            shift 2
            ;;
        -l|--log-thread)
            LOG_THREAD="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [-t N] [-a ADDR] [-l TID] <path/to/file.hex>"
            echo "  -t, --threads N    Number of threads (1-1024)"
            echo "  -a, --argptr ADDR  Argument pointer address (default: first data addr in input)"
            echo "  -l, --log-thread TID  Only log trace for this thread (0-31)"
            exit 0
            ;;
        *)
            HEX_FILE="$1"
            shift
            ;;
    esac
done

if [ -z "${HEX_FILE:-}" ]; then
    echo -e "${RED}Error:${NC} Usage: $0 [-t N] [-a ADDR] <path/to/file.hex>"
    exit 1
fi

# Validate threads override if provided
if [ -n "$THREADS_OVERRIDE" ]; then
    if ! [[ "$THREADS_OVERRIDE" =~ ^[0-9]+$ ]] || [ "$THREADS_OVERRIDE" -lt 1 ] || [ "$THREADS_OVERRIDE" -gt 1024 ]; then
        echo -e "${RED}Error:${NC} Threads must be between 1 and 1024 (got: $THREADS_OVERRIDE)"
        exit 1
    fi
fi

# Paths are relative to emulator dir (we cd'd to script dir above)

if [ ! -f "$HEX_FILE" ]; then
    echo -e "${RED}Error:${NC} File not found: $HEX_FILE"
    exit 1
fi

# Derive base name and directory for expected files
dir_name=$(dirname "$HEX_FILE")
base_name=$(basename "$HEX_FILE" .hex)

mkdir -p "$DIFF_DIR"
rm -f "$MEMINIT" "$EMU_OUTPUT" "$FINAL_EXPECTED" "$TEMP_CMD_LOG" "$INSTR_PART"
# Note: we never delete the user's input file

# ==========================================
# 1. Prepare MEMINIT
# ==========================================
# Check if file is pre-formatted (0xADDR 0xDATA) or raw (single hex per line)
first_line=$(head -n 1 "$HEX_FILE" | tr -d '\r')
part_count=$(echo "$first_line" | awk '{print NF}')

if [ "$part_count" -eq 2 ]; then
    # Pre-formatted: use as MEMINIT directly (copy, don't modify original)
    cp "$HEX_FILE" "$MEMINIT"
else
    # Raw format: add addresses like assembler output
    awk '{v=$0; gsub(/^0x/,"",v); printf "0x%08x 0x%s\n", (NR-1)*4, v}' "$HEX_FILE" > "$MEMINIT"
    # Optionally append _data.hex if present
    input_data_file=$(find "$dir_name" -maxdepth 1 -name "${base_name}_data.hex" 2>/dev/null | head -n 1)
    if [ -n "$input_data_file" ]; then
        cat "$input_data_file" >> "$MEMINIT"
    fi
fi

# Use MEMINIT for emulator (we created it from user's file)
INPUT_TO_USE="$MEMINIT"

# Set default argptr from first data address if not overridden by -a
if [ -z "$ARGPTR" ]; then
    ARGPTR=$(get_first_data_addr "$INPUT_TO_USE")
fi

echo "========================================"
echo "      GPU Emulator - Hex Input Test"
echo "      Input:   $HEX_FILE"
echo "      Base:    $base_name"
echo "      Argptr:  $ARGPTR"
echo "========================================"

# ==========================================
# 2. Extract instruction part for comparison (addr < 0x20000000)
# ==========================================
# Portable: lines with addr 0x0xxxxxxx or 0x1xxxxxxx (code region)
grep -E '^0x[01][0-9a-fA-F]{7}[[:space:]]' "$INPUT_TO_USE" > "$INSTR_PART" 2>/dev/null || true
if [ ! -s "$INSTR_PART" ]; then
    touch "$INSTR_PART"  # empty if no instruction region (e.g. data-only file)
fi

# ==========================================
# 3. Find expected files and run tests
# ==========================================
expected_files=$(find "$dir_name" -maxdepth 1 -name "${base_name}_exp_*.hex" 2>/dev/null | sort)

# If threads override is set, use it and run single config (compare only if matching expected exists)
if [ -n "$THREADS_OVERRIDE" ]; then
    THREADS="$THREADS_OVERRIDE"
    BLOCKS=1
    exp_file=$(find "$dir_name" -maxdepth 1 -name "${base_name}_exp_t${THREADS}_b${BLOCKS}.hex" 2>/dev/null | head -n 1)

    run_emulator "$INPUT_TO_USE" "$THREADS" "$BLOCKS" > "$TEMP_CMD_LOG" 2>&1

    if [ $? -ne 0 ] || [ ! -f "$EMU_OUTPUT" ]; then
        echo -e "${RED}[RUN FAIL]${NC} $base_name (t=$THREADS, b=$BLOCKS)"
        mv "$TEMP_CMD_LOG" "$DIFF_DIR/${base_name}_run_error.log"
        cp "$INPUT_TO_USE" "$DIFF_DIR/${base_name}_meminit.hex"
        ((FAIL_COUNT++))
    elif [ -z "$exp_file" ]; then
        echo -e "${YELLOW}[NO REF]${NC}   $base_name (t=$THREADS, b=$BLOCKS) - Output saved"
        sort_hex_by_addr "$EMU_OUTPUT"
        cp "$EMU_OUTPUT" "$DIFF_DIR/${base_name}_gen.hex"
        cp "$INPUT_TO_USE" "$DIFF_DIR/${base_name}_meminit.hex"
        ((MISSING_COUNT++))
    else
        test_id="${base_name}_t${THREADS}_b${BLOCKS}"
        error_log="$DIFF_DIR/${test_id}_error.log"
        cat "$INSTR_PART" "$exp_file" > "$FINAL_EXPECTED"
        sort_hex_by_addr "$EMU_OUTPUT"
        sort_hex_by_addr "$FINAL_EXPECTED"
        diff -u -w -i "$EMU_OUTPUT" "$FINAL_EXPECTED" > "$error_log"
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[PASS]${NC}     $base_name (t=$THREADS, b=$BLOCKS)"
            rm -f "$error_log"
            ((PASS_COUNT++))
        else
            echo -e "${RED}[FAIL]${NC}     $base_name (t=$THREADS, b=$BLOCKS)"
            cp "$EMU_OUTPUT" "$DIFF_DIR/${test_id}_gen.hex"
            cp "$FINAL_EXPECTED" "$DIFF_DIR/${test_id}_exp.hex"
            cp "$INPUT_TO_USE" "$DIFF_DIR/${test_id}_meminit.hex"
            cp "$TEMP_CMD_LOG" "$DIFF_DIR/${test_id}_trace.log"
            ((FAIL_COUNT++))
        fi
    fi
elif [ -z "$expected_files" ]; then
    # --- No expected files: run with default config ---
    THREADS=32
    BLOCKS=1

    run_emulator "$INPUT_TO_USE" "$THREADS" "$BLOCKS" > "$TEMP_CMD_LOG" 2>&1

    if [ $? -ne 0 ] || [ ! -f "$EMU_OUTPUT" ]; then
        echo -e "${RED}[RUN FAIL]${NC} $base_name (t=$THREADS)"
        mv "$TEMP_CMD_LOG" "$DIFF_DIR/${base_name}_run_error.log"
        cp "$INPUT_TO_USE" "$DIFF_DIR/${base_name}_meminit.hex"
        ((FAIL_COUNT++))
    else
        echo -e "${YELLOW}[NO REF]${NC}   $base_name (t=$THREADS) - Output saved"
        sort_hex_by_addr "$EMU_OUTPUT"
        cp "$EMU_OUTPUT" "$DIFF_DIR/${base_name}_gen.hex"
        cp "$INPUT_TO_USE" "$DIFF_DIR/${base_name}_meminit.hex"
        ((MISSING_COUNT++))
    fi
else
    # --- Multiple configurations from expected files ---
    for exp_file in $expected_files; do
        THREADS=32
        BLOCKS=1
        if [[ "$exp_file" =~ _t([0-9]+) ]]; then THREADS="${BASH_REMATCH[1]}"; fi
        if [[ "$exp_file" =~ _b([0-9]+) ]]; then BLOCKS="${BASH_REMATCH[1]}"; fi

        test_id="${base_name}_t${THREADS}_b${BLOCKS}"
        error_log="$DIFF_DIR/${test_id}_error.log"

        run_emulator "$INPUT_TO_USE" "$THREADS" "$BLOCKS" > "$TEMP_CMD_LOG" 2>&1

        if [ $? -ne 0 ] || [ ! -f "$EMU_OUTPUT" ]; then
            echo -e "${RED}[RUN FAIL]${NC} $base_name (t=$THREADS, b=$BLOCKS)"
            cat "$TEMP_CMD_LOG" > "$error_log"
            cp "$INPUT_TO_USE" "$DIFF_DIR/${test_id}_meminit.hex"
            ((FAIL_COUNT++))
            continue
        fi

        # Build FINAL_EXPECTED = instruction part + expected output
        cat "$INSTR_PART" "$exp_file" > "$FINAL_EXPECTED"
        sort_hex_by_addr "$EMU_OUTPUT"
        sort_hex_by_addr "$FINAL_EXPECTED"

        diff -u -w -i "$EMU_OUTPUT" "$FINAL_EXPECTED" > "$error_log"

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[PASS]${NC}     $base_name (t=$THREADS, b=$BLOCKS)"
            rm -f "$error_log"
            ((PASS_COUNT++))
        else
            echo -e "${RED}[FAIL]${NC}     $base_name (t=$THREADS, b=$BLOCKS)"
            cp "$EMU_OUTPUT" "$DIFF_DIR/${test_id}_gen.hex"
            cp "$FINAL_EXPECTED" "$DIFF_DIR/${test_id}_exp.hex"
            cp "$INPUT_TO_USE" "$DIFF_DIR/${test_id}_meminit.hex"
            cp "$TEMP_CMD_LOG" "$DIFF_DIR/${test_id}_trace.log"
            ((FAIL_COUNT++))
        fi
    done
fi

# ==========================================
# Cleanup (never delete user's input file)
# ==========================================
rm -f "$MEMINIT" "$EMU_OUTPUT" "$FINAL_EXPECTED" "$TEMP_CMD_LOG" "$INSTR_PART"

echo "========================================"
echo "Summary"
echo -e "Passed:  ${GREEN}$PASS_COUNT${NC}"
echo -e "Failed:  ${RED}$FAIL_COUNT${NC}"
echo -e "No Ref:  ${YELLOW}$MISSING_COUNT${NC}"

if [ $FAIL_COUNT -gt 0 ]; then
    echo "Check '$DIFF_DIR/' for logs and generated output."
    exit 1
fi
exit 0
