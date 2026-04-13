#!/usr/bin/env python3
"""
GPU SYSTEM TEST AUTOMATION SCRIPT (test_cardinal.py)

Automates the execution of GPU tests, comparing simulator output against
either emulator (golden model) or pre-generated expected files.

Usage:
  python3 test_cardinal.py --src {assembly|bin} --truth {emu|exp} [pattern]

Arguments:
  --src {assembly|bin}    Source file type to test
                          - assembly: Compile .s files
                          - bin: Use pre-compiled .bin files
                          
  --truth {emu|exp}       Ground truth source to compare against
                          - emu: Run emulator as golden model
                          - exp: Compare against pre-generated expected files
                          
  pattern                 Optional search pattern for test files
                          (e.g., "*.s", "saxpy*", "unit/", "program/*.bin")
  
  --debug-file FILE       Write debug output to results/debug/<FILE>
  
  --debug-dual-output     Write debug output to both terminal and file
                          (use with --debug-file)

Examples:
  # Test assembly files against emulator output (compile & compare)
  python3 test_cardinal.py --src assembly --truth emu
  
  # Test assembly files against expected files (compile & compare to golden)
  python3 test_cardinal.py --src assembly --truth exp
  
  # Test binary files against emulator output
  python3 test_cardinal.py --src bin --truth emu
  
  # Test binary files against expected files
  python3 test_cardinal.py --src bin --truth exp
  
  # Test only unit directory
  python3 test_cardinal.py --src assembly --truth emu unit/
  
  # Test specific pattern
  python3 test_cardinal.py --src assembly --truth emu saxpy*
  
  # Test with debug output to file only
  python3 test_cardinal.py --src bin --truth exp --debug-file test_debug.log
  
  # Test with debug output to both terminal and file
  python3 test_cardinal.py --src bin --truth exp --debug-file test_debug.log --debug-dual-output

Debugging:
  If a test fails, check the 'test_diffs/' directory for detailed
  logs, expected vs. actual hex dumps, and diff results.
  
  Thread Count Validation:
  The test runner validates that thread counts are consistent across:
  1. Directory structure (e.g., pixel/t1024/ -> 1024 threads)
  2. Expected file path (e.g., program/pixel/t1024/pixel.hex -> 1024 threads)
  3. MMIO configuration in meminit (when TBS is enabled)
  
  If thread counts don't match, the test fails with a validation error.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass
import io
from contextlib import redirect_stdout, redirect_stderr

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import get_settings

# Import SM class from simulator
from simulator.sm import SM


# Colors for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[0;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color


class DebugLogger:
    """Handles debug output to both terminal and file."""
    
    def __init__(self, debug_file: Optional[Path] = None, dual_output: bool = False):
        """Initialize debug logger.
        
        Args:
            debug_file: Optional file to write debug output to
            dual_output: If True, write to both terminal and file; if False, only write to file
        """
        self.debug_file = debug_file
        self.dual_output = dual_output
        self.file_handle = None
        
        if self.debug_file:
            self.debug_file.parent.mkdir(parents=True, exist_ok=True)
            self.file_handle = open(self.debug_file, 'w')
    
    def write(self, message: str):
        """Write a debug message.
        
        Args:
            message: Message to write
        """
        if self.dual_output or not self.debug_file:
            print(message)
        
        if self.debug_file and self.file_handle:
            self.file_handle.write(message + '\n')
            self.file_handle.flush()
    
    def close(self):
        """Close debug file."""
        if self.file_handle:
            self.file_handle.close()
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()


@dataclass
class TestResult:
    """Result of a test execution."""
    name: str
    passed: bool
    threads: int
    blocks: int
    error_log: Optional[str] = None


class GPUTestRunner:
    """Main test runner class."""
    
    def __init__(self, src: Optional[str] = None, truth: Optional[str] = None, search_pattern: Optional[str] = None, config_path: Optional[Path] = None, clean: bool = False, skip_cleanup: bool = False, enable_cycle_limit: bool = False, max_cycles: Optional[int] = None, debug_file: Optional[Path] = None, debug_dual_output: bool = False):
        """Initialize the test runner.
        
        Args:
            src: Source type ("assembly" or "bin")
            truth: Truth type ("emu" or "exp")
            search_pattern: Optional file pattern to search for
            config_path: Optional path to config file
            clean: If True, clean results/ directory before running
            skip_cleanup: If True, skip cleanup after tests run
            enable_cycle_limit: If True, enforce a max cycle limit
            max_cycles: Maximum cycles to run (only used if enable_cycle_limit is True)
            debug_file: Optional path to debug output file (in results/debug/)
            debug_dual_output: If True, write debug output to both terminal and file
        """
        # Validate arguments only if running tests
        if src is not None and src not in ("assembly", "bin"):
            raise ValueError(f"Invalid src: {src}. Must be 'assembly' or 'bin'")
        if truth is not None and truth not in ("emu", "exp"):
            raise ValueError(f"Invalid truth: {truth}. Must be 'emu' or 'exp'")
        
        self.src = src
        self.truth = truth
        self.clean = clean
        self.skip_cleanup = skip_cleanup
        self.enable_cycle_limit = enable_cycle_limit
        self.max_cycles = max_cycles or 100000
        self.settings = get_settings(config_path)
        self.pass_count = 0
        self.fail_count = 0
        self.debug_dual_output = debug_dual_output
        
        # Setup debug logger
        if debug_file:
            debug_path = Path("results/debug") / debug_file
        else:
            debug_path = None
        self.debug_logger = DebugLogger(debug_path, debug_dual_output)
        
        # Clean results directory if requested
        if self.clean:
            self._clean_results()
        
        # Only set up test paths if running tests
        if src is not None:
            # Determine test root based on source type
            if src == "assembly":
                self.test_root = self.settings.directories.test_root_asm
                file_ext = ".s"
            else:  # bin
                self.test_root = self.settings.directories.test_root_bin
                file_ext = ".bin"
            
            # Use provided pattern or default
            self.search_pattern = search_pattern or self.settings.test_parameters.default_pattern
            
            # Append file extension if needed
            if not self.search_pattern.endswith(file_ext) and '/' not in self.search_pattern:
                # Only append extension if it's not a directory pattern
                if not self.search_pattern.endswith('/'):
                    self.search_pattern += file_ext
        
        # Setup results directory (for all output files)
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
        
        # Setup diff directory
        self.diff_dir = Path(self.settings.directories.diff_dir)
        self.diff_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean previous diff files
        for file in self.diff_dir.glob('*'):
            file.unlink()
    
    def run_command(self, cmd: List[str], log_file: Optional[Path] = None, 
                   capture_output: bool = True, cwd: Optional[str] = None) -> Tuple[int, str, str]:
        """Run a shell command and return the result.
        
        Args:
            cmd: Command to run as list of strings
            log_file: Optional file to write output to
            capture_output: Whether to capture stdout/stderr
            cwd: Optional working directory to run command in
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if capture_output:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
            if log_file:
                log_file.write_text(result.stdout + result.stderr)
            return result.returncode, result.stdout, result.stderr
        else:
            if log_file:
                with open(log_file, 'w') as f:
                    result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, text=True, cwd=cwd)
            else:
                result = subprocess.run(cmd, text=True, cwd=cwd)
            return result.returncode, "", ""
    
    def find_test_files(self) -> List[Path]:
        """Find all test files matching the search pattern.
        
        The search_pattern can be:
        - A file pattern: "*.s", "saxpy*", "test.bin"
        - A directory pattern: "unit/", "program/"
        - A combination: "unit/*.s", "program/saxpy*"
        
        Returns:
            List of paths to test files
        """
        test_root = Path(self.test_root)
        if not test_root.exists():
            print(f"{Colors.RED}Error:{Colors.NC} Test root directory '{test_root}' does not exist")
            return []
        
        pattern = self.search_pattern
        
        # Check if pattern starts with a directory (no wildcards in first part before /)
        if '/' in pattern:
            # Pattern includes a directory specification
            parts = pattern.split('/', 1)
            directory = parts[0]
            file_pattern = parts[1] if len(parts) > 1 and parts[1] else '*'
            
            # Build the full search path
            search_root = test_root / directory
            if not search_root.exists():
                print(f"{Colors.RED}Error:{Colors.NC} Directory '{directory}' not found in test root")
                return []
            
            # Search within the specified directory
            files = sorted([f for f in search_root.rglob(file_pattern) if f.is_file()])
        else:
            # No directory specified, search from test root
            files = sorted([f for f in test_root.rglob(pattern) if f.is_file()])
        
        if not files:
            print(f"{Colors.RED}Error:{Colors.NC} No files found matching '{self.search_pattern}'")
        
        return files
    
    def run_assembler(self, asm_file: Path) -> Tuple[bool, Optional[str]]:
        """Run the assembler on a source file.
        
        Args:
            asm_file: Path to assembly file
            
        Returns:
            Tuple of (success, error_message)
        """
        raw_output = Path(self.settings.files.raw_asm_output)
        temp_log = Path(self.settings.files.temp_cmd_log)
        
        cmd = [
            'python3',
            self.settings.paths.assembler_script,
            str(asm_file),
            str(raw_output),
            'hex',
            self.settings.paths.opcodes
        ]
        
        returncode, _, _ = self.run_command(cmd, temp_log)
        
        if returncode != 0:
            return False, temp_log.read_text()
        
        return True, None
    
    def format_instructions(self) -> None:
        """Format raw assembler output with addresses."""
        raw_output = Path(self.settings.files.raw_asm_output)
        formatted_output = Path(self.settings.files.formatted_instr)
        
        with open(raw_output, 'r') as f_in, open(formatted_output, 'w') as f_out:
            for i, line in enumerate(f_in):
                line = line.strip()
                if line:
                    f_out.write(f"0x{i*4:08x} 0x{line}\n")
    
    def extract_thread_count_from_path(self, file_path: Path) -> Optional[int]:
        """Extract thread count from new directory structure.
        
        New structure: <test_name>/t<num_threads>/<test_name>.bin
        Example: pixel/t1024/pixel.bin -> returns 1024
        
        Args:
            file_path: Path to test file
            
        Returns:
            Thread count if found in path, None otherwise
        """
        # Check parent directory name for pattern t<digits>
        parent_name = file_path.parent.name
        if parent_name.startswith('t') and parent_name[1:].isdigit():
            return int(parent_name[1:])
        return None
    
    def find_expected_file_for_binary(self, bin_file: Path, threads: int = None, blocks: int = None) -> Optional[Path]:
        """Find expected output file for a binary test file.
        
        Supports two expected file naming conventions:
        
        1. New structure (program tests):
           Binary: tests/bin/program/<test_name>/t<threads>/<test_name>.bin
           Expected: tests/exp/program/<test_name>/t<threads>/<test_name>.hex
        
        2. Old structure (unit tests):
           Binary: tests/bin/unit/.../<test_name>.bin
           Expected: tests/exp/unit/.../<test_name>_exp_t<threads>_b<blocks>.hex
        
        Args:
            bin_file: Path to binary file
            threads: Number of threads (extracted from path if not provided)
            blocks: Number of blocks
            
        Returns:
            Path to expected file if found, None otherwise
        """
        base_name = bin_file.stem
        expected_dir = Path(self.settings.directories.expected_dir)
        
        # Extract thread count from path if not provided
        if threads is None:
            extracted = self.extract_thread_count_from_path(bin_file)
            if extracted:
                threads = extracted
            else:
                threads = self.settings.test_parameters.default_threads
        
        if blocks is None:
            blocks = self.settings.test_parameters.default_blocks
        
        # Try new structure first: program/<test_name>/t<threads>/<test_name>.hex
        # For new structure, the path is: bin/program/<test_name>/t<threads>/<test_name>.bin
        # So parent.parent.name would be the test_name
        if "program" in str(bin_file) and bin_file.parent.name.startswith('t'):
            test_name = bin_file.parent.parent.name
            new_structure_file = expected_dir / "program" / test_name / f"t{threads}" / f"{base_name}.hex"
            if new_structure_file.exists():
                return new_structure_file
        
        # Fall back to old structure: <test_name>_exp_t<threads>_b<blocks>.hex
        old_structure_filename = f"{base_name}_exp_t{threads}_b{blocks}.hex"
        for match in expected_dir.rglob(old_structure_filename):
            return match
        
        return None
    
    def extract_thread_count_from_expected_file(self, expected_file: Path) -> Optional[int]:
        """Extract thread count from expected file path.
        
        Handles both new and old expected file structures:
        - New: tests/exp/program/<test_name>/t<threads>/<test_name>.hex
        - Old: <test_name>_exp_t<threads>_b<blocks>.hex
        
        Args:
            expected_file: Path to expected file
            
        Returns:
            Thread count if found, None otherwise
        """
        # Try new structure first: parent directory name should be t<threads>
        parent_name = expected_file.parent.name
        if parent_name.startswith('t') and parent_name[1:].isdigit():
            return int(parent_name[1:])
        
        # Try old structure: filename format _exp_t<threads>_b<blocks>
        filename = expected_file.name
        if '_exp_t' in filename:
            # Extract threads from pattern: _exp_t<threads>_b
            try:
                parts = filename.split('_exp_t')
                if len(parts) > 1:
                    thread_part = parts[1].split('_b')[0]
                    if thread_part.isdigit():
                        return int(thread_part)
            except (IndexError, ValueError):
                pass
        
        return None
    
    def extract_mmio_thread_count(self, meminit_file: Path) -> Optional[int]:
        """Extract thread count from MMIO in meminit file.
        
        MMIO register at address 0x18 (line 6 in hex format) contains total threads.
        Format: line number corresponds to address (each line = 4 bytes)
        
        Args:
            meminit_file: Path to meminit hex file
            
        Returns:
            Total threads from MMIO 0x18, or None if not found
        """
        if not meminit_file.exists():
            return None
        
        try:
            lines = meminit_file.read_text().strip().split('\n')
            # MMIO 0x18 is at address 0x18 = 24 bytes
            # Each line = 4 bytes (one 32-bit value)
            # Line 0 = addr 0x00, Line 1 = addr 0x04, ..., Line 6 = addr 0x18
            if len(lines) > 6:
                # Parse the value at address 0x18 (7th line, index 6)
                mmio_line = lines[6].split()
                if len(mmio_line) >= 2:
                    # Value is in hex format (0xXXXXXXXX)
                    total_threads = int(mmio_line[1], 16) if mmio_line[1].startswith('0x') else int(mmio_line[1], 16)
                    return total_threads
        except (IndexError, ValueError) as e:
            self.debug_logger.write(f"Warning: Failed to extract MMIO thread count: {e}")
        
        return None
    
    def validate_thread_count_consistency(self, bin_file: Path, expected_file: Optional[Path] = None, meminit_file: Optional[Path] = None) -> Tuple[bool, str]:
        """Validate thread count consistency across directory structure, MMIO, and expected file.
        
        Checks that the thread count from the directory structure matches:
        1. The thread count in the expected file (if provided)
        2. The thread count in MMIO (if provided and TBS enabled)
        
        Args:
            bin_file: Path to binary test file
            expected_file: Optional path to expected output file
            meminit_file: Optional path to meminit file (for MMIO extraction)
            
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if all thread counts match, False otherwise
            - error_message: Description of any mismatches
        """
        # Extract thread count from directory structure
        dir_threads = self.extract_thread_count_from_path(bin_file)
        if dir_threads is None:
            # No thread count in directory structure, validation not applicable
            return True, ""
        
        errors = []
        
        # Check expected file thread count
        if expected_file and expected_file.exists():
            exp_threads = self.extract_thread_count_from_expected_file(expected_file)
            if exp_threads is not None and exp_threads != dir_threads:
                errors.append(
                    f"Thread count mismatch: directory path has {dir_threads} threads but "
                    f"expected file '{expected_file.name}' has {exp_threads} threads"
                )
        
        # Check MMIO thread count (if TBS enabled and meminit provided)
        if self.settings.sm.enable_tbs and meminit_file:
            mmio_threads = self.extract_mmio_thread_count(meminit_file)
            if mmio_threads is not None and mmio_threads != dir_threads:
                errors.append(
                    f"Thread count mismatch: directory path has {dir_threads} threads but "
                    f"MMIO register (0x18) in meminit has {mmio_threads} threads"
                )
        
        if errors:
            error_msg = " | ".join(errors)
            return False, error_msg
        
        return True, ""

        """Create memory initialization file.
        
        This file combines instruction code with optional data and MMIO configuration.
        
        Structure:
            - Lines 0x00-0x20: MMIO registers (when TBS enabled)
                0x0C: Kernel entry point
                0x10: Threads per block
                0x14: Number of blocks
                0x18: Total threads
                0x1C: Kernel arguments address
                0x20: Kernel argument size
            - Lines 0x24+: Instruction code
            - Additional lines: Data section (from *_data.hex if present)
        
        Args:
            base_name: Base name of the test file
            dir_name: Directory containing the test file
        """
        formatted_instr = Path(self.settings.files.formatted_instr)
        meminit = Path(self.settings.files.meminit)
        
        # Start with instructions
        with open(meminit, 'w') as f_out:
            with open(formatted_instr, 'r') as f_in:
                f_out.write(f_in.read())
        
        # Look for data file
        data_file = dir_name / f"{base_name}_data.hex"
        if data_file.exists():
            with open(meminit, 'a') as f_out:
                with open(data_file, 'r') as f_in:
                    f_out.write(f_in.read())
    
    def convert_hex_to_bin(self) -> None:
        """Convert hex memory init to binary format."""
        cmd = [
            'python3',
            self.settings.paths.hex_bin_converter,
            'h2b',
            self.settings.files.meminit,
            self.settings.files.meminit_bin
        ]
        self.run_command(cmd)
    
    def convert_bin_to_hex(self, bin_file: Path, hex_output: Path) -> None:
        """Convert binary file to hex format.
        
        Args:
            bin_file: Input binary file
            hex_output: Output hex file
        """
        cmd = [
            'python3',
            self.settings.paths.hex_bin_converter,
            'b2h',
            str(bin_file),
            str(hex_output)
        ]
        self.run_command(cmd)
    
    def run_emulator(self, input_file: str, threads: int, blocks: int) -> bool:
        """Run the emulator.
        
        Args:
            input_file: Input memory file
            threads: Number of threads
            blocks: Number of blocks
            
        Returns:
            True if successful
        """
        temp_log = Path(self.settings.files.temp_cmd_log)
        
        # Resolve emulator script path
        emulator_script = Path(self.settings.paths.emulator)
        emulator_dir = emulator_script.parent
        
        cmd = [
            'python3',
            emulator_script.name,
            '-t', str(threads),
            '-b', str(blocks),
            '--start-pc', str(self.settings.test_parameters.default_start_pc),
            '--mem-format', self.settings.test_parameters.format,
            input_file
        ]
        
        # Run emulator from its own directory so imports work
        returncode, one, two = self.run_command(cmd, temp_log, cwd=str(emulator_dir))
        
        # Move memsim.hex from emulator directory to memgolden.hex
        emu_memsim = Path(self.settings.files.emu_temp_output)
        memgolden = Path(self.settings.files.emu_output)
        if emu_memsim.exists():
            emu_memsim.rename(memgolden)
        
        return returncode == 0
    
    def _capture_stdout_to_file(self, test_name: str) -> Tuple[Path, any]:
        """Create a debug log file for test stdout capture.
        
        Args:
            test_name: Name of the test for the log filename
            
        Returns:
            Tuple of (log_file_path, original_stdout)
        """
        debug_dir = Path("results/debug")
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a log file with the test name
        log_file = debug_dir / f"{test_name}_debug.log"
        
        return log_file, sys.stdout
    
    def run_simulator(self, input_file: str, test_name: Optional[str] = None) -> bool:
        """Run the simulator using SM class.
        
        Supports both TBS-enabled and TBS-disabled modes:
        
        When enable_tbs = false (default):
            - Uses kernel parameters from config.toml (sm.tb_size, memory.start_pc)
            - Simple single-block execution model
        
        When enable_tbs = true:
            - Reads kernel parameters from MMIO memory-mapped I/O in meminit file
            - Addresses: 0x0C (entry point), 0x10 (threads_per_block), 0x14 (num_blocks), 
              0x18 (total_threads), 0x1C (args_address), 0x20 (args_size)
            - Falls back to config.toml MMIO defaults if values not found in meminit
            - Enables dynamic thread block scheduling
        
        Args:
            input_file: Input binary file (meminit.bin format)
            test_name: Optional test name for perf data (e.g., "beq.bin")
            
        Returns:
            True if successful
        """
        try:
            # Create a copy of settings and customize perf_counter output settings for this test
            if test_name is None:
                test_file_path = Path(input_file)
                test_name = f"{test_file_path.stem}.{test_file_path.suffix.lstrip('.')}"
            
            # Set up debug logging
            debug_file, original_stdout = self._capture_stdout_to_file(test_name)
            debug_file_handle = open(debug_file, 'w')
            
            # Redirect stdout to capture print statements
            sys.stdout = debug_file_handle
            
            try:
                # Make a mutable copy of settings for this run
                import copy
                settings = copy.deepcopy(self.settings)
                # Set output_dir to test-specific subdirectory
                settings.perf_counter.output_dir = f"results/perf_data/{test_name}"
                # Set output_prefix to include test name in the filename
                settings.perf_counter.output_prefix = test_name
                
                # Create SM instance with simulator config
                sm = SM(
                    test_file=Path(input_file),
                    test_file_type="bin",
                    config=settings
                )
                
                # Run simulation - sm.pipeline is a dict with all stages
                # Need to tick through until completion
                cycle = 0
                max_cycles = self.max_cycles if self.enable_cycle_limit else float('inf')
                
                while cycle < max_cycles:
                    # Check if scheduler indicates completion
                    if hasattr(sm.pipeline.get('scheduler'), 'system_finished'):
                        if sm.pipeline['scheduler'].system_finished:
                            break
                    
                    # Tick all pipeline stages
                    sm.tick()
                    
                    cycle += 1
                
                if self.enable_cycle_limit and cycle >= self.max_cycles:
                    print(f"Warning: Simulation hit max cycle limit of {self.max_cycles}")
                
                # Finalize performance counter collection
                sm.finalize()
                
                # Dump register file to output
                sm.pipeline["mem"].dump(path=str(self.settings.files.sim_output))
                
                return True
            finally:
                # Always restore stdout and close the debug file
                sys.stdout = original_stdout
                debug_file_handle.close()
                print(f"Debug output written to {debug_file}")
                
        except Exception as e:
            # Make sure to restore stdout before printing error
            if 'original_stdout' in locals():
                sys.stdout = original_stdout
            if 'debug_file_handle' in locals():
                debug_file_handle.close()
                
            print(f"{Colors.RED}Simulator error:{Colors.NC} {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def prepare_expected_file_with_instructions(self, expected_file: Path, meminit_file: Path, output_file: Path) -> None:
        """Prepare expected file by prepending instructions (meminit) to it.
        
        The expected files only contain register state changes, not instructions.
        This method combines the meminit (instructions) with the expected output
        for proper comparison with the simulator's full output.
        
        Args:
            expected_file: Path to original expected file (register changes only)
            meminit_file: Path to meminit file (instructions)
            output_file: Path to write combined file
        """
        # Read both files
        meminit_content = meminit_file.read_text() if meminit_file.exists() else ""
        expected_content = expected_file.read_text() if expected_file.exists() else ""
        
        # Combine: instructions first, then expected register changes
        combined_content = meminit_content + expected_content
        
        # Write combined file
        output_file.write_text(combined_content)
    
    def compare_outputs(self, expected_file: Path, actual_file: Path, error_log: Path) -> bool:
        """Compare expected and actual output files.
        
        Args:
            expected_file: Expected output file
            actual_file: Actual output file
            error_log: Error log file
            
        Returns:
            True if files match
        """
        cmd = [
            'diff', '-u', '-w', '-i',
            str(expected_file),
            str(actual_file)
        ]
        
        returncode, stdout, _ = self.run_command(cmd)
        
        if returncode != 0:
            error_log.write_text(stdout)
        
        return returncode == 0
    
    def test_assembly_mode(self, asm_file: Path) -> TestResult:
        """Test a single assembly file.
        
        Args:
            asm_file: Path to assembly file
            
        Returns:
            TestResult object
        """
        base_name = asm_file.stem
        dir_name = asm_file.parent
        
        # Run assembler
        success, error = self.run_assembler(asm_file)
        if not success:
            error_log = self.diff_dir / f"{base_name}_asm_error.log"
            error_log.write_text(error or "Unknown error")
            return TestResult(base_name, False, 0, 0, str(error_log))
        
        # Format instructions and create meminit
        self.format_instructions()
        self.create_meminit(base_name, dir_name)
        self.convert_hex_to_bin()
        
        # Get thread/block counts
        threads = self.settings.test_parameters.default_threads
        blocks = self.settings.test_parameters.default_blocks
        
        # Run emulator
        self.run_emulator(self.settings.files.meminit, threads, blocks)
        
        # Run simulator (pass test name for perf_data directory)
        test_name = f"{base_name}.s"
        self.run_simulator(self.settings.files.meminit_bin, test_name=test_name)
        
        # Compare outputs
        test_id = f"{base_name}_t{threads}_b{blocks}"
        error_log = self.diff_dir / f"{test_id}_error.log"
        
        emu_output = Path(self.settings.files.emu_output)
        sim_output = Path(self.settings.files.sim_output)
        
        if self.compare_outputs(emu_output, sim_output, error_log):
            # Test passed
            if not self.skip_cleanup:
                # Clean up
                if error_log.exists():
                    error_log.unlink()
            else:
                # Save artifacts for inspection
                (self.diff_dir / f"{test_id}_exp.hex").write_text(emu_output.read_text())
                (self.diff_dir / f"{test_id}_sim.hex").write_text(sim_output.read_text())
                meminit = Path(self.settings.files.meminit)
                if meminit.exists():
                    (self.diff_dir / f"{test_id}_meminit.hex").write_text(meminit.read_text())
            return TestResult(base_name, True, threads, blocks)
        else:
            # Test failed - save artifacts
            (self.diff_dir / f"{test_id}_exp.hex").write_text(emu_output.read_text())
            (self.diff_dir / f"{test_id}_sim.hex").write_text(sim_output.read_text())
            meminit = Path(self.settings.files.meminit)
            if meminit.exists():
                (self.diff_dir / f"{test_id}_meminit.hex").write_text(meminit.read_text())
            return TestResult(base_name, False, threads, blocks, str(error_log))
    
    def test_binary_mode(self, bin_file: Path) -> TestResult:
        """Test a single binary file against emulator output.
        
        Supports new directory structure with thread counts:
        - New: tests/bin/program/<test_name>/t<threads>/<test_name>.bin
        - Old: tests/bin/unit/.../<test_name>.bin
        
        Args:
            bin_file: Path to binary file
            
        Returns:
            TestResult object
        """
        base_name = bin_file.stem
        results_dir = Path(self.settings.directories.diff_dir)
        hex_output = results_dir / f"{base_name}_meminit.hex"
        bin_output = results_dir / f"{base_name}_sim.bin"
        
        # Convert binary to hex for emulator
        self.convert_bin_to_hex(bin_file, hex_output)
        
        # Extract thread/block counts (from directory structure if available)
        extracted_threads = self.extract_thread_count_from_path(bin_file)
        threads = extracted_threads if extracted_threads else self.settings.test_parameters.default_threads
        blocks = self.settings.test_parameters.default_blocks
        
        # Run emulator
        self.run_emulator(str(hex_output), threads, blocks)
        
        # Convert hex back to binary for simulator (using the same format as mode 1)
        cmd = [
            'python3',
            self.settings.paths.hex_bin_converter,
            'h2b',
            str(hex_output),
            str(bin_output)
        ]
        self.run_command(cmd)
        
        # Run simulator (pass original test file name for perf_data directory)
        test_name = f"{bin_file.stem}.{bin_file.suffix.lstrip('.')}"
        self.run_simulator(str(bin_output), test_name=test_name)
        
        # Compare outputs
        test_id = f"{base_name}_t{threads}_b{blocks}"
        error_log = self.diff_dir / f"{test_id}_error.log"
        
        emu_output = Path(self.settings.files.emu_output)
        sim_output = Path(self.settings.files.sim_output)
        
        if self.compare_outputs(emu_output, sim_output, error_log):
            # Test passed
            if not self.skip_cleanup:
                # Clean up
                if error_log.exists():
                    error_log.unlink()
                if hex_output.exists():
                    hex_output.unlink()
                if bin_output.exists():
                    bin_output.unlink()
            else:
                # Save artifacts for inspection
                (self.diff_dir / f"{test_id}_exp.hex").write_text(emu_output.read_text())
                (self.diff_dir / f"{test_id}_sim.hex").write_text(sim_output.read_text())
                if hex_output.exists():
                    (self.diff_dir / f"{test_id}_meminit.hex").write_text(hex_output.read_text())
            return TestResult(base_name, True, threads, blocks)
        else:
            # Test failed - save artifacts
            (self.diff_dir / f"{test_id}_exp.hex").write_text(emu_output.read_text())
            (self.diff_dir / f"{test_id}_sim.hex").write_text(sim_output.read_text())
            if hex_output.exists():
                (self.diff_dir / f"{test_id}_meminit.hex").write_text(hex_output.read_text())
                hex_output.unlink()
            if bin_output.exists():
                bin_output.unlink()
            return TestResult(base_name, False, threads, blocks, str(error_log))
    
    def test_binary_with_expected(self, bin_file: Path) -> TestResult:
        """Test a binary file against pre-generated expected output.
        
        Supports both old and new expected file structures:
        - New: tests/exp/program/<test_name>/t<threads>/<test_name>.hex
        - Old: tests/exp/unit/.../<test_name>_exp_t<threads>_b<blocks>.hex
        
        Args:
            bin_file: Path to binary file
            
        Returns:
            TestResult object
        """
        base_name = bin_file.stem
        
        # Extract thread count from directory structure if available
        extracted_threads = self.extract_thread_count_from_path(bin_file)
        threads = extracted_threads if extracted_threads else self.settings.test_parameters.default_threads
        blocks = self.settings.test_parameters.default_blocks
        
        # Convert binary to hex for memory initialization
        hex_output = Path(f"{base_name}_meminit.hex")
        self.convert_bin_to_hex(bin_file, hex_output)
        
        # Run simulator (pass test name for perf_data directory)
        test_name = f"{bin_file.stem}.{bin_file.suffix.lstrip('.')}"
        self.run_simulator(str(bin_file), test_name=test_name)
        
        # Find expected file using new unified method
        expected_file = self.find_expected_file_for_binary(bin_file, threads, blocks)
        
        if expected_file is None:
            old_format_name = f"{base_name}_exp_t{threads}_b{blocks}.hex"
            print(f"{Colors.YELLOW}[SKIP]{Colors.NC}     {base_name} (Missing expected file: {old_format_name})")
            return TestResult(base_name, True, threads, blocks)  # Skip doesn't count as fail
        
        # Validate thread count consistency
        meminit_file = Path(f"{base_name}_meminit.hex") if hex_output.exists() else None
        is_valid, error_msg = self.validate_thread_count_consistency(bin_file, expected_file, meminit_file)
        
        if not is_valid:
            # Thread count mismatch - log error and fail test
            error_log = self.diff_dir / f"{base_name}_t{threads}_b{blocks}_validation.log"
            error_log.write_text(f"THREAD COUNT VALIDATION ERROR:\n{error_msg}\n")
            self.debug_logger.write(f"{Colors.RED}[ERROR]{Colors.NC} {base_name}: {error_msg}")
            print(f"{Colors.RED}[FAIL]{Colors.NC}     {base_name} (Thread count validation failed)")
            return TestResult(base_name, False, threads, blocks, str(error_log))
        
        # Compare outputs
        test_id = f"{base_name}_t{threads}_b{blocks}"
        error_log = self.diff_dir / f"{test_id}_error.log"
        
        sim_output = Path(self.settings.files.sim_output)
        
        # Prepare expected file with instructions prepended
        expected_with_instr = self.diff_dir / f"{test_id}_exp_full.hex"
        self.prepare_expected_file_with_instructions(expected_file, hex_output, expected_with_instr)
        
        if self.compare_outputs(expected_with_instr, sim_output, error_log):
            # Test passed
            if not self.skip_cleanup:
                # Clean up all artifacts
                if error_log.exists():
                    error_log.unlink()
                if hex_output.exists():
                    hex_output.unlink()
                if expected_with_instr.exists():
                    expected_with_instr.unlink()
            else:
                # Save artifacts for inspection
                (self.diff_dir / f"{test_id}_exp.hex").write_text(expected_with_instr.read_text())
                (self.diff_dir / f"{test_id}_sim.hex").write_text(sim_output.read_text())
                if hex_output.exists():
                    (self.diff_dir / f"{test_id}_meminit.hex").write_text(hex_output.read_text())
            return TestResult(base_name, True, threads, blocks)
        else:
            # Test failed - save artifacts for debugging
            (self.diff_dir / f"{test_id}_exp.hex").write_text(expected_with_instr.read_text())
            (self.diff_dir / f"{test_id}_sim.hex").write_text(sim_output.read_text())
            if hex_output.exists():
                (self.diff_dir / f"{test_id}_meminit.hex").write_text(hex_output.read_text())
                hex_output.unlink()
            return TestResult(base_name, False, threads, blocks, str(error_log))
    
    def test_assembly_with_expected(self, asm_file: Path) -> TestResult:
        """Test an assembly file against pre-generated expected output.
        
        Args:
            asm_file: Path to assembly file
            
        Returns:
            TestResult object
        """
        base_name = asm_file.stem
        dir_name = asm_file.parent
        
        # Run assembler
        success, error = self.run_assembler(asm_file)
        if not success:
            error_log = self.diff_dir / f"{base_name}_asm_error.log"
            error_log.write_text(error or "Unknown error")
            return TestResult(base_name, False, 0, 0, str(error_log))
        
        # Format instructions and create meminit
        self.format_instructions()
        self.create_meminit(base_name, dir_name)
        self.convert_hex_to_bin()
        
        # Get thread/block counts
        threads = self.settings.test_parameters.default_threads
        blocks = self.settings.test_parameters.default_blocks
        
        # Run simulator (pass test name for perf_data directory)
        test_name = f"{base_name}.s"
        self.run_simulator(self.settings.files.meminit_bin, test_name=test_name)
        
        # Locate expected file (recursive search)
        expected_dir = Path(self.settings.directories.expected_dir)
        expected_filename = f"{base_name}_exp_t{threads}_b{blocks}.hex"
        
        # Search recursively for the file
        expected_file = None
        for match in expected_dir.rglob(expected_filename):
            expected_file = match
            break
        
        if expected_file is None:
            print(f"{Colors.YELLOW}[SKIP]{Colors.NC}     {base_name} (Missing expected file: {expected_filename})")
            return TestResult(base_name, True, threads, blocks)  # Skip doesn't count as fail
        
        # Compare outputs
        test_id = f"{base_name}_t{threads}_b{blocks}"
        error_log = self.diff_dir / f"{test_id}_error.log"
        
        sim_output = Path(self.settings.files.sim_output)
        meminit = Path(self.settings.files.meminit)
        
        # Prepare expected file with instructions prepended
        expected_with_instr = self.diff_dir / f"{test_id}_exp_full.hex"
        self.prepare_expected_file_with_instructions(expected_file, meminit, expected_with_instr)
        
        if self.compare_outputs(expected_with_instr, sim_output, error_log):
            # Test passed
            if not self.skip_cleanup:
                # Clean up all artifacts
                if error_log.exists():
                    error_log.unlink()
                if expected_with_instr.exists():
                    expected_with_instr.unlink()
            else:
                # Save artifacts for inspection
                (self.diff_dir / f"{test_id}_exp.hex").write_text(expected_with_instr.read_text())
                (self.diff_dir / f"{test_id}_sim.hex").write_text(sim_output.read_text())
                if meminit.exists():
                    (self.diff_dir / f"{test_id}_meminit.hex").write_text(meminit.read_text())
            return TestResult(base_name, True, threads, blocks)
        else:
            # Test failed - save artifacts for debugging
            (self.diff_dir / f"{test_id}_exp.hex").write_text(expected_with_instr.read_text())
            (self.diff_dir / f"{test_id}_sim.hex").write_text(sim_output.read_text())
            if meminit.exists():
                (self.diff_dir / f"{test_id}_meminit.hex").write_text(meminit.read_text())
            return TestResult(base_name, False, threads, blocks, str(error_log))
    
    def _clean_results(self) -> None:
        """Clean the results/ directory completely."""
        results_dir = Path(self.settings.directories.diff_dir).parent
        if results_dir.exists():
            import shutil
            print(f"Cleaning {results_dir}...")
            shutil.rmtree(results_dir)
            results_dir.mkdir(parents=True, exist_ok=True)
            print(f"Cleaned {results_dir}")
    
    def cleanup(self) -> None:
        """Clean up intermediate files."""
        files_to_remove = [
            self.settings.files.raw_asm_output,
            self.settings.files.emu_output,
            self.settings.files.sim_output,
            self.settings.files.formatted_instr,
            self.settings.files.final_expected,
            self.settings.files.temp_cmd_log,
            self.settings.files.meminit,
            self.settings.files.meminit_bin,
        ]
        
        for file in files_to_remove:
            path = Path(file)
            if path.exists():
                path.unlink()
        
        # Only keep error artifacts in diff_dir; remove passed test artifacts
        # Keep: *_error.log, *_exp.hex, *_sim.hex, *_meminit.hex (for failed tests)
        # Remove: all other intermediate files
        if self.pass_count > 0:
            # If we had passing tests, clean up their artifacts from diff_dir
            # (We keep artifacts for failed tests for debugging)
            for file in self.diff_dir.glob('*'):
                # Only remove intermediate temp files, keep error artifacts
                if file.name.endswith('_exp_full.hex'):
                    file.unlink()
    
    def run(self) -> int:
        """Run all tests.
        
        Returns:
            Exit code (0 for success, 1 for failure)
        """
        print("=" * 40)
        print("      Starting GPU System Tests")
        print(f"      Source:  {self.src}")
        print(f"      Truth:   {self.truth}")
        print(f"      Root:    {self.test_root}")
        print(f"      Pattern: {self.search_pattern}")
        print("=" * 40)
        
        # Find test files
        test_files = self.find_test_files()
        if not test_files:
            return 1
        
        # Run tests based on src/truth combination
        for test_file in test_files:
            if self.src == "assembly" and self.truth == "emu":
                result = self.test_assembly_mode(test_file)
            elif self.src == "bin" and self.truth == "emu":
                result = self.test_binary_mode(test_file)
            elif self.src == "bin" and self.truth == "exp":
                result = self.test_binary_with_expected(test_file)
            elif self.src == "assembly" and self.truth == "exp":
                result = self.test_assembly_with_expected(test_file)
            else:
                print(f"{Colors.RED}Error:{Colors.NC} Invalid src/truth combination: {self.src}/{self.truth}")
                return 1
            
            # Print result
            if result.passed:
                print(f"{Colors.GREEN}[PASS]{Colors.NC}     {result.name} (t={result.threads}, b={result.blocks})")
                self.pass_count += 1
            else:
                print(f"{Colors.RED}[FAIL]{Colors.NC}     {result.name} (t={result.threads}, b={result.blocks})")
                self.fail_count += 1
        
        # Cleanup
        if not self.skip_cleanup:
            self.cleanup()
        
        # Close debug logger
        self.debug_logger.close()
        
        # Print summary
        print("=" * 40)
        print("Summary")
        print(f"Passed:  {Colors.GREEN}{self.pass_count}{Colors.NC}")
        print(f"Failed:  {Colors.RED}{self.fail_count}{Colors.NC}")
        
        if self.fail_count > 0:
            print(f"Check '{self.diff_dir}/' for logs and generated assembly.")
            return 1
        
        return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='GPU System Test Automation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--src', choices=['assembly', 'bin'], required=False,
        help='Source file type: assembly (.s files) or bin (.bin files)'
    )
    parser.add_argument(
        '--truth', choices=['emu', 'exp'], required=False,
        help='Ground truth source: emu (emulator) or exp (expected files)'
    )
    parser.add_argument(
        'pattern', nargs='?', default=None,
        help='Optional search pattern for test files (e.g., "*.s", "saxpy*", "unit/", "program/*.bin")'
    )
    parser.add_argument(
        '--config', type=Path, default=None,
        help='Path to config file (default: config.toml)'
    )
    parser.add_argument(
        '--clean', action='store_true',
        help='Clean results/ directory before running tests'
    )
    parser.add_argument(
        '--skip-cleanup', action='store_true',
        help='Skip cleanup after tests run (keep all output files for inspection)'
    )
    parser.add_argument(
        '--enable-cycle-limit', action='store_true',
        help='Enable maximum cycle limit for simulator (default: no limit)'
    )
    parser.add_argument(
        '--max-cycles', type=int, default=100000,
        help='Maximum number of cycles to simulate (only used with --enable-cycle-limit, default: 100000)'
    )
    parser.add_argument(
        '--debug-file', type=str, default=None,
        help='Write debug output to results/debug/<debug_file_name> (or to both terminal and file if --debug-dual-output is set)'
    )
    parser.add_argument(
        '--debug-dual-output', action='store_true',
        help='Write debug output to both terminal and debug file (use with --debug-file)'
    )
    
    args = parser.parse_args()
    
    # If --clean is specified alone, just clean and exit
    if args.clean and args.src is None and args.truth is None:
        try:
            runner = GPUTestRunner(None, None, None, args.config, args.clean, args.skip_cleanup, args.enable_cycle_limit, args.max_cycles, args.debug_file, args.debug_dual_output)
            runner._clean_results()
            print(f"{Colors.GREEN}Results directory cleaned.{Colors.NC}")
            return 0
        except Exception as e:
            print(f"{Colors.RED}Error:{Colors.NC} {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1
    
    # Otherwise, require --src and --truth
    if args.src is None or args.truth is None:
        parser.error("--src and --truth are required (unless using --clean alone)")
    
    try:
        runner = GPUTestRunner(args.src, args.truth, args.pattern, args.config, args.clean, args.skip_cleanup, args.enable_cycle_limit, args.max_cycles, args.debug_file, args.debug_dual_output)
        sys.exit(runner.run())
    except Exception as e:
        print(f"{Colors.RED}Error:{Colors.NC} {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
