#!/bin/bash

# ==========================================
# Configuration
# ==========================================
ASSEMBLER_SCRIPT="../assembler/assembler.py"
OPCODES="../assembler/opcodes.txt"
TEST_ROOT="tests"
DIFF_DIR="test_diffs"

# Intermediate files
RAW_ASM_OUTPUT="raw_instr.hex"        # Raw output from assembler (no addresses)
FORMATTED_INSTR="formatted_instr.hex" # Instructions with 0x0000 0x.... addresses
MEMINIT="meminit.hex"                 # Final input to emulator (Instr + Data)
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

    # --------------------------------------
    # 3. Find All Test Configurations
    # --------------------------------------
    # Find ALL expected files (saxpy_exp_t32.hex, saxpy_exp_t1024.hex, etc.)
    expected_files=$(find "$dir_name" -maxdepth 1 -name "${base_name}_exp_*.hex" | sort)

    # --------------------------------------
    # 4. Run Tests
    # --------------------------------------
    if [ -z "$expected_files" ]; then
        # --- CASE A: No Expected Files (Run Default) ---
        THREADS=32
        BLOCKS=1
        
        make run INPUT="$MEMINIT" THREADS="$THREADS" BLOCKS="$BLOCKS" > "$TEMP_CMD_LOG" 2>&1
        
        if [ $? -ne 0 ] || [ ! -f "$EMU_OUTPUT" ]; then
            echo -e "${RED}[RUN FAIL]${NC} $base_name (t=$THREADS)"
            mv "$TEMP_CMD_LOG" "$DIFF_DIR/${base_name}_run_error.log"
            ((FAIL_COUNT++))
        else
            echo -e "${YELLOW}[NO REF]${NC}   $base_name (t=$THREADS) - Output saved"
            cp "$EMU_OUTPUT" "$DIFF_DIR/${base_name}_gen.hex"
            cp "$MEMINIT" "$DIFF_DIR/${base_name}_meminit.hex" # <--- Added Dump
            ((MISSING_COUNT++))
        fi

    else
        # --- CASE B: Multiple Configurations ---
        for exp_file in $expected_files; do
            # Parse params
            THREADS=32
            BLOCKS=1
            if [[ "$exp_file" =~ _t([0-9]+) ]]; then THREADS="${BASH_REMATCH[1]}"; fi
            if [[ "$exp_file" =~ _b([0-9]+) ]]; then BLOCKS="${BASH_REMATCH[1]}"; fi
            
            # Unique Test ID
            test_id="${base_name}_t${THREADS}_b${BLOCKS}"
            error_log="$DIFF_DIR/${test_id}_error.log"

            # Run Emulator
            make run INPUT="$MEMINIT" THREADS="$THREADS" BLOCKS="$BLOCKS" > "$TEMP_CMD_LOG" 2>&1
            
            if [ $? -ne 0 ] || [ ! -f "$EMU_OUTPUT" ]; then
                echo -e "${RED}[RUN FAIL]${NC} $base_name (t=$THREADS, b=$BLOCKS)"
                cat "$TEMP_CMD_LOG" > "$error_log"
                cp "$MEMINIT" "$DIFF_DIR/${test_id}_meminit.hex" # <--- Added Dump
                ((FAIL_COUNT++))
                continue
            fi
            
            # Compare
            cat "$FORMATTED_INSTR" "$exp_file" > "$FINAL_EXPECTED"

            diff -u -w -i "$EMU_OUTPUT" "$FINAL_EXPECTED" > "$error_log"
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}[PASS]${NC}     $base_name (t=$THREADS, b=$BLOCKS)"
                rm -f "$error_log"
                ((PASS_COUNT++))
            else
                echo -e "${RED}[FAIL]${NC}     $base_name (t=$THREADS, b=$BLOCKS)"
                # Save all artifacts for debugging
                cp "$EMU_OUTPUT" "$DIFF_DIR/${test_id}_gen.hex"
                cp "$FINAL_EXPECTED" "$DIFF_DIR/${test_id}_exp.hex"
                cp "$MEMINIT" "$DIFF_DIR/${test_id}_meminit.hex" # <--- Added Dump
                ((FAIL_COUNT++))
            fi
        done
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
    echo "Check '$DIFF_DIR/' for logs and generated assembly."
    exit 1
fi
exit 0