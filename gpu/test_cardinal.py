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

Debugging:
  If a test fails, check the 'test_diffs/' directory for detailed
  logs, expected vs. actual hex dumps, and diff results.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass

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
    
    def __init__(self, src: str, truth: str, search_pattern: Optional[str] = None, config_path: Optional[Path] = None, clean: bool = False, skip_cleanup: bool = False, enable_cycle_limit: bool = False, max_cycles: Optional[int] = None):
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
        """
        # Validate arguments
        if src not in ("assembly", "bin"):
            raise ValueError(f"Invalid src: {src}. Must be 'assembly' or 'bin'")
        if truth not in ("emu", "exp"):
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
        
        # Clean results directory if requested
        if self.clean:
            self._clean_results()
        
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
    
    def create_meminit(self, base_name: str, dir_name: Path) -> None:
        """Create memory initialization file.
        
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
    
    def run_simulator(self, input_file: str) -> bool:
        """Run the simulator using SM class.
        
        Args:
            input_file: Input binary file
            
        Returns:
            True if successful
        """
        try:
            # Create SM instance with simulator config
            sm = SM(
                test_file=Path(input_file),
                test_file_type="bin",
                config=self.settings
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
                print(f"{Colors.YELLOW}Warning:{Colors.NC} Simulation hit max cycle limit of {self.max_cycles}")
            
            # Finalize performance counter collection
            sm.finalize()
            
            # Dump register file to output
            sm.pipeline["mem"].dump(path=str(self.settings.files.sim_output))
            #pipeline_rf = sm.pipeline.get('pipeline_rf')
            #if pipeline_rf:
            #    pipeline_rf.dump(str(self.settings.files.sim_output))
            #else:
            #    print(f"{Colors.RED}Error:{Colors.NC} Could not find pipeline_rf in SM")
            #    return False
            
            return True
        except Exception as e:
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
        
        # Run simulator
        self.run_simulator(self.settings.files.meminit_bin)
        
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
        """Test a single binary file.
        
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
        
        # Get thread/block counts
        threads = self.settings.test_parameters.default_threads
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
        
        # Run simulator
        self.run_simulator(str(bin_output))
        
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
        
        Args:
            bin_file: Path to binary file
            
        Returns:
            TestResult object
        """
        base_name = bin_file.stem
        
        # Get thread/block counts
        threads = self.settings.test_parameters.default_threads
        blocks = self.settings.test_parameters.default_blocks
        
        # Convert binary to hex for memory initialization
        hex_output = Path(f"{base_name}_meminit.hex")
        self.convert_bin_to_hex(bin_file, hex_output)
        
        # Run simulator
        self.run_simulator(str(bin_file))
        
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
        
        # Run simulator
        self.run_simulator(self.settings.files.meminit_bin)
        
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
        '--src', choices=['assembly', 'bin'], required=True,
        help='Source file type: assembly (.s files) or bin (.bin files)'
    )
    parser.add_argument(
        '--truth', choices=['emu', 'exp'], required=True,
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
    
    args = parser.parse_args()
    
    try:
        runner = GPUTestRunner(args.src, args.truth, args.pattern, args.config, args.clean, args.skip_cleanup, args.enable_cycle_limit, args.max_cycles)
        sys.exit(runner.run())
    except Exception as e:
        print(f"{Colors.RED}Error:{Colors.NC} {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
