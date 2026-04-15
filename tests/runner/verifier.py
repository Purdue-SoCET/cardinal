import re
import struct
import math
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional, List

# ==========================================
# Data Models
# ==========================================
@dataclass
class VerificationResult:
    passed: bool
    message: str
    mismatches: int = 0

class VerifierError(Exception):
    """Raised when the verifier cannot parse the provided files."""
    pass

# ==========================================
# Core Logic
# ==========================================
def parse_hex_dump(filepath: Path) -> Dict[int, str]:
    """
    Parses a hex file into a dictionary.
    Expects format: 0xADDR 0xDATA (one pair per line).
    """
    mem = {}

    if not filepath.exists():
        raise VerifierError(f"File not found: {filepath}")

    with open(filepath, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = re.sub(r'(//|#).*', '', line).strip()
            if not line:
                continue

            tokens = line.split()
            if len(tokens) != 2:
                raise VerifierError(f"Invalid format on line {line_num} in {filepath.name}. Expected '0xADDR 0xDATA'. Got: '{line}'")

            addr_str, data_str = tokens

            if not addr_str.lower().startswith('0x'):
                raise VerifierError(f"Address missing '0x' prefix on line {line_num} in {filepath.name}: '{addr_str}'")
            
            try:
                addr = int(addr_str, 16)
            except ValueError:
                raise VerifierError(f"Cannot parse address '{addr_str}' as hex on line {line_num} in {filepath.name}")

            clean_data = data_str.upper().replace('0X', '0x')
            if not clean_data.startswith('0x'):
                clean_data = '0x' + clean_data
                
            mem[addr] = clean_data

    return mem

def hex_to_float32(hex_str: str) -> float:
    """
    Decodes a 32-bit hex string into an IEEE 754 float.
    Uses big-endian ('>f') mapping standard for hex dumps. 
    """
    clean_hex = hex_str.lower().replace('0x', '').zfill(8)
    try:
        return struct.unpack('>f', bytes.fromhex(clean_hex))[0]
    except (ValueError, struct.error):
        return float('nan')

def is_zero_value(val_str: str) -> bool:
    """Checks if a string represents a zero value or a MISSING memory marker."""
    if val_str == "MISSING":
        return True
    try:
        # Handles 0x00000000, 0x0, etc.
        return int(val_str, 16) == 0
    except ValueError:
        return False

def verify_memory(
    actual_file: Path, 
    expected_file: Path, 
    start_hex: Optional[str] = None, 
    end_hex: Optional[str] = None,
    float_tolerance: Optional[float] = None,
    allow_missing_zeros: bool = True
) -> VerificationResult:
    """
    Compares two hex files within an optional bounded memory region.
    If float_tolerance is provided, compares data as IEEE 754 floats.
    Treats missing actual values as 0 if allow_missing_zeros is True.
    """
    try:
        actual_mem = parse_hex_dump(actual_file)
        expected_mem = parse_hex_dump(expected_file)
    except VerifierError as e:
        return VerificationResult(passed=False, message=str(e))

    start_addr = int(start_hex, 16) if start_hex else 0
    end_addr = int(end_hex, 16) if end_hex else float('inf')

    target_addresses = [addr for addr in expected_mem.keys() if start_addr <= addr <= end_addr]

    if not target_addresses:
        return VerificationResult(
            passed=False, 
            message=f"No expected data found within bounds [{start_hex or 'START'} - {end_hex or 'END'}]."
        )

    mismatches = 0
    diff_output: List[str] = [
        f"--- {expected_file.name} (Expected)",
        f"+++ {actual_file.name} (Actual)"
    ]

    for addr in target_addresses:
        exp_val = expected_mem[addr]
        act_val = actual_mem.get(addr, "MISSING")

        is_match = False
        diff_text_exp = f"- {exp_val}"
        diff_text_act = f"+ {act_val}"

        # 1. Exact String Match
        if exp_val == act_val:
            is_match = True
            
        # 2. Missing Zero Match
        elif allow_missing_zeros and is_zero_value(exp_val) and is_zero_value(act_val):
            is_match = True
            
        # 3. Float Tolerance Match
        elif float_tolerance is not None and act_val != "MISSING":
            f_exp = hex_to_float32(exp_val)
            f_act = hex_to_float32(act_val)

            if not math.isnan(f_exp) and not math.isnan(f_act):
                if abs(f_exp - f_act) <= float_tolerance:
                    is_match = True
                else:
                    diff_text_exp += f" ({f_exp:e})"
                    diff_text_act += f" ({f_act:e})"

        if not is_match:
            mismatches += 1
            diff_output.append(f"@@ 0x{addr:08X} @@")
            diff_output.append(diff_text_exp)
            diff_output.append(diff_text_act)

    if mismatches > 0:
        return VerificationResult(
            passed=False,
            mismatches=mismatches,
            message="\n".join(diff_output)
        )

    return VerificationResult(
        passed=True,
        message=f"No differences found across {len(target_addresses)} addresses checked."
    )

# ==========================================
# Local Testing
# ==========================================
if __name__ == "__main__":
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_act.hex') as act_file, \
         tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='_exp.hex') as exp_file:
        
        # Expected
        exp_file.write("0x40000000 0x3F800000\n") # 1.0
        exp_file.write("0x40000004 0x00000000\n") # 0.0
        exp_file.write("0x40000008 0x40400000\n") # 3.0
        
        # Actual
        act_file.write("0x40000000 0x3F800001\n") # 1.0 (Match via float tolerance)
        # 0x40000004 is entirely MISSING from this file (Match via Missing Zero allowance)
        act_file.write("0x40000008 0x41000000\n") # 8.0 (Massive failure)
        
        act_path = Path(act_file.name)
        exp_path = Path(exp_file.name)

    print("--- Testing Missing Zero Forgiveness ---\n")
    
    result = verify_memory(act_path, exp_path, start_hex="0x40000000", end_hex="0x40000010", float_tolerance=0.001)
    
    if result.passed:
        print("[PASS] " + result.message)
    else:
        print(f"[FAIL] {result.mismatches} mismatch(es) found:")
        print(result.message)

    os.remove(act_path)
    os.remove(exp_path)