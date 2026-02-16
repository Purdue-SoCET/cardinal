#!/bin/bash

# ==========================================
# Configuration
# ==========================================
ASSEMBLER_SCRIPT="../assembler/assembler.py"
OPCODES="../assembler/opcodes.txt"
TEST_ROOT="tests"
DIFF_DIR="test_diffs"

# Intermediate files
ASM_OUTPUT="meminit.hex"      # Assembler Output
EMU_OUTPUT="memsim.hex"       # Emulator Output (Fixed name from Makefile)
TEMP_FORMATTED_INSTR="temp_instr.hex"
FINAL_EXPECTED="final_expected_combined.hex"
TEMP_CMD_LOG="temp_command_output.txt" 

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
# Setup
# ==========================================
# Default pattern to all .s files if no argument provided
SEARCH_PATTERN="${1:-*.s}"
if [[ "$SEARCH_PATTERN" != *".s" ]]; then SEARCH_PATTERN="$SEARCH_PATTERN.s"; fi

mkdir -p "$DIFF_DIR"
rm -f "$DIFF_DIR"/*

echo "========================================"
echo "      Starting GPU System Tests"
echo "      Root:    $TEST_ROOT"
echo "      Pattern: $SEARCH_PATTERN"
echo "========================================"

# Find all test sources
files_found=$(find "$TEST_ROOT" -name "$SEARCH_PATTERN" | sort)

if [ -z "$files_found" ]; then
    echo -e "${RED}Error:${NC} No files found matching '$SEARCH_PATTERN'"
    exit 1
fi

# ==========================================
# Main Test Loop
# ==========================================
for asm_file in $files_found; do
    dir_name=$(dirname "$asm_file")
    base_name=$(basename "$asm_file" .s)
    
    # --------------------------------------
    # 1. Dynamic Expected File Search
    # --------------------------------------
    # Look for any file matching: [testname]_exp_*.hex in the same directory
    # This finds "add_exp_t32_b1.hex" automatically
    expected_file=$(find "$dir_name" -maxdepth 1 -name "${base_name}_exp_*.hex" | head -n 1)

    # Logging paths
    error_log="$DIFF_DIR/${base_name}_error.log"
    saved_gen="$DIFF_DIR/${base_name}_gen.hex"
    saved_exp="$DIFF_DIR/${base_name}_exp.hex"

    # Default params if no expected file found
    THREADS=32
    BLOCKS=1
    has_expected=0

    if [ -n "$expected_file" ]; then
        has_expected=1
        
        # --------------------------------------
        # 2. Parse Config from Filename
        # --------------------------------------
        # Extract matches for "t32" and "b1"
        if [[ "$expected_file" =~ _t([0-9]+) ]]; then THREADS="${BASH_REMATCH[1]}"; fi
        if [[ "$expected_file" =~ _b([0-9]+) ]]; then BLOCKS="${BASH_REMATCH[1]}"; fi
    else
        # If no expected file, we skip comparison but still run checks
        ((MISSING_COUNT++))
    fi

    # --------------------------------------
    # 3. Run Assembler
    # --------------------------------------
    python3 "$ASSEMBLER_SCRIPT" "$asm_file" "$ASM_OUTPUT" hex "$OPCODES" > "$TEMP_CMD_LOG" 2>&1
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ASM FAIL]${NC} $base_name"
        cat "$TEMP_CMD_LOG" > "$error_log"
        ((FAIL_COUNT++))
        continue
    fi

    # --------------------------------------
    # 4. Run Emulator (via Makefile)
    # --------------------------------------
    # We pass the dynamic THREADS and BLOCKS variables here
    make run INPUT="$ASM_OUTPUT" THREADS="$THREADS" BLOCKS="$BLOCKS" > "$TEMP_CMD_LOG" 2>&1
    
    if [ $? -ne 0 ] || [ ! -f "$EMU_OUTPUT" ]; then
        echo -e "${RED}[RUN FAIL]${NC} $base_name (t=$THREADS, b=$BLOCKS)"
        cat "$TEMP_CMD_LOG" > "$error_log"
        ((FAIL_COUNT++))
        continue
    fi

    # --------------------------------------
    # 5. Compare Results
    # --------------------------------------
    if [ $has_expected -eq 0 ]; then
        cp "$EMU_OUTPUT" "$saved_gen"
        echo -e "${YELLOW}[NO REF]${NC}   $base_name (Ran with defaults t=$THREADS, b=$BLOCKS)"
    else
        # Format Assembler output to align with Emulator dump format (Addr + Hex)
        awk '{printf "0x%08x 0x%s\n", (NR-1)*4, $0}' "$ASM_OUTPUT" > "$TEMP_FORMATTED_INSTR"
        
        # Combine [Instructions] + [Expected Data] to create the full Golden Reference
        cat "$TEMP_FORMATTED_INSTR" "$expected_file" > "$FINAL_EXPECTED"

        # Diff
        diff -u -w -i "$EMU_OUTPUT" "$FINAL_EXPECTED" > "$error_log"
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[PASS]${NC}     $base_name (t=$THREADS, b=$BLOCKS)"
            rm -f "$error_log"
            ((PASS_COUNT++))
        else
            echo -e "${RED}[FAIL]${NC}     $base_name"
            cp "$EMU_OUTPUT" "$saved_gen"
            cp "$FINAL_EXPECTED" "$saved_exp"
            ((FAIL_COUNT++))
        fi
    fi
done

# ==========================================
# Cleanup
# ==========================================
rm -f "$ASM_OUTPUT" "$EMU_OUTPUT" "$TEMP_FORMATTED_INSTR" "$FINAL_EXPECTED" "$TEMP_CMD_LOG"

echo "========================================"
echo "Summary"
echo -e "Passed:  ${GREEN}$PASS_COUNT${NC}"
echo -e "Failed:  ${RED}$FAIL_COUNT${NC}"
echo -e "No Ref:  ${YELLOW}$MISSING_COUNT${NC}"

if [ $FAIL_COUNT -gt 0 ]; then
    echo "Check '$DIFF_DIR/' for logs."
    exit 1
fi
exit 0