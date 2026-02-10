#!/bin/bash

# ==========================================
# Configuration
# ==========================================
ASSEMBLER_SCRIPT="../assembler/assembler.py"
OPCODES="../assembler/opcodes.txt"
TEST_DIR="tests/unit_tests/simple_tests/tests"
EXPECTED_DIR="tests/unit_tests/simple_tests/expected"
DIFF_DIR="test_diffs"

# File names
ASM_OUTPUT="meminit.hex"      # Output from assembler
EMU_OUTPUT="memsim.hex"       # Output from emulator

# Intermediate files
TEMP_FORMATTED_INSTR="temp_instr.hex"
FINAL_EXPECTED="final_expected_combined.hex"
TEMP_CMD_LOG="temp_command_output.txt" # Captures stdout/stderr of current tool

# Suffix mapping
EXPECTED_SUFFIX="_exp_32.hex"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASS_COUNT=0
FAIL_COUNT=0

# ==========================================
# Argument Parsing
# ==========================================
if [ -z "$1" ]; then
    SEARCH_PATTERN="*.s"
else
    SEARCH_PATTERN="$1"
fi

# Setup Output Directory
mkdir -p "$DIFF_DIR"

# Clean diffs matching the current pattern
if [ "$SEARCH_PATTERN" == "*.s" ]; then
    rm -f "$DIFF_DIR"/*
else
    rm -f "$DIFF_DIR"/${SEARCH_PATTERN%.*}.*
fi

echo "========================================"
echo "      Starting Full System Tests"
echo "      Pattern: $SEARCH_PATTERN"
echo "========================================"

if [ ! -d "$TEST_DIR" ]; then
    echo -e "${RED}Error:${NC} Test directory $TEST_DIR not found."
    exit 1
fi

files_found=$(ls "$TEST_DIR"/$SEARCH_PATTERN 2>/dev/null)

if [ -z "$files_found" ]; then
    echo -e "${RED}Error:${NC} No files found matching '$SEARCH_PATTERN' in $TEST_DIR"
    exit 1
fi

for asm_file in $files_found; do
    test_name=$(basename "$asm_file" .s)
    expected_file_fragment="$EXPECTED_DIR/${test_name}${EXPECTED_SUFFIX}"
    
    # --------------------------------------
    # Define Per-Test Log Files
    # --------------------------------------
    error_log="$DIFF_DIR/${test_name}_error_log.txt"
    saved_gen="$DIFF_DIR/${test_name}_generated.hex"
    saved_exp="$DIFF_DIR/${test_name}_expected.hex"

    # Flag to track if we have expected data to compare against
    has_expected=1
    if [ ! -f "$expected_file_fragment" ]; then
        has_expected=0
    fi

    # --------------------------------------
    # 1. Run Assembler -> meminit.hex
    # --------------------------------------
    python3 "$ASSEMBLER_SCRIPT" "$asm_file" "$ASM_OUTPUT" hex "$OPCODES" > "$TEMP_CMD_LOG" 2>&1
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR]${NC} $test_name: Assembler crashed."
        mv "$TEMP_CMD_LOG" "$error_log"
        ((FAIL_COUNT++))
        continue
    fi

    # --------------------------------------
    # 2. Run Emulator (Make) -> memsim.hex
    # --------------------------------------
    make > "$TEMP_CMD_LOG" 2>&1
    make_status=$?

    if [ $make_status -ne 0 ]; then
        echo -e "${RED}[ERROR]${NC} $test_name: Make/Emulator command failed."
        mv "$TEMP_CMD_LOG" "$error_log"
        ((FAIL_COUNT++))
        continue
    fi

    if [ ! -f "$EMU_OUTPUT" ]; then
        echo -e "${RED}[ERROR]${NC} $test_name: Emulator did not produce $EMU_OUTPUT."
        echo "Make command finished successfully, but '$EMU_OUTPUT' was not found." > "$error_log"
        echo "Make Output:" >> "$error_log"
        cat "$TEMP_CMD_LOG" >> "$error_log"
        ((FAIL_COUNT++))
        continue
    fi

    # --------------------------------------
    # 3. Compare or Save
    # --------------------------------------
    if [ $has_expected -eq 0 ]; then
        # Case A: No Expected File -> Just Save Output
        cp "$EMU_OUTPUT" "$saved_gen"
        echo -e "${BLUE}[SAVE]${NC}   $test_name (No expected file, saved output)"
        # We do not increment PASS or FAIL counts
    else
        # Case B: Expected File Exists -> Construct Final Expected & Compare
        
        # Format instructions to match emulator output style
        awk '{printf "0x%08x 0x%s\n", (NR-1)*4, $0}' "$ASM_OUTPUT" > "$TEMP_FORMATTED_INSTR"

        # Concatenate: [Formatted Instructions] + [Expected Data Fragment]
        cat "$TEMP_FORMATTED_INSTR" "$expected_file_fragment" > "$FINAL_EXPECTED"

        # Compare
        diff -u -w -i "$EMU_OUTPUT" "$FINAL_EXPECTED" > "$error_log"
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[PASS]${NC}   $test_name"
            rm -f "$error_log"
            ((PASS_COUNT++))
        else
            echo -e "${RED}[FAIL]${NC}   $test_name"
            # Save artifacts for debugging
            cp "$EMU_OUTPUT" "$saved_gen"
            cp "$FINAL_EXPECTED" "$saved_exp"
            ((FAIL_COUNT++))
        fi
    fi

done

# Cleanup Intermediate Files
rm -f "$ASM_OUTPUT" "$EMU_OUTPUT" "$TEMP_FORMATTED_INSTR" "$FINAL_EXPECTED" "$TEMP_CMD_LOG"

echo "========================================"
echo "Tests Complete."
echo -e "Passed: ${GREEN}$PASS_COUNT${NC}"
echo -e "Failed: ${RED}$FAIL_COUNT${NC}"

if [ $FAIL_COUNT -gt 0 ]; then
    echo "Error logs saved in '$DIFF_DIR/'"
    exit 1
else
    exit 0
fi