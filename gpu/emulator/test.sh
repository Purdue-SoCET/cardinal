#!/bin/bash

# ==========================================
# Configuration
# ==========================================
ASSEMBLER_SCRIPT="../assembler/assembler.py"
OPCODES="../assembler/opcodes.txt"
TEST_ROOT="tests"
DIFF_DIR="test_diffs"

# Intermediate files
RAW_ASM_OUTPUT="raw_instr.hex"      # Raw output from assembler (no addresses)
FORMATTED_INSTR="formatted_instr.hex" # Instructions with 0x0000 0x.... addresses
MEMINIT="meminit.hex"               # Final input to emulator (Instr + Data)
EMU_OUTPUT="memsim.hex"             
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
SEARCH_PATTERN="${1:-*.s}"
if [[ "$SEARCH_PATTERN" != *".s" ]]; then SEARCH_PATTERN="$SEARCH_PATTERN.s"; fi

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
for asm_file in $files_found; do
    dir_name=$(dirname "$asm_file")
    base_name=$(basename "$asm_file" .s)
    
    # Logging paths
    error_log="$DIFF_DIR/${base_name}_error.log"
    saved_gen="$DIFF_DIR/${base_name}_gen.hex"
    saved_exp="$DIFF_DIR/${base_name}_exp.hex"

    # --------------------------------------
    # 1. Identify Resources
    # --------------------------------------
    # A. Expected Output
    expected_file=$(find "$dir_name" -maxdepth 1 -name "${base_name}_exp_*.hex" | head -n 1)

    # B. Input Data (Raw Hex with Addresses) <--- NEW: Looks for _data.hex
    input_data_file=$(find "$dir_name" -maxdepth 1 -name "${base_name}_data.hex" | head -n 1)

    # Default params
    THREADS=32
    BLOCKS=1
    has_expected=0

    # Parse Expected Params
    if [ -n "$expected_file" ]; then
        has_expected=1
        if [[ "$expected_file" =~ _t([0-9]+) ]]; then THREADS="${BASH_REMATCH[1]}"; fi
        if [[ "$expected_file" =~ _b([0-9]+) ]]; then BLOCKS="${BASH_REMATCH[1]}"; fi
    else
        ((MISSING_COUNT++))
    fi

    # --------------------------------------
    # 2. Run Assembler
    # --------------------------------------
    # Generates raw hex (DATADATA)
    python3 "$ASSEMBLER_SCRIPT" "$asm_file" "$RAW_ASM_OUTPUT" hex "$OPCODES" > "$TEMP_CMD_LOG" 2>&1
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ASM FAIL]${NC} $base_name"
        cat "$TEMP_CMD_LOG" > "$error_log"
        ((FAIL_COUNT++))
        continue
    fi

    # --------------------------------------
    # 3. Post-Process & Merge
    # --------------------------------------
    
    # A. Format Instructions: Add 0xADDR 0xDATA
    awk '{printf "0x%08x 0x%s\n", (NR-1)*4, $0}' "$RAW_ASM_OUTPUT" > "$FORMATTED_INSTR"

    # B. Create Final Memory Init File
    cat "$FORMATTED_INSTR" > "$MEMINIT"

    # C. Append Input Data (if it exists)
    if [ -n "$input_data_file" ]; then
        cat "$input_data_file" >> "$MEMINIT"
        # Optional: Add a newline if your emulator is picky about concatenation
        # echo "" >> "$MEMINIT" 
    fi

    # --------------------------------------
    # 4. Run Emulator
    # --------------------------------------
    make run INPUT="$MEMINIT" THREADS="$THREADS" BLOCKS="$BLOCKS" > "$TEMP_CMD_LOG" 2>&1
    
    if [ $? -ne 0 ] || [ ! -f "$EMU_OUTPUT" ]; then
        echo -e "${RED}[RUN FAIL]${NC} $base_name (t=$THREADS)"
        cat "$TEMP_CMD_LOG" > "$error_log"
        ((FAIL_COUNT++))
        continue
    fi

    # --------------------------------------
    # 5. Compare Results
    # --------------------------------------
    if [ $has_expected -eq 0 ]; then
        cp "$EMU_OUTPUT" "$saved_gen"
        echo -e "${YELLOW}[NO REF]${NC}   $base_name (t=$THREADS)"
    else
        # We re-use FORMATTED_INSTR + Expected Data to build the "Perfect Golden" file
        # Note: We assume the expected file contains the final state of EVERYTHING relevant
        cat "$FORMATTED_INSTR" "$expected_file" > "$FINAL_EXPECTED"

        # Diff
        diff -u -w -i "$EMU_OUTPUT" "$FINAL_EXPECTED" > "$error_log"
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[PASS]${NC}     $base_name (t=$THREADS)"
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
rm -f "$RAW_ASM_OUTPUT" "$EMU_OUTPUT" "$FORMATTED_INSTR" "$FINAL_EXPECTED" "$TEMP_CMD_LOG" "$MEMINIT"

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