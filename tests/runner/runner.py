import sys
import json
import shutil
import argparse
from pathlib import Path

# Import our local modules
from schema import TestSuite, SchemaValidationError
from toolchain import run_script, compile_c, run_assembler, run_emulator, ToolchainError
from verifier import verify_memory

# Path Anchors
RUNNER_DIR = Path(__file__).resolve().parent
REPO_ROOT = RUNNER_DIR.parent.parent
BUILD_ROOT = REPO_ROOT / "test_builds"

# ANSI Colors for console output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def setup_workspace(suite_name: str, test_name: str) -> Path:
    """Creates an isolated, clean directory for the test artifacts."""
    # Sanitize names for folder creation
    safe_suite = suite_name.replace(" ", "_").lower()
    safe_test = test_name.replace(" ", "_").lower()
    
    workspace = BUILD_ROOT / safe_suite / safe_test
    
    # Wipe it if it already exists from a previous run
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    
    return workspace

def merge_hex_files(output_file: Path, base_hex: Path, consumes: list, workspace: Path):
    """Merges a compiled hex file with any consumed hex files into a single meminit.
    Overrides any consumed memory that overlaps with the new compiled code."""
    
    compiled_memory = {}
    max_compiled_addr = -1
    
    # 1. Parse compiled code (Unaddressed -> Explicitly Addressed)
    if base_hex.exists():
        with open(base_hex, 'r') as infile:
            addr = 0
            for line in infile:
                # Strip whitespace and comments
                line = line.split('#')[0].split(';')[0].strip()
                if not line:
                    continue
                
                # Format data to ensure it has a 0x prefix
                data = line.split()[0]
                if not data.lower().startswith("0x"):
                    data = f"0x{data}"
                    
                compiled_memory[addr] = data
                max_compiled_addr = addr
                
                # Assuming 32-bit instructions, increment address by 4 bytes. 
                # (Change to += 1 if your architecture is purely word-addressed)
                addr += 4 

    # 2. Parse and filter consumed memory dumps
    consumed_memory = {}
    for consume_file in consumes:
        consume_path = workspace / consume_file
        
        if not consume_path.exists():
            # Fallback to main repo (requires REPO_ROOT to be defined in scope)
            consume_path = REPO_ROOT / consume_file

        if consume_path.exists():
            with open(consume_path, 'r') as infile:
                for line in infile:
                    line = line.split('#')[0].split(';')[0].strip()
                    if not line or len(line.split()) < 2:
                        continue
                        
                    parts = line.split()
                    addr_str = parts[0]
                    data_str = parts[1]
                    
                    try:
                        addr_val = int(addr_str, 16)
                        # CRITICAL: Only keep consumed memory if it sits ABOVE the compiled code
                        if addr_val > max_compiled_addr:
                            consumed_memory[addr_val] = data_str
                    except ValueError:
                        continue # Skip badly formatted lines gracefully
        else:
            # Requires YELLOW and RESET to be defined in scope
            print(f"{YELLOW}[WARN] Consumed file '{consume_file}' not found in workspace or repo.{RESET}")

    # 3. Write the finalized, merged memory state
    with open(output_file, 'w') as outfile:
        # Write compiled code first in strict 0xADDRADDR 0xDATADATA format
        for addr in sorted(compiled_memory.keys()):
            outfile.write(f"0x{addr:08X} {compiled_memory[addr]}\n")
            
        # Add the debugging spacer if both segments exist
        if compiled_memory and consumed_memory:
            outfile.write("\n")
            
        # Write the filtered consumed data
        for addr in sorted(consumed_memory.keys()):
            # Ensure the address is zero-padded to 8 chars to match formatting
            outfile.write(f"0x{addr:08X} {consumed_memory[addr]}\n")

# Update the signature and the script block inside tests/runner/runner.py

def execute_pipeline(test, workspace: Path, suite_dir: Path) -> bool:
    """Executes a single test's pipeline stages sequentially."""
    for i, stage in enumerate(test.pipeline):
        print(f"    -> Running Stage {i+1}: {stage.name or stage.type}")
        
        try:
            if stage.type == "script":
                # --- NEW: Smart Command Path Resolution ---
                resolved_tokens = []
                for token in stage.command.split():
                    # Ignore CLI flags
                    if not token.startswith('-'): 
                        potential_file = suite_dir / token
                        # If the file exists next to suite.json, use its absolute path
                        if potential_file.is_file():
                            token = str(potential_file.resolve())
                    resolved_tokens.append(token)
                    
                final_command = " ".join(resolved_tokens)
                
                # Execute the resolved command
                output = run_script(final_command, cwd=workspace)
                with open(workspace / f"stage{i}_script.log", 'w') as f:
                    f.write(output)

            elif stage.type in ["c_source", "asm_source"]:
                # 1. Resolve source path (Dynamic resolution)
                potential_suite_src = suite_dir / stage.source
                
                # Check locally next to suite.json first, fallback to REPO_ROOT
                if potential_suite_src.is_file():
                    src_path = potential_suite_src
                else:
                    src_path = REPO_ROOT / stage.source
                    
                compiled_hex = workspace / f"stage{i}_compiled.hex"
                
                # 2. Compile or Assemble
                if stage.type == "c_source":
                    compile_c(src_path, compiled_hex, stage.compiler_flags, cwd=workspace)
                else:
                    run_assembler(src_path, compiled_hex, cwd=workspace)
                
                # 3. Handle Memory Dependencies (The Glue)
                meminit_hex = workspace / f"stage{i}_meminit.hex"
                consumes = stage.execution.consumes if stage.execution else []
                merge_hex_files(meminit_hex, compiled_hex, consumes, workspace)
                
                # Determine where the emulator should save its final state
                produces = stage.execution.produces_mem
                emulator_out_path = (workspace / produces) if produces else (workspace / "mem_dump.hex")

                # 4. Run the Emulator
                emulator_log = run_emulator(
                    meminit_file=meminit_hex,
                    threads=stage.execution.threads,
                    blocks=stage.execution.blocks,
                    output_file=emulator_out_path,
                    start_pc=stage.execution.start_pc,
                    arg_pointer=stage.execution.arg_pointer,
                    track_regfile=stage.execution.track_regfile,
                    print_zero=stage.execution.print_zero,
                    cwd=workspace
                )

                log_filename = f"stage{i}_emulator.log"
                with open(workspace / log_filename, 'w') as f:
                    f.write(emulator_log)
                
                # 5. Handle State Handoff
                # Assuming your emulator outputs its final state to a file named 'mem_dump.hex'
                emulator_dump = workspace / "mem_dump.hex"
                produces = stage.execution.produces_mem
                if produces and emulator_dump.exists():
                    shutil.move(emulator_dump, workspace / produces)

        except ToolchainError as e:
            print(f"      {RED}[ERROR] Toolchain Failed on Stage {i+1}{RESET}")
            with open(workspace / f"error_stage{i}.log", 'w') as f:
                f.write(f"COMMAND:\n{e.cmd}\n\nSTDOUT:\n{e.stdout}\n\nSTDERR:\n{e.stderr}")
            print(f"      ↳ See logs in {workspace.relative_to(REPO_ROOT)}")
            return False # Stop the pipeline on failure
            
    return True

def run_suite(json_path: Path):
    """Loads a suite.json and processes all tests within it."""
    print(f"\n========================================")
    print(f"Loading Suite: {json_path.relative_to(REPO_ROOT)}")
    print(f"========================================")

    try:
        with open(json_path, 'r') as f:
            raw_data = json.load(f)
        suite = TestSuite.from_dict(raw_data)
        suite.apply_shared_config()
    except SchemaValidationError as e:
        print(f"{RED}[SCHEMA ERROR] {e}{RESET}")
        return
    except json.JSONDecodeError:
        print(f"{RED}[JSON ERROR] Invalid JSON syntax in {json_path.name}{RESET}")
        return

    for test in suite.tests:
        print(f"\nRunning Test: {test.name}")
        workspace = setup_workspace(suite.suite_name, test.name)
        
        # 1. Execute the Pipeline
        pipeline_success = execute_pipeline(test, workspace, json_path.parent)
        if not pipeline_success:
            continue # Skip verification if pipeline crashed

# 2. Verification
        if test.verification:
            expected_name = test.verification.expected_file
            
            # --- NEW: Dynamic vs Static Expected File Resolution ---
            # 1. Check if the script generated it dynamically in the workspace
            expected_path = workspace / expected_name
            
            # 2. If not, assume it's a static file next to the suite.json
            if not expected_path.exists():
                expected_path = json_path.parent / expected_name
            # --------------------------------------------------------

            # Locate the actual output (either the final 'produces_mem' or default dump)
            
            final_stage = test.pipeline[-1]
            if test.verification.actual_file is not None:
                actual_path = workspace / test.verification.actual_file

            elif final_stage.execution and final_stage.execution.produces_mem:
                actual_path = workspace / final_stage.execution.produces_mem
            
            else:
                actual_path = workspace / "mem_dump.hex"

            if not expected_path.exists():
                print(f"  {RED}[FAIL]{RESET} Expected file not found: {expected_path}")
                continue
                
            if not actual_path.exists():
                print(f"  {RED}[FAIL]{RESET} Actual emulator dump not found: {actual_path}")
                continue

            result = verify_memory(
                actual_file=actual_path,
                expected_file=expected_path,
                start_hex=test.verification.check_start,
                end_hex=test.verification.check_end,
                float_tolerance=test.verification.float_tolerance
            )

            if result.passed:
                print(f"  {GREEN}[PASS]{RESET} {result.message}")
            else:
                print(f"  {RED}[FAIL]{RESET} {result.mismatches} mismatch(es).")
                diff_log = workspace / "verification_diff.log"
                with open(diff_log, 'w') as f:
                    f.write(result.message)
                print(f"  ↳ Diff saved to {diff_log.relative_to(REPO_ROOT)}")
        else:
            print(f"  {YELLOW}[WARN]{RESET} Test completed, but no verification block was defined.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPU Hardware Test Runner")
    parser.add_argument("suite", nargs="?", help="Path to a specific suite.json file to run.")
    args = parser.parse_args()

    if args.suite:
        target = Path(args.suite).resolve()
        if target.exists():
            run_suite(target)
        else:
            print(f"{RED}Error: Cannot find file {args.suite}{RESET}")
    else:
        # Auto-discover all suite.json files in tests/complex_tests/
        complex_tests_dir = REPO_ROOT / "tests" / "complex_tests"
        suites = list(complex_tests_dir.rglob("*suite.json"))
        
        if not suites:
            print(f"{YELLOW}No suite.json files found in {complex_tests_dir.relative_to(REPO_ROOT)}{RESET}")
        else:
            for suite_path in suites:
                run_suite(suite_path)