#!/bin/bash
# ======================================================================
# GPU SYSTEM TEST AUTOMATION SCRIPT (test_sim.sh)
# ======================================================================
# Description:
# Automates the execution of GPU tests, comparing emulator (expected)
# vs. simulator (actual) memory dumps.
#
# Usage:
#   ./test_sim.sh [-1 | -2] [optional_search_pattern]
#
# Modes:
#   -1 (Default) : Assembly Mode. Compiles .s files from 'tests/', 
#                  generates memory init files, runs models, and diffs.
#                  Usage: ./test_sim.sh -1
#                  Usage: ./test_sim.sh -1 saxpy.s
#
#   -2           : Binary Mode. Takes pre-compiled .bin files from 
#                  'tests_bin/', converts to hex, runs models, and diffs.
#                  Usage: ./test_sim.sh -2
#                  Usage: ./test_sim.sh -2 math_test.bin
#
# Debugging:
#   If a test fails, check the 'test_diffs/' directory for detailed
#   logs, expected vs. actual hex dumps, and diff results.
# ======================================================================

# ==========================================
# Configuration
# ==========================================
ASSEMBLER_SCRIPT="../../../assembler/assembler.py"              # CHANGE THIS WHEN CHANGING DIRECTORY
OPCODES="../../../assembler/opcodes.txt"                        # CHANGE THIS WHEN CHANGING DIRECTORY
DIFF_DIR="test_diffs"

# Intermediate files
RAW_ASM_OUTPUT="raw_instr.hex"        # Raw output from assembler (no addresses)
FORMATTED_INSTR="formatted_instr.hex" # Instructions with 0x0000 0x.... addresses
MEMINIT="meminit.hex"                 # Final input to emulator (Instr + Data)
MEMINIT_BIN="meminit.bin"
EMU_OUTPUT="memgolden.hex"
SIM_OUTPUT="memsim.hex"          
FINAL_EXPECTED="final_expected_combined.hex"
TEMP_CMD_LOG="temp_command_output.txt"


# Counters
PASS_COUNT=0
FAIL_COUNT=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ==========================================
# Option Parsing
# ==========================================
# Default to Option 1 if no flag is provided
RUN_OPTION=1

while getopts "12" opt; do
    case ${opt} in
        1 ) RUN_OPTION=1 ;;
        2 ) RUN_OPTION=2 ;;
        \? ) echo "Usage: $0 [-1] [-2] [search_pattern]"
             exit 1 ;;
    esac
done
# Shift the positional parameters so $1 becomes the search pattern again
shift $((OPTIND -1))

# ==========================================
# Setup
# ==========================================
if [ "$RUN_OPTION" -eq 1 ]; then
    TEST_ROOT="tests"
    SEARCH_PATTERN="${1:-*.s}"
    if [[ "$SEARCH_PATTERN" != *".s" ]]; then SEARCH_PATTERN="$SEARCH_PATTERN.s"; fi
elif [ "$RUN_OPTION" -eq 2 ]; then
    TEST_ROOT="tests_bin"
    SEARCH_PATTERN="${1:-*.bin}"
    if [[ "$SEARCH_PATTERN" != *".bin" ]]; then SEARCH_PATTERN="$SEARCH_PATTERN.bin"; fi
fi

mkdir -p "$DIFF_DIR"
rm -f "$DIFF_DIR"/*

echo "========================================"
echo "      Starting GPU System Tests"
echo "      Root:    $TEST_ROOT"
echo "      Pattern: $SEARCH_PATTERN"
echo "========================================"

files_found=$(find "$TEST_ROOT" -name "$SEARCH_PATTERN" | sort)

if [ -z "$files_found" ]; then
    echo -e "${RED}Error:${NC} No files found matching '$SEARCH_PATTERN'"
    exit 1
fi

# ==========================================
# Main Test Loop
# ==========================================
if [ "$RUN_OPTION" -eq 1 ]; then
    for asm_file in $files_found; do
        dir_name=$(dirname "$asm_file")
        base_name=$(basename "$asm_file" .s)
        # --------------------------------------
        # 1. Run Assembler (Run ONCE per source)
        # --------------------------------------
        # We generate the machine code once, as it doesn't change based on thread count.
        python3 "$ASSEMBLER_SCRIPT" "$asm_file" "$RAW_ASM_OUTPUT" hex "$OPCODES" > "$TEMP_CMD_LOG" 2>&1

        if [ $? -ne 0 ]; then
            echo -e "${RED}[ASM FAIL]${NC} $base_name"
            mv "$TEMP_CMD_LOG" "$DIFF_DIR/${base_name}_asm_error.log"
            ((FAIL_COUNT++))
            continue
        fi

        # --------------------------------------
        # 2. Prepare Base Memory Image
        # --------------------------------------
        # A. Format Instructions: Add 0xADDR 0xDATA
        awk '{printf "0x%08x 0x%s\n", (NR-1)*4, $0}' "$RAW_ASM_OUTPUT" > "$FORMATTED_INSTR"

        # B. Look for Input Data (e.g. saxpy_data.hex)
        input_data_file=$(find "$dir_name" -maxdepth 1 -name "${base_name}_data.hex" | head -n 1)

        # C. Create MEMINIT (Instructions + Optional Data)
        cat "$FORMATTED_INSTR" > "$MEMINIT"
        if [ -n "$input_data_file" ]; then
            cat "$input_data_file" >> "$MEMINIT"
        fi

        # Convert meminit.hex (Hex Data) to meminit_bin.txt (Binary Data)
        python3 hex_bin_converter.py h2b "$MEMINIT" "$MEMINIT_BIN"

        # --------------------------------------
        # 3. Run Tests
        # --------------------------------------
        THREADS=32
        BLOCKS=1

        # Run the emulator
        make run INPUT="$MEMINIT" THREADS="$THREADS" BLOCKS="$BLOCKS" > "$TEMP_CMD_LOG" 2>&1
        if [ -f "memsim.hex" ]; then
            mv memsim.hex memgolden.hex         # Rename the memory dump from the emulator as memgolden.hex
        fi

        # Run the simulator
        make simulator INPUT="$MEMINIT_BIN"

        # --------------------------------------
        # 3. Compare emulator and simulator output
        # --------------------------------------
        test_id="${base_name}_t${THREADS}_b${BLOCKS}"
        error_log="$DIFF_DIR/${test_id}_error.log"

        diff -u -w -i "$EMU_OUTPUT" "$SIM_OUTPUT" > "$error_log"

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[PASS]${NC}     $base_name (t=$THREADS, b=$BLOCKS)"
            rm -f "$error_log"
            ((PASS_COUNT++))
        else
            echo -e "${RED}[FAIL]${NC}     $base_name (t=$THREADS, b=$BLOCKS)"
            # Save all artifacts for debugging
            cp "$EMU_OUTPUT" "$DIFF_DIR/${test_id}_exp.hex"
            cp "$SIM_OUTPUT" "$DIFF_DIR/${test_id}_sim.hex"
            cp "$MEMINIT" "$DIFF_DIR/${test_id}_meminit.hex" # <--- Added Dump
            ((FAIL_COUNT++))
        fi
    done

elif [ "$RUN_OPTION" -eq 2 ]; then
    for bin_file in $files_found; do
        # Assuming that the binary files contain both the instruction and the data already combined
       
        # --------------------------------------
        # 1. Converting the binary to hex for emulator
        # --------------------------------------
        base_name=$(basename "$bin_file" .bin)
        hex_output="${base_name}_meminit.hex"
        
        # Convert the binary meminit to hex for emulator 
        python3 hex_bin_converter.py b2h "$bin_file" "$hex_output"

        # --------------------------------------
        # 2. Run Tests
        # --------------------------------------
        THREADS=32
        BLOCKS=1

        # Run the emulator
        make run INPUT="$hex_output" THREADS="$THREADS" BLOCKS="$BLOCKS" > "$TEMP_CMD_LOG" 2>&1
        if [ -f "memsim.hex" ]; then
            mv memsim.hex memgolden.hex         # Rename the memory dump from the emulator as memgolden.hex
        fi

        # Run the simulator
        make simulator INPUT="$bin_file"

        # --------------------------------------
        # 3. Compare emulator and simulator output
        # --------------------------------------
        test_id="${base_name}_t${THREADS}_b${BLOCKS}"
        error_log="$DIFF_DIR/${test_id}_error.log"

        diff -u -w -i "$EMU_OUTPUT" "$SIM_OUTPUT" > "$error_log"

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[PASS]${NC}     $base_name (t=$THREADS, b=$BLOCKS)"
            rm -f "$error_log"
            ((PASS_COUNT++))
        else
            echo -e "${RED}[FAIL]${NC}     $base_name (t=$THREADS, b=$BLOCKS)"
            # Save all artifacts for debugging
            cp "$EMU_OUTPUT" "$DIFF_DIR/${test_id}_exp.hex"
            cp "$SIM_OUTPUT" "$DIFF_DIR/${test_id}_sim.hex"
            cp "$hex_output" "$DIFF_DIR/${test_id}_meminit.hex" # <--- Added Dump
            ((FAIL_COUNT++))
        fi

        rm -f "$hex_output"   
    done
fi

# ==========================================
# Cleanup
# ==========================================
rm -f "$RAW_ASM_OUTPUT" "$EMU_OUTPUT" "$SIM_OUTPUT" "$FORMATTED_INSTR" "$FINAL_EXPECTED" "$TEMP_CMD_LOG" "$MEMINIT" "$MEMINIT_BIN"

echo "========================================"
echo "Summary"
echo -e "Passed:  ${GREEN}$PASS_COUNT${NC}"
echo -e "Failed:  ${RED}$FAIL_COUNT${NC}"

if [ $FAIL_COUNT -gt 0 ]; then
    echo "Check '$DIFF_DIR/' for logs and generated assembly."
    exit 1
fi
exit 0