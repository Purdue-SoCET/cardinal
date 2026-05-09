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
import csv
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass
import io
import toml
from contextlib import redirect_stdout, redirect_stderr

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import get_settings, ProgramConfig

# Import SM class from simulator
from simulator.sm import SM

import builtins

# This turns off ALL print statements in the whole codebase
# builtins.print = lambda *args, **kwargs: None

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


class SimulatorOutputCapture:
    """Captures simulator stdout/stderr with optional dual output to terminal and file."""
    
    def __init__(self, output_file: Optional[Path] = None, dual_output: bool = False):
        """Initialize simulator output capture.
        
        Args:
            output_file: Optional file to write simulator output to
            dual_output: If True, also print to terminal (in addition to file)
        """
        self.output_file = output_file
        self.dual_output = dual_output
        self.file_handle = None
        self.original_stdout = None
        self.original_stderr = None
        
        if self.output_file:
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            self.file_handle = open(self.output_file, 'w')
    
    def start_capture(self):
        """Start capturing stdout/stderr."""
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        
        if self.dual_output and self.output_file:
            # Create a tee-like wrapper that writes to both file and original stdout
            sys.stdout = self._TeeOutput(self.file_handle, self.original_stdout)
            sys.stderr = self._TeeOutput(self.file_handle, self.original_stderr)
        elif self.output_file:
            # File only
            sys.stdout = self.file_handle
            sys.stderr = self.file_handle
        # else: no capture, keep original stdout/stderr
    
    def stop_capture(self):
        """Stop capturing and restore original stdout/stderr."""
        if self.original_stdout:
            sys.stdout = self.original_stdout
            self.original_stdout = None
        if self.original_stderr:
            sys.stderr = self.original_stderr
            self.original_stderr = None
        
        if self.file_handle and not self.file_handle.closed:
            self.file_handle.flush()
    
    def close(self):
        """Close the output file."""
        self.stop_capture()
        if self.file_handle and not self.file_handle.closed:
            self.file_handle.close()
        self.file_handle = None
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()
    
    class _TeeOutput:
        """Helper class that writes to both file and terminal."""
        def __init__(self, file_handle, terminal):
            self.file = file_handle
            self.terminal = terminal
        
        def write(self, message):
            self.file.write(message)
            self.terminal.write(message)
        
        def flush(self):
            self.file.flush()
            self.terminal.flush()
        
        def isatty(self):
            return self.terminal.isatty()


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
    
    def __init__(
        self,
        src: Optional[str] = None,
        truth: Optional[str] = None,
        search_pattern: Optional[str] = None,
        config_path: Optional[Path] = None,
        clean: bool = False,
        skip_cleanup: bool = False,
        enable_cycle_limit: bool = False,
        max_cycles: Optional[int] = None,
        debug_file: Optional[Path] = None,
        debug_dual_output: bool = False,
        enable_simulator_output: bool = False,
        simulator_output_file: Optional[str] = None,
        sweep: bool = False,
        sweep_config: Optional[Path] = None,
        sweep_inputs: Optional[List[str]] = None,
    ):
        """Initialize the test runner."""
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
        self.enable_simulator_output = enable_simulator_output
        self.simulator_output_file = simulator_output_file
        self.settings = get_settings(config_path)
        self.pass_count = 0
        self.fail_count = 0
        self.debug_dual_output = debug_dual_output

        self.sweep = sweep
        self.sweep_config = sweep_config
        self.sweep_inputs = sweep_inputs or []

        self.last_sim_cycles = 0
        self.last_sim_finished = False

        if debug_file:
            debug_path = Path("results/debug") / debug_file
        else:
            debug_path = None
        self.debug_logger = DebugLogger(debug_path, debug_dual_output)

        if self.clean:
            self._clean_results()

        if src is not None:
            if src == "assembly":
                self.test_root = self.settings.directories.test_root_asm
                file_ext = ".s"
            else:
                self.test_root = self.settings.directories.test_root_bin
                file_ext = ".bin"

            self.search_pattern = search_pattern or self.settings.test_parameters.default_pattern

            if not self.search_pattern.endswith(file_ext) and '/' not in self.search_pattern:
                if not self.search_pattern.endswith('/'):
                    self.search_pattern += file_ext

        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)

        self.diff_dir = Path(self.settings.directories.diff_dir)
        self.diff_dir.mkdir(parents=True, exist_ok=True)

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
        
    def find_test_files_for_pattern(self, pattern: str) -> List[Path]:
        """Find all test files matching a specific pattern."""
        test_root = Path(self.test_root)
        if not test_root.exists():
            print(f"{Colors.RED}Error:{Colors.NC} Test root directory '{test_root}' does not exist")
            return []

        if '/' in pattern:
            parts = pattern.split('/', 1)
            directory = parts[0]
            file_pattern = parts[1] if len(parts) > 1 and parts[1] else '*'

            search_root = test_root / directory
            if not search_root.exists():
                print(f"{Colors.RED}Error:{Colors.NC} Directory '{directory}' not found in test root")
                return []

            files = sorted([f for f in search_root.rglob(file_pattern) if f.is_file()])
        else:
            files = sorted([f for f in test_root.rglob(pattern) if f.is_file()])

        if not files:
            print(f"{Colors.RED}Error:{Colors.NC} No files found matching '{pattern}'")

        return files


    def find_test_files(self) -> List[Path]:
        """Find all test files matching the runner search pattern."""
        return self.find_test_files_for_pattern(self.search_pattern)

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
    
    def run_simulator(
        self,
        input_file: str,
        test_name: Optional[str] = None,
        config_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ) -> bool:
        """Run the simulator using SM class."""
        try:
            if test_name is None:
                test_file_path = Path(input_file)
                test_name = f"{test_file_path.stem}.{test_file_path.suffix.lstrip('.')}"

            if output_dir is not None:
                output_dir.mkdir(parents=True, exist_ok=True)

            if self.enable_simulator_output and self.simulator_output_file:
                output_file = (output_dir / self.simulator_output_file) if output_dir else (Path("results/debug") / self.simulator_output_file)
            else:
                log_dir = output_dir if output_dir else Path("results/debug")
                log_dir.mkdir(parents=True, exist_ok=True)
                output_file = log_dir / f"{test_name}_simulator.log"

            output_capture = SimulatorOutputCapture(output_file, dual_output=self.enable_simulator_output)
            output_capture.start_capture()

            try:
                import copy

                if config_path is None:
                    settings = copy.deepcopy(self.settings)
                else:
                    settings = copy.deepcopy(get_settings(config_path))

                if output_dir is not None:
                    settings.perf_counter.output_dir = str(output_dir / "perf_data")
                else:
                    settings.perf_counter.output_dir = f"results/perf_data/{test_name}"

                settings.perf_counter.output_prefix = test_name

                sm = SM(
                    test_file=Path(input_file),
                    test_file_type="bin",
                    config=settings,
                )

                cycle = 0
                max_cycles = self.max_cycles if self.enable_cycle_limit else float('inf')

                while cycle < max_cycles:
                    # Check if scheduler indicates completion
                    if sm.pipeline['tbs'].kern_finished:
                        break
                    
                    # Tick all pipeline stages
                    sm.tick()
                    cycle += 1

                if self.enable_cycle_limit and cycle >= self.max_cycles:
                    print(f"Warning: Simulation hit max cycle limit of {self.max_cycles}")

                sm.finalize()

                # Dump the dcache 3C statistics if available
                if "dcache" in sm.pipeline and hasattr(sm.pipeline["dcache"], "dump_stats"):
                    sm.pipeline["dcache"].dump_stats()

                self.last_sim_cycles = cycle
                self.last_sim_finished = sm.finished

                if output_dir is not None:
                    sim_output_path = output_dir / "memsim.hex"
                else:
                    sim_output_path = Path(self.settings.files.sim_output)

                sm.pipeline["mem"].dump(path=str(sim_output_path))
                return True
            finally:
                output_capture.stop_capture()
                output_capture.close()
                if self.enable_simulator_output:
                    print(f"Simulator output written to {output_file}")

        except Exception as e:
            self.last_sim_cycles = 0
            self.last_sim_finished = False

            if 'output_capture' in locals():
                output_capture.stop_capture()
                output_capture.close()

            print(f"{Colors.RED}Simulator error:{Colors.NC} {e}")
            import traceback
            traceback.print_exc()
            return False

    def filter_hex_by_address_range(self, hex_file: Path, start_addr: int, end_addr: int, output_file: Path) -> None:
        """Filter hex file to only include addresses within the specified range.
        
        Addresses are filtered to include only those between start_addr and end_addr (inclusive).
        If start_addr > end_addr (config error), use all addresses.
        If end_addr extends beyond the last address in the file, the actual end becomes the last address.
        
        Args:
            hex_file: Input hex file with address/value pairs
            start_addr: Start address (inclusive)
            end_addr: End address (inclusive)
            output_file: Output file with filtered addresses
        """
        lines = []
        all_lines = []
        
        try:
            # First pass: collect all lines and addresses
            with open(hex_file, 'r') as f:
                for line in f:
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    
                    parts = line_stripped.split()
                    if len(parts) < 2:
                        continue
                    
                    try:
                        addr = int(parts[0], 16)
                        all_lines.append((addr, line_stripped))
                    except ValueError:
                        # Skip malformed lines
                        continue
            
            if not all_lines:
                # No valid lines found
                output_file.write_text("")
                return
            
            # If start > end (config error), just use all lines
            if start_addr > end_addr:
                filtered_lines = all_lines
            else:
                # Get actual address range from file
                max_addr_in_file = max(a for a, _ in all_lines)
                
                # Adjust end_addr if it extends beyond the file (as per user requirement)
                # If end_addr >= max_addr in file, use max_addr as the end
                actual_end = min(end_addr, max_addr_in_file)
                
                # Filter lines that fall within the range
                filtered_lines = [
                    (addr, line) for addr, line in all_lines
                    if start_addr <= addr <= actual_end
                ]
            
            # Write filtered output
            output_file.write_text(''.join(line + "\n" for _, line in filtered_lines))
            
        except Exception as e:
            print(f"Error filtering hex file {hex_file}: {e}")
            # Write empty file on error
            output_file.write_text("")
    
    def prepare_outputs_with_address_filtering(self, 
                                              program_config: Optional['ProgramConfig'],
                                              expected_file: Path, 
                                              sim_output_file: Path,
                                              filtered_expected: Path,
                                              filtered_sim: Path) -> None:
        """Prepare output files by filtering to address range if program config is available.
        
        Args:
            program_config: Program configuration with address range, or None to skip filtering
            expected_file: Path to expected output file
            sim_output_file: Path to simulator output file
            filtered_expected: Output path for filtered expected file
            filtered_sim: Output path for filtered simulator file
        """
        if program_config:
            # Filter both files to the specified address range
            self.filter_hex_by_address_range(
                expected_file,
                program_config.diff_start_addr,
                program_config.diff_end_addr,
                filtered_expected
            )
            self.filter_hex_by_address_range(
                sim_output_file,
                program_config.diff_start_addr,
                program_config.diff_end_addr,
                filtered_sim
            )
        else:
            # No filtering, just copy files
            filtered_expected.write_text(expected_file.read_text())
            filtered_sim.write_text(sim_output_file.read_text())
    
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

    def compare_sweep_outputs(
        self,
        test_file: Path,
        sim_input: Path,
        run_dir: Path,
    ) -> Tuple[bool, Optional[bool], str]:
        """Run correctness checks for a sweep case when --truth is provided.

        Returns:
            Tuple of (checked, passed, message)
            - checked: whether a correctness check was attempted
            - passed: True/False when checked, None when no check was requested
            - message: failure/skip context
        """
        if self.truth is None:
            return False, None, ""

        sim_output = run_dir / "memsim.hex"
        if not sim_output.exists():
            return True, False, f"Simulator output missing: {sim_output}"

        extracted_threads = self.extract_thread_count_from_path(test_file)
        threads = extracted_threads if extracted_threads else self.settings.test_parameters.default_threads
        blocks = self.settings.test_parameters.default_blocks
        test_id = f"{test_file.stem}_t{threads}_b{blocks}"

        if self.truth == "emu":
            if self.src == "bin":
                emu_input = run_dir / f"{test_file.stem}_meminit.hex"
                self.convert_bin_to_hex(test_file, emu_input)
            elif self.src == "assembly":
                emu_input = Path(self.settings.files.meminit)
            else:
                return True, False, f"Unsupported src '{self.src}' for emulator comparison"

            if not self.run_emulator(str(emu_input), threads, blocks):
                return True, False, "Emulator run failed"

            emu_output = Path(self.settings.files.emu_output)
            run_emu_output = run_dir / "emugolden.hex"
            if emu_output.exists():
                run_emu_output.write_text(emu_output.read_text())

            error_log = run_dir / f"{test_id}_error.log"
            matched = self.compare_outputs(run_emu_output, sim_output, error_log)
            if matched:
                if error_log.exists():
                    error_log.unlink()
                return True, True, ""
            return True, False, f"Output mismatch: {error_log.name}"

        if self.truth == "exp":
            if self.src != "bin":
                return True, False, "Sweep exp comparison currently supports --src bin only"

            expected_file = self.find_expected_file_for_binary(test_file, threads, blocks)
            if expected_file is None:
                missing = f"{test_file.stem}_exp_t{threads}_b{blocks}.hex"
                return True, False, f"Missing expected file: {missing}"

            is_valid, error_msg = self.validate_thread_count_consistency(test_file, expected_file, None)
            if not is_valid:
                return True, False, error_msg

            program_config_path = test_file.parent / "program_config.toml"
            program_config = self.settings.read_program_config(program_config_path)

            filtered_exp_file = run_dir / f"{test_id}_exp_filtered.hex"
            filtered_sim_file = run_dir / f"{test_id}_sim_filtered.hex"
            self.prepare_outputs_with_address_filtering(
                program_config,
                expected_file,
                sim_output,
                filtered_exp_file,
                filtered_sim_file,
            )

            error_log = run_dir / f"{test_id}_error.log"
            matched = self.compare_outputs(filtered_exp_file, filtered_sim_file, error_log)
            if matched:
                if error_log.exists():
                    error_log.unlink()
                return True, True, ""
            return True, False, f"Output mismatch: {error_log.name}"

        return True, False, f"Unsupported truth mode '{self.truth}'"
    
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
        
        self.debug_logger.write(f"[TEST] Starting: {base_name} (t={threads}, b={blocks})")
        
        # Convert binary to hex for memory initialization
        self.debug_logger.write(f"[STEP] Converting binary to hex: {bin_file}")
        hex_output = Path(f"{base_name}_meminit.hex")
        self.convert_bin_to_hex(bin_file, hex_output)
        self.debug_logger.write(f"[STEP] Binary conversion complete")
        
        # Run simulator (pass test name for perf_data directory)
        self.debug_logger.write(f"[STEP] Running simulator...")
        test_name = f"{bin_file.stem}.{bin_file.suffix.lstrip('.')}"
        self.run_simulator(str(bin_file), test_name=test_name)
        self.debug_logger.write(f"[STEP] Simulator complete")
        
        # Find expected file using new unified method
        self.debug_logger.write(f"[STEP] Finding expected file...")
        expected_file = self.find_expected_file_for_binary(bin_file, threads, blocks)
        
        if expected_file is None:
            old_format_name = f"{base_name}_exp_t{threads}_b{blocks}.hex"
            self.debug_logger.write(f"[SKIP] Expected file not found: {old_format_name}")
            print(f"{Colors.YELLOW}[SKIP]{Colors.NC}     {base_name} (Missing expected file: {old_format_name})")
            return TestResult(base_name, True, threads, blocks)  # Skip doesn't count as fail
        
        self.debug_logger.write(f"[STEP] Expected file found: {expected_file}")
        
        # Validate thread count consistency
        self.debug_logger.write(f"[STEP] Validating thread count consistency...")
        meminit_file = Path(f"{base_name}_meminit.hex") if hex_output.exists() else None
        is_valid, error_msg = self.validate_thread_count_consistency(bin_file, expected_file, meminit_file)
        
        if not is_valid:
            # Thread count mismatch - log error and fail test
            self.debug_logger.write(f"[VALIDATION ERROR] {error_msg}")
            error_log = self.diff_dir / f"{base_name}_t{threads}_b{blocks}_validation.log"
            error_log.write_text(f"THREAD COUNT VALIDATION ERROR:\n{error_msg}\n")
            self.debug_logger.write(f"{Colors.RED}[ERROR]{Colors.NC} {base_name}: {error_msg}")
            print(f"{Colors.RED}[FAIL]{Colors.NC}     {base_name} (Thread count validation failed)")
            return TestResult(base_name, False, threads, blocks, str(error_log))
        
        self.debug_logger.write(f"[STEP] Thread count validation passed")
        
        # Load program configuration if available
        self.debug_logger.write(f"[STEP] Loading program configuration...")
        program_config_path = bin_file.parent / "program_config.toml"
        program_config = self.settings.read_program_config(program_config_path)
        if program_config:
            self.debug_logger.write(f"[STEP] Program config loaded: start={hex(program_config.diff_start_addr)}, end={hex(program_config.diff_end_addr)}")
        else:
            self.debug_logger.write(f"[STEP] No program config found, will use full output")
        
        # Compare outputs with address filtering
        self.debug_logger.write(f"[STEP] Comparing outputs...")
        test_id = f"{base_name}_t{threads}_b{blocks}"
        error_log = self.diff_dir / f"{test_id}_error.log"
        
        sim_output = Path(self.settings.files.sim_output)
        
        # Prepare filtered output files
        filtered_exp_file = self.diff_dir / f"{test_id}_exp_filtered.hex"
        filtered_sim_file = self.diff_dir / f"{test_id}_sim_filtered.hex"
        self.prepare_outputs_with_address_filtering(
            program_config,
            expected_file,
            sim_output,
            filtered_exp_file,
            filtered_sim_file
        )
        
        if self.compare_outputs(filtered_exp_file, filtered_sim_file, error_log):
            # Test passed
            self.debug_logger.write(f"[PASS] {base_name} outputs match")
            if not self.skip_cleanup:
                # Clean up all artifacts
                if error_log.exists():
                    error_log.unlink()
                if hex_output.exists():
                    hex_output.unlink()
                if filtered_exp_file.exists():
                    filtered_exp_file.unlink()
                if filtered_sim_file.exists():
                    filtered_sim_file.unlink()
            else:
                # Save artifacts for inspection
                (self.diff_dir / f"{test_id}_exp.hex").write_text(filtered_exp_file.read_text())
                (self.diff_dir / f"{test_id}_sim.hex").write_text(filtered_sim_file.read_text())
                if hex_output.exists():
                    (self.diff_dir / f"{test_id}_meminit.hex").write_text(hex_output.read_text())
            return TestResult(base_name, True, threads, blocks)
        else:
            # Test failed - save artifacts for debugging
            self.debug_logger.write(f"[FAIL] {base_name} outputs do not match")
            (self.diff_dir / f"{test_id}_exp.hex").write_text(filtered_exp_file.read_text())
            (self.diff_dir / f"{test_id}_sim.hex").write_text(filtered_sim_file.read_text())
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
    
    def load_sweep_cases(self) -> Tuple[Path, List[dict]]:
        """Load sweep case definitions from a TOML file."""
        if self.sweep_config is None:
            raise ValueError("Sweep mode requires --sweep-config")

        sweep_spec = toml.load(self.sweep_config)
        output_root = Path(sweep_spec.get("output_root", "results/sweeps"))
        if not output_root.is_absolute():
            output_root = (self.sweep_config.parent / output_root).resolve()

        raw_cases = sweep_spec.get("cases", [])
        if not raw_cases:
            raise ValueError(f"No [[cases]] entries found in {self.sweep_config}")

        cases = []
        for raw_case in raw_cases:
            case_id = raw_case.get("id")
            config_value = raw_case.get("config")
            if not case_id or not config_value:
                raise ValueError("Each [[cases]] entry must define both 'id' and 'config'")

            config_path = Path(config_value)
            if not config_path.is_absolute():
                config_path = (self.sweep_config.parent / config_path).resolve()

            cases.append({
                "id": case_id,
                "config_path": config_path,
            })

        return output_root, cases

    def prepare_sweep_input(self, test_file: Path) -> Tuple[bool, Optional[Path], Optional[str]]:
        """Prepare the simulator input for a sweep case."""
        if self.src == "bin":
            return True, test_file, None

        if self.src == "assembly":
            base_name = test_file.stem
            dir_name = test_file.parent

            success, error = self.run_assembler(test_file)
            if not success:
                return False, None, error

            self.format_instructions()
            self.create_meminit(base_name, dir_name)
            self.convert_hex_to_bin()
            return True, Path(self.settings.files.meminit_bin), None

        return False, None, f"Unsupported src '{self.src}' for sweep mode"

    def run_sweep(self) -> int:
        """Run simulator sweeps over one or more inputs and case configs."""
        output_root, cases = self.load_sweep_cases()
        output_root.mkdir(parents=True, exist_ok=True)

        patterns = self.sweep_inputs or [self.search_pattern]
        test_files: List[Path] = []
        for pattern in patterns:
            test_files.extend(self.find_test_files_for_pattern(pattern))

        test_files = sorted(set(test_files))
        if not test_files:
            return 1

        summary_rows = []

        print("=" * 40)
        print("      Starting GPU Sweep")
        print(f"      Source:      {self.src}")
        print(f"      Root:        {self.test_root}")
        print(f"      Inputs:      {patterns}")
        print(f"      Cases:       {len(cases)}")
        print(f"      Output Root: {output_root}")
        print("=" * 40)

        for test_file in test_files:
            prep_ok, sim_input, prep_error = self.prepare_sweep_input(test_file)
            if not prep_ok or sim_input is None:
                print(f"{Colors.RED}[FAIL]{Colors.NC}     {test_file.name} (prepare failed)")
                self.fail_count += 1
                summary_rows.append({
                    "test_name": test_file.name,
                    "case_id": "PREPARE",
                    "config_path": "",
                    "cycles": 0,
                    "finished": False,
                    "passed": False,
                    "output_dir": "",
                    "error": prep_error or "Unknown prepare error",
                })
                continue

            for case in cases:
                case_id = case["id"]
                case_config = case["config_path"]
                run_dir = output_root / test_file.stem / case_id
                run_name = f"{test_file.stem}_{case_id}"
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "config.toml").write_text(case_config.read_text())

                ok = self.run_simulator(
                    input_file=str(sim_input),
                    test_name=run_name,
                    config_path=case_config,
                    output_dir=run_dir,
                )

                compare_checked, compare_passed, compare_message = self.compare_sweep_outputs(
                    test_file=test_file,
                    sim_input=sim_input,
                    run_dir=run_dir,
                )

                passed = ok and self.last_sim_finished
                if self.truth is not None:
                    passed = passed and bool(compare_checked) and bool(compare_passed)

                if passed:
                    print(f"{Colors.GREEN}[PASS]{Colors.NC}     {test_file.name} :: {case_id} ({self.last_sim_cycles} cycles)")
                    self.pass_count += 1
                else:
                    detail = f" - {compare_message}" if compare_message else ""
                    print(f"{Colors.RED}[FAIL]{Colors.NC}     {test_file.name} :: {case_id} ({self.last_sim_cycles} cycles){detail}")
                    self.fail_count += 1

                summary_rows.append({
                    "test_name": test_file.name,
                    "case_id": case_id,
                    "config_path": str(case_config),
                    "cycles": self.last_sim_cycles,
                    "finished": self.last_sim_finished,
                    "passed": passed,
                    "comparison_mode": self.truth or "",
                    "comparison_checked": compare_checked,
                    "comparison_passed": "" if compare_passed is None else compare_passed,
                    "output_dir": str(run_dir),
                    "error": (
                        "Simulator run failed"
                        if not ok else
                        compare_message
                    ),
                })

        summary_csv = output_root / "summary.csv"
        fieldnames = [
            "test_name",
            "case_id",
            "config_path",
            "cycles",
            "finished",
            "passed",
            "comparison_mode",
            "comparison_checked",
            "comparison_passed",
            "output_dir",
            "error",
        ]
        write_header = not summary_csv.exists() or summary_csv.stat().st_size == 0
        with open(summary_csv, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerows(summary_rows)

        self.debug_logger.close()

        print("=" * 40)
        print("Sweep Summary")
        print(f"Passed:  {Colors.GREEN}{self.pass_count}{Colors.NC}")
        print(f"Failed:  {Colors.RED}{self.fail_count}{Colors.NC}")
        print(f"Summary: {summary_csv}")

        return 0 if self.fail_count == 0 else 1

    def run(self) -> int:
        """Run tests or sweep mode."""
        if self.sweep:
            return self.run_sweep()

        print("=" * 40)
        print("      Starting GPU System Tests")
        print(f"      Source:  {self.src}")
        print(f"      Truth:   {self.truth}")
        print(f"      Root:    {self.test_root}")
        print(f"      Pattern: {self.search_pattern}")
        print("=" * 40)

        test_files = self.find_test_files()
        if not test_files:
            return 1

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

            if result.passed:
                print(f"{Colors.GREEN}[PASS]{Colors.NC}     {result.name} (t={result.threads}, b={result.blocks})")
                self.pass_count += 1
            else:
                print(f"{Colors.RED}[FAIL]{Colors.NC}     {result.name} (t={result.threads}, b={result.blocks})")
                self.fail_count += 1

        if not self.skip_cleanup:
            self.cleanup()

        self.debug_logger.close()

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
    parser.add_argument(
        '--enable-simulator-output', action='store_true',
        help='Display simulator print statements to terminal (and optionally to file)'
    )
    parser.add_argument(
        '--simulator-output-file', type=str, default=None,
        help='Save simulator output to results/debug/<file> (use with --enable-simulator-output for dual output)'
    )
    parser.add_argument(
        '--sweep', action='store_true',
        help='Run sweep mode using a list of real per-case config TOML files'
    )
    parser.add_argument(
        '--sweep-config', type=Path, default=None,
        help='Path to sweep case definition TOML'
    )
    parser.add_argument(
        '--sweep-inputs', nargs='+', default=None,
        help='One or more test file patterns/paths for sweep mode (e.g. unit/ program/pixel/)'
    )

    args = parser.parse_args()

    if args.clean and args.src is None and args.truth is None and not args.sweep:
        try:
            runner = GPUTestRunner(
                None, None, None, args.config, args.clean, args.skip_cleanup,
                args.enable_cycle_limit, args.max_cycles, args.debug_file,
                args.debug_dual_output, args.enable_simulator_output,
                args.simulator_output_file
            )
            runner._clean_results()
            print(f"{Colors.GREEN}Results directory cleaned.{Colors.NC}")
            return 0
        except Exception as e:
            print(f"{Colors.RED}Error:{Colors.NC} {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1

    if args.sweep:
        if args.src is None:
            parser.error("--src is required with --sweep")
        if args.sweep_config is None:
            parser.error("--sweep-config is required with --sweep")

        try:
            runner = GPUTestRunner(
                src=args.src,
                truth=args.truth,
                search_pattern=args.pattern,
                config_path=args.config,
                clean=args.clean,
                skip_cleanup=args.skip_cleanup,
                enable_cycle_limit=args.enable_cycle_limit,
                max_cycles=args.max_cycles,
                debug_file=args.debug_file,
                debug_dual_output=args.debug_dual_output,
                enable_simulator_output=args.enable_simulator_output,
                simulator_output_file=args.simulator_output_file,
                sweep=True,
                sweep_config=args.sweep_config,
                sweep_inputs=args.sweep_inputs,
            )
            sys.exit(runner.run())
        except Exception as e:
            print(f"{Colors.RED}Error:{Colors.NC} {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)

    if args.src is None or args.truth is None:
        parser.error("--src and --truth are required (unless using --clean alone or --sweep)")

    try:
        runner = GPUTestRunner(
            args.src, args.truth, args.pattern, args.config, args.clean,
            args.skip_cleanup, args.enable_cycle_limit, args.max_cycles,
            args.debug_file, args.debug_dual_output,
            args.enable_simulator_output, args.simulator_output_file
        )
        sys.exit(runner.run())
    except Exception as e:
        print(f"{Colors.RED}Error:{Colors.NC} {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
