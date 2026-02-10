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
    # If anything fails, the error details go here:
    error_log="$DIFF_DIR/${test_name}_error_log.txt"
    
    # Artifacts (Only created on diff failure)
    saved_gen="$DIFF_DIR/${test_name}_generated.hex"
    saved_exp="$DIFF_DIR/${test_name}_expected.hex"

    # 1. Check for Expected Data Fragment
    if [ ! -f "$expected_file_fragment" ]; then
        echo -e "${YELLOW}[SKIP]${NC} $test_name (No expected data file)"
        continue
    fi

    # --------------------------------------
    # 2. Run Assembler -> meminit.hex
    # --------------------------------------
    # Capture ALL output (stdout + stderr) to temp log
    python3 "$ASSEMBLER_SCRIPT" "$asm_file" "$ASM_OUTPUT" hex "$OPCODES" > "$TEMP_CMD_LOG" 2>&1
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR]${NC} $test_name: Assembler crashed."
        # Move the captured output to the final error log
        mv "$TEMP_CMD_LOG" "$error_log"
        ((FAIL_COUNT++))
        continue
    fi

    # --------------------------------------
    # 3. Construct "Final Expected" File
    # --------------------------------------
    # A. Format instructions
    awk '{printf "0x%08x 0x%s\n", (NR-1)*4, $0}' "$ASM_OUTPUT" > "$TEMP_FORMATTED_INSTR"

    # B. Concatenate
    cat "$TEMP_FORMATTED_INSTR" "$expected_file_fragment" > "$FINAL_EXPECTED"

    # --------------------------------------
    # 4. Run Emulator (Make) -> memsim.hex
    # --------------------------------------
    # Capture ALL output (stdout + stderr) to temp log
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
    # 5. Compare
    # --------------------------------------
    # We save the diff output directly to the error log variable
    diff -u -w -i "$EMU_OUTPUT" "$FINAL_EXPECTED" > "$error_log"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[PASS]${NC}   $test_name"
        # Test Passed: Remove the empty error log
        rm -f "$error_log"
        ((PASS_COUNT++))
    else
        echo -e "${RED}[FAIL]${NC}   $test_name"
        # Test Failed: We keep $error_log (which now contains the diff)
        
        # Also save the raw files for debugging
        cp "$EMU_OUTPUT" "$saved_gen"
        cp "$FINAL_EXPECTED" "$saved_exp"
        
        ((FAIL_COUNT++))
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