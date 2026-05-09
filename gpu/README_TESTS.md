# GPU Test Suite Guide

> This is AI-generated. I am going back to look over this and verify it I promise
> Everything is super new and still a little jank. I will be working on fixing things and making the workflow more straightforward. There are also lots of features I plan on adding. So pull often and bear with me lol.
> 
Complete documentation for the GPU System Test Automation (`test_cardinal.py`) - a comprehensive testing framework for validating GPU simulator correctness against reference implementations.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Current Test Status](#current-test-status)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [Test Modes](#test-modes)
7. [Example Workflows](#example-workflows)
8. [Output and Debugging](#output-and-debugging)
9. [Advanced Options](#advanced-options)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The GPU test suite (`test_cardinal.py`) automates validation of GPU simulator behavior by:

- **Compiling** assembly code or using pre-compiled binaries
- **Running** tests through the GPU emulator (golden model) and simulator
- **Comparing** outputs to identify correctness issues
- **Generating** detailed diagnostic reports for failures

### Key Concepts

- **Source (`--src`)**: Where test code comes from
  - `assembly` - Compile `.s` files into binaries
  - `bin` - Use pre-compiled `.bin` files
  
- **Truth (`--truth`)**: What we compare against
  - `emu` - Run emulator as the golden model
  - `exp` - Compare against pre-generated expected output files

### Test Modes (Src × Truth Combinations)

| Mode | Src | Truth | Use Case |
|------|-----|-------|----------|
| **Assembly vs Emulator** | assembly | emu | Full pipeline: compile → emulate → simulate → compare |
| **Binary vs Emulator** | bin | emu | Test without assembly compilation |
| **Binary vs Expected** | bin | exp | Compare to golden/reference files |
| **Assembly vs Expected** | assembly | exp | Compile then compare to golden files |

---

## Current Test Status

### ✅ Working Tests

**Unit Tests (Recommended Configuration):**
```bash
# CORRECT: Unit tests in binary mode against emulator
python3 test_cardinal.py --src bin --truth emu unit/
```
- Works: All unit tests pass
- Don't use: Assembly mode, expected files (jpnz will fail)

**Program Tests (Limited Support):**
```bash
# CORRECT: Only saxpy in assembly mode against emulator
python3 test_cardinal.py --src assembly --truth emu program/saxpy.s
```
- Works: Only saxpy
- Everything else in program/ fails

### ❌ Non-Working Tests

**Do NOT Run:**
- `cos`, `sin` (estimation functions - slight differences expected)
- `prlw`, `prsw` (print functions - not implemented)
- `lb`, `lh` (load byte/half - not implemented)
- Any program tests other than `saxpy`

**Why They Fail:**
- Instruction not yet implemented in simulator
- Estimation functions have inherent precision differences
- Load operations incomplete

### Quick Test Commands

```bash
# Test all unit tests (WORKING)
python3 test_cardinal.py --src bin --truth emu unit/

# Test only saxpy program (WORKING)
python3 test_cardinal.py --src assembly --truth emu program/saxpy.s

# DON'T test these (will fail)
python3 test_cardinal.py --src assembly --truth emu cos.s      # ❌ Don't run
python3 test_cardinal.py --src assembly --truth emu sin.s      # ❌ Don't run
python3 test_cardinal.py --src assembly --truth emu unit/      # ❌ Use bin mode instead
```

---

## Quick Start

### Basic Commands

```bash
# Test assembly files against emulator
python3 test_cardinal.py --src assembly --truth emu

# Test binary files against emulator
python3 test_cardinal.py --src bin --truth emu

# Test assembly against pre-generated expected files
python3 test_cardinal.py --src assembly --truth exp

# Test binary against expected files
python3 test_cardinal.py --src bin --truth exp
```

### With Patterns

```bash
# Test only unit tests
python3 test_cardinal.py --src assembly --truth emu unit/

# Test specific files matching pattern
python3 test_cardinal.py --src bin --truth emu program/saxpy*

# Test all assembly files in a directory
python3 test_cardinal.py --src assembly --truth exp program/*
```

### With Options

```bash
# Keep output files for inspection (don't cleanup)
python3 test_cardinal.py --src assembly --truth emu --skip-cleanup

# Limit simulation cycles to prevent hanging
python3 test_cardinal.py --src bin --truth emu --enable-cycle-limit --max-cycles 10000

# Use custom config file
python3 test_cardinal.py --src assembly --truth emu --config custom_config.toml

# Enable debug output to file only
python3 test_cardinal.py --src bin --truth exp --debug-file test_debug.log

# Enable debug output to both terminal and file
python3 test_cardinal.py --src bin --truth exp --debug-file test_debug.log --debug-dual-output

# Combine multiple options
# Combine multiple options
python3 test_cardinal.py --src assembly --truth exp unit/ --skip-cleanup --enable-cycle-limit --max-cycles 50000 --debug-file combined.log
```

---

## Test Directory Structure

The test suite supports two directory structures:

### New Structure (Program Tests)
```
tests/
├── bin/program/
│   └── <test_name>/
│       └── t<num_threads>/
│           └── <test_name>.bin
└── exp/program/
    └── <test_name>/
        └── t<num_threads>/
            └── <test_name>.hex
```

**Example:** `tests/bin/program/pixel/t1024/pixel.bin`

### Old Structure (Unit Tests)
```
tests/
├── bin/unit/
│   └── <category>/
│       └── <test_name>.bin
└── exp/unit/
    └── <category>/
        └── <test_name>_exp_t<threads>_b<blocks>.hex
```

**Example:** `tests/bin/unit/b_type/beq.bin`

---

## Thread Count Validation

The test suite automatically validates that thread counts are consistent across:

1. **Directory Structure** - Thread count from path (e.g., `t1024` → 1024 threads)
2. **Expected File Path** - Thread count from expected output file location/name
3. **MMIO Configuration** - Thread count from kernel parameters (when TBS enabled)

### Validation Behavior

**When validation passes:**
- Test proceeds normally
- No additional output or delay

**When validation fails:**
- Test is marked as **FAILED**
- Error message saved to `results/test_diffs/<test_name>_validation.log`
- Message printed to console and debug file (if enabled)

### Example Validation Error

```
[FAIL]     pixel (Thread count validation failed)

THREAD COUNT VALIDATION ERROR:
Thread count mismatch: directory path has 1024 threads but 
expected file 'pixel.hex' has 512 threads
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Directory thread count (t1024) doesn't match expected file name/path (t512) | Mismatched test metadata | Rename directory or expected file to match |
| MMIO register value (0x18) differs from directory thread count | MMIO configuration error | Update meminit file or config.toml |
| Thread count extracted differently from old vs new structure | Structure mismatch | Ensure consistent naming conventions |

---

## Current Test Status

### ⚠️ Important: Known Working and Broken Tests

The test suite is under active development. **Not all tests are functional yet.** Use the commands below based on what you're testing.

### Working Tests

#### Unit Tests ✅
**Command:**
```bash
python3 test_cardinal.py --src bin --truth emu unit/
```

**Required Configuration:**
- **Threads:** 32
- **Blocks:** 1
- **SM Config:** `num_warps * threads_per_warp = 32` (e.g., 1 warp × 32 threads/warp)

**Configuration:**
```toml
[test_parameters]
default_threads = 32
default_blocks = 1

[sm]
num_warps = 1
threads_per_warp = 32
```

**Status:** All unit tests pass  
**Note:** Must use `bin` mode with `emu` comparison. Using `assembly` or `exp` modes will fail (jpnz instruction has issues in these modes).

**Example:**
```bash
python3 test_cardinal.py --src bin --truth emu unit/addi.bin
```

#### Saxpy Program ✅
**Command:**
```bash
python3 test_cardinal.py --src assembly --truth emu program/saxpy.s
```

**Required Configuration:**
- **Threads:** 1024
- **Blocks:** 1
- **SM Config:** `num_warps * threads_per_warp = 1024` (e.g., 32 warps × 32 threads/warp)

**Configuration:**
```toml
[test_parameters]
default_threads = 1024
default_blocks = 1

[sm]
num_warps = 32
threads_per_warp = 32
```

**Status:** Passes with assembly mode comparing to emulator  
**Note:** Other modes and combinations fail. Must use exactly `--src assembly --truth emu`.

**Example:**
```bash
python3 test_cardinal.py --src assembly --truth emu program/saxpy.s
```

### ⚠️ Important Configuration Constraint

**The SM hardware configuration must match the test thread count:**

```
num_warps × threads_per_warp = default_threads (from test_parameters)
```

**Examples:**

| Test | default_threads | num_warps | threads_per_warp | Valid? |
|------|-----------------|-----------|------------------|--------|
| Unit Tests | 32 | 1 | 32 | ✅ 1 × 32 = 32 |
| Unit Tests | 32 | 32 | 32 | ❌ 32 × 32 = 1024 |
| Saxpy | 1024 | 32 | 32 | ✅ 32 × 32 = 1024 |
| Saxpy | 1024 | 1 | 32 | ❌ 1 × 32 = 32 |

**If your configuration doesn't match, tests will fail or produce incorrect results!**

### Non-Working Tests ❌

The following tests **should not be run** as they have known issues:

| Test | Issue | Status |
|------|-------|--------|
| **cos** | Uses estimation function, produces slightly incorrect results | Expected behavior |
| **sin** | Uses estimation function, produces slightly incorrect results | Expected behavior |
| **prlw** | Not fully implemented | Broken |
| **prsw** | Not fully implemented | Broken |
| **lb** | Load byte instruction issue | Broken |
| **lh** | Load half-word instruction issue | Broken |
| **Other program tests** | Not yet implemented | Broken |

**Do not run:**
```bash
# ❌ AVOID - These will fail:
python3 test_cardinal.py --src assembly --truth emu cos.s
python3 test_cardinal.py --src assembly --truth emu sin.s
python3 test_cardinal.py --src assembly --truth emu prlw.s
python3 test_cardinal.py --src assembly --truth emu prsw.s
python3 test_cardinal.py --src assembly --truth emu lb.s
python3 test_cardinal.py --src assembly --truth emu lh.s
python3 test_cardinal.py --src assembly --truth emu program/   # (except saxpy)
```

### Current Test Coverage

```
tests/
├── assembly/unit/        ✅ All working (but see note below)
├── assembly/program/
│   ├── saxpy.s          ✅ Works (assembly mode only)
│   ├── cos.s            ❌ Estimation function (expected)
│   ├── sin.s            ❌ Estimation function (expected)
│   ├── prlw.s           ❌ Not implemented
│   ├── prsw.s           ❌ Not implemented
│   ├── lb.s             ❌ Broken
│   └── lh.s             ❌ Broken
└── bin/unit/            ✅ All working
```

### Recommended Test Commands

Use these commands to validate the current test suite:

```bash
# ✅ Test unit binaries (THE MAIN TEST)
python3 test_cardinal.py --src bin --truth emu unit/

# ✅ Test saxpy assembly (SECONDARY TEST)
python3 test_cardinal.py --src assembly --truth emu program/saxpy.s

# ✅ Debug individual unit test
python3 test_cardinal.py --src bin --truth emu unit/addi.bin --skip-cleanup

# ✅ Debug saxpy with cycle limit
python3 test_cardinal.py --src assembly --truth emu program/saxpy.s --enable-cycle-limit --max-cycles 20000
```

---

## Configuration

### Configuration Files

- **`config.py`**: Python configuration class definitions
- **`config.toml`**: TOML configuration values (read by config.py)

Both files are located in the same directory as `test_cardinal.py`.

### config.toml Reference

#### Paths Section
```toml
[paths]
assembler_script = "assembler/assembler.py"      # Path to assembly compiler
opcodes = "assembler/opcodes.txt"                # Opcode definitions
emulator = "src/emulator/src/emulator.py"        # Path to emulator
hex_bin_converter = "tests/final_integration/hex_bin_converter.py"  # Converter tool
```

#### Directories Section
```toml
[directories]
diff_dir = "results/test_diffs"                  # Output directory for test results
test_root_asm = "tests/assembly"                 # Assembly source files
test_root_bin = "tests/bin"                      # Binary test files
expected_dir = "tests/exp"                       # Expected output files
```

#### Files Section
```toml
[files]
raw_asm_output = "results/raw_instr.hex"         # Assembled instructions
formatted_instr = "results/formatted_instr.hex"  # Formatted instructions
meminit = "results/meminit.hex"                  # Memory initialization (hex)
meminit_bin = "results/meminit.bin"              # Memory initialization (binary)
emu_output = "results/memgolden.hex"             # Emulator output
emu_temp_output = "src/emulator/memsim.hex"      # Temporary emulator output
sim_output = "results/memsim.hex"                # Simulator output
final_expected = "results/final_expected_combined.hex"  # Combined expected for comparison
temp_cmd_log = "results/temp_command_output.txt" # Command execution logs
```

#### Test Parameters Section
```toml
[test_parameters]
default_start_pc = 0                             # Default program counter start
default_threads = 32                             # Threads per test (shared by all modes)
default_blocks = 1                               # Thread blocks (shared by all modes)
format = "hex"                                   # Output format
default_pattern = "*.s"                          # Default search pattern
```

#### Simulator Configuration

**SM (Streaming Multiprocessor):**
```toml
[sm]
sm_no = 0                                        # SM identifier
num_warps = 32                                   # Number of warps
num_preds = 16                                   # Predicates per warp (for TBS mode)
threads_per_warp = 32                            # Threads per warp
enable_tbs = false                               # Enable ThreadBlockScheduler
kernel_base_addr = 0x0                           # Kernel base address
tb_size = 32                                     # Thread block size
```

**Memory:**
```toml
[memory]
start_pc = 0x0                                   # Starting program counter
latency = 2                                      # Memory access latency
policy = "rr"                                    # Memory scheduling policy
```

**Kernel, Caches, and Other Components:**
```toml
[kernel]
max_kernels_per_sm = 1
kernel_id = 9203930

[icache]
cache_size = 32768
block_size = 4
associativity = 1

[dcache]
cache_size = 32768
block_size = 4
associativity = 1

[functional_units]
[writeback]
[register_file]
[predicate_register_file]
```

### Modifying Configuration

#### Change Thread Count
```toml
[test_parameters]
default_threads = 64  # Changes for all test modes
```

#### Disable ThreadBlockScheduler
```toml
[sm]
enable_tbs = false
```

#### Set Memory Latency
```toml
[memory]
latency = 3  # Increase memory latency
```

#### Use Custom Config File
```bash
python3 test_cardinal.py --src assembly --truth emu --config my_config.toml
```

---

## Usage

### Command-Line Arguments

```
Usage: python3 test_cardinal.py [OPTIONS] [PATTERN]

REQUIRED:
  --src {assembly|bin}     Source file type
  --truth {emu|exp}        Ground truth source

OPTIONAL:
  PATTERN                  File search pattern
                           Examples: *.s, unit/, program/saxpy*
  
  --config CONFIG          Path to config file (default: config.toml)
  --skip-cleanup           Don't delete test artifacts after completion
  --enable-cycle-limit     Enforce maximum cycle limit
  --max-cycles N           Max cycles (default: 100000)
  -h, --help              Show help message
```

### Pattern Syntax

Patterns support flexible file and directory matching:

```bash
# File patterns (standard glob)
*.s                    # All assembly files
saxpy*                 # Files starting with "saxpy"
test.bin               # Specific file
math_*.s               # Pattern matching

# Directory patterns (NEW)
unit/                  # All files in unit/ directory
program/               # All files in program/ directory

# Directory + file pattern combinations
unit/*.s               # Only .s files in unit/
program/saxpy*         # Files matching "saxpy*" in program/
```

---

## Test Modes

### Mode 1: Assembly vs Emulator

**Command:**
```bash
python3 test_cardinal.py --src assembly --truth emu
```

**Pipeline:**
```
source.s → Assembler → meminit.hex → Emulator
                                    ├─ memgolden.hex
                                    └─ Simulator → memsim.hex
                                                 → DIFF → Pass/Fail
```

**Use Case:**
- Full validation pipeline
- Tests both assembler and simulator
- Compares emulator (golden) vs simulator output

**Files Generated:**
- `raw_instr.hex` - Raw assembler output
- `formatted_instr.hex` - Formatted instructions
- `meminit.hex` - Memory initialization
- `memgolden.hex` - Emulator result
- `memsim.hex` - Simulator result
- `results/test_diffs/*` - Comparison details

---

### Mode 2: Binary vs Emulator

**Command:**
```bash
python3 test_cardinal.py --src bin --truth emu
```

**Pipeline:**
```
source.bin → Emulator → memgolden.hex
          ├─ Simulator → memsim.hex
          └─ DIFF → Pass/Fail
```

**Use Case:**
- Test pre-compiled binaries
- Skip assembly compilation
- Faster iteration when binaries are already built

**Files Generated:**
- `meminit.hex` - Memory initialization from binary
- `memgolden.hex` - Emulator result
- `memsim.hex` - Simulator result
- `results/test_diffs/*` - Comparison details

---

### Mode 3: Binary vs Expected

**Command:**
```bash
python3 test_cardinal.py --src bin --truth exp
```

**Pipeline:**
```
source.bin → Simulator → memsim.hex
          ├─ Expected file (from tests/exp/)
          └─ DIFF → Pass/Fail
```

**Use Case:**
- Compare against pre-generated reference files
- No emulator dependency
- Validation with known-good outputs

**Expected File Format:**
```
tests/exp/
├── test_name_t32_b1_exp.hex
├── test_name_t64_b1_exp.hex
├── test_name_t32_b2_exp.hex
└── ...
```

**Files Generated:**
- `memsim.hex` - Simulator result
- `results/test_diffs/*` - Comparison details

---

### Mode 4: Assembly vs Expected

**Command:**
```bash
python3 test_cardinal.py --src assembly --truth exp
```

**Pipeline:**
```
source.s → Assembler → meminit.hex → Simulator → memsim.hex
        ├─ Expected file (from tests/exp/)
        └─ DIFF → Pass/Fail
```

**Use Case:**
- End-to-end validation with assembly
- Compare to reference implementation
- Full pipeline testing

**Files Generated:**
- `raw_instr.hex` - Assembler output
- `formatted_instr.hex` - Formatted instructions
- `meminit.hex` - Memory initialization
- `memsim.hex` - Simulator result
- `results/test_diffs/*` - Comparison details

---

## Example Workflows

### Workflow 1: Quick Validation of Single Test

```bash
# Check if one assembly test works against emulator
python3 test_cardinal.py --src assembly --truth emu addi.s
```

**Output:**
```
========================================
      Starting GPU System Tests
      Source:  assembly
      Truth:   emu
      Root:    /path/to/tests/assembly
      Pattern: addi.s
========================================
[PASS]     addi (t=32, b=1)
========================================
Summary
Passed:  1
Failed:  0
```

---

### Workflow 2: Batch Test with Directory Filter

```bash
# Test all unit tests against emulator
python3 test_cardinal.py --src assembly --truth emu unit/
```

**Output shows pass/fail for each test in unit/ directory**

---

### Workflow 3: Debug Failed Test

```bash
# Run test with skip-cleanup to examine artifacts
python3 test_cardinal.py --src assembly --truth emu addi.s --skip-cleanup
```

**Files available in `results/test_diffs/`:**
- `addi_t32_b1_sim.hex` - What simulator produced
- `addi_t32_b1_exp.hex` - Expected output
- `addi_t32_b1_error.log` - Diff output showing differences
- `addi_t32_b1_meminit.hex` - Instructions loaded into memory

**Inspect differences:**
```bash
cat results/test_diffs/addi_t32_b1_error.log
```

---

### Workflow 4: Test Different Thread Configurations

Modify `config.toml`:
```toml
[test_parameters]
default_threads = 64   # Change from 32 to 64
default_blocks = 2     # Change from 1 to 2
```

Then run:
```bash
python3 test_cardinal.py --src assembly --truth emu
```

**All tests now run with 64 threads and 2 blocks**

---

### Workflow 5: Test Against Reference Implementation

```bash
# First, generate reference files using emulator
# (Files saved to tests/exp/ directory)

# Then validate simulator against those references
python3 test_cardinal.py --src assembly --truth exp
```

---

### Workflow 6: Prevent Infinite Loops

```bash
# If test hangs, limit cycles
python3 test_cardinal.py --src bin --truth emu --enable-cycle-limit --max-cycles 10000
```

**Simulator will stop after 10,000 cycles, preventing hangs**

---

### Workflow 7: Comprehensive Test Suite Run

```bash
# Test everything: all modes against all patterns
python3 test_cardinal.py --src assembly --truth emu

# Then test against references
python3 test_cardinal.py --src assembly --truth exp

# Test binaries too
python3 test_cardinal.py --src bin --truth emu
python3 test_cardinal.py --src bin --truth exp
```

---

## Output and Debugging

### Directory Structure

```
gpu/
├── test_cardinal.py              # Main test script
├── config.py                      # Configuration classes
├── config.toml                    # Configuration values
├── README_TESTS.md               # This file
│
├── results/                       # All test output
│   ├── test_diffs/               # Detailed test results
│   │   ├── addi_t32_b1_sim.hex   # Simulator output
│   │   ├── addi_t32_b1_exp.hex   # Expected output
│   │   ├── addi_t32_b1_error.log # Diff details
│   │   └── ...
│   ├── raw_instr.hex             # Assembled instructions
│   ├── meminit.hex               # Memory init (hex)
│   ├── meminit.bin               # Memory init (binary)
│   ├── memgolden.hex             # Emulator output
│   └── memsim.hex                # Simulator output
│
├── tests/
│   ├── assembly/                 # Assembly source files
│   │   ├── unit/                 # Unit tests
│   │   ├── program/              # Program tests
│   │   └── benchmarks/           # Benchmark tests
│   ├── bin/                      # Pre-compiled binaries
│   │   ├── unit/
│   │   ├── program/
│   │   └── benchmarks/
│   └── exp/                      # Expected output files
│       ├── test_t32_b1_exp.hex
│       └── ...
```

### Reading Test Output

**Pass Output:**
```
[PASS]     saxpy (t=32, b=1)
```
- Test passed
- Thread count: 32
- Block count: 1

**Fail Output:**
```
[FAIL]     matmul (t=64, b=2)
```
- Test failed
- Output saved to `results/test_diffs/`

### Examining Failures

When a test fails with `--skip-cleanup`:

1. **Find the error log:**
   ```bash
   cat results/test_diffs/test_name_tX_bY_error.log
   ```

2. **Compare outputs:**
   ```bash
   diff results/test_diffs/test_name_tX_bY_exp.hex \
        results/test_diffs/test_name_tX_bY_sim.hex
   ```

3. **Check memory initialization:**
   ```bash
   cat results/test_diffs/test_name_tX_bY_meminit.hex
   ```

4. **View full simulator output:**
   ```bash
   cat results/test_diffs/test_name_tX_bY_sim.hex | head -20
   ```

---

## Advanced Options

### Cycle Limiting

Prevent infinite loops by limiting simulation cycles:

```bash
python3 test_cardinal.py --src assembly --truth emu \
  --enable-cycle-limit --max-cycles 5000
```

**Default:** No cycle limit (runs until completion)

**Use when:** Tests hang or run unexpectedly long

### Artifact Preservation

Keep test artifacts for detailed analysis:

```bash
python3 test_cardinal.py --src assembly --truth emu --skip-cleanup
```

**Default:** Clean up after successful tests (keep failures)

**Files preserved:**
- Simulator outputs
- Expected outputs
- Diff logs
- Error messages

### Custom Configuration

Use a non-default config file:

```bash
python3 test_cardinal.py --src assembly --truth emu \
  --config /path/to/custom_config.toml
```

**Use when:** Testing different hardware configurations or parameters

### Debug Logging

Capture detailed debug output for test analysis:

```bash
# Write debug output to file only
python3 test_cardinal.py --src bin --truth exp --debug-file test_run.log

# Write debug output to both terminal and file
python3 test_cardinal.py --src bin --truth exp --debug-file test_run.log --debug-dual-output
```

**Options:**
- `--debug-file FILE` - Filename for debug output (written to `results/debug/FILE`)
- `--debug-dual-output` - Print to both terminal and file (use with `--debug-file`)

**Default:** No debug output (normal operation)

**Debug output includes:**
- Thread count validation messages
- Configuration details
- Test execution logs
- Error details

**Use when:**
- Debugging test failures
- Analyzing thread count mismatches
- Investigating configuration issues
- Recording test execution for later review

---

## Troubleshooting

### Error: "No files found matching pattern"

**Cause:** Pattern doesn't match any files in the directory

**Solution:**
1. Check file extensions match the source type
   - `--src assembly` needs `.s` files
   - `--src bin` needs `.bin` files

2. Verify directory exists:
   ```bash
   ls tests/assembly/unit/
   ```

3. Try a simpler pattern:
   ```bash
   python3 test_cardinal.py --src assembly --truth emu "*.s"
   ```

---

### Error: "Invalid src/truth combination"

**Cause:** Invalid argument values

**Solution:** Verify arguments:
```bash
# WRONG (typo):
python3 test_cardinal.py --src assem --truth emu

# CORRECT:
python3 test_cardinal.py --src assembly --truth emu
```

---

### Error: "ThreadBlockScheduler not available"

**Cause:** TBS enabled but module not found

**Solution:**
1. Disable TBS in config.toml:
   ```toml
   [sm]
   enable_tbs = false
   ```

2. Or ensure TBS module is installed

---

### Test Hangs/Never Completes

**Cause:** Infinite loop in simulator

**Solution:** Use cycle limit:
```bash
python3 test_cardinal.py --src assembly --truth emu \
  --enable-cycle-limit --max-cycles 10000
```

Or investigate with `--skip-cleanup`:
```bash
python3 test_cardinal.py --src assembly --truth emu test_name.s --skip-cleanup
```

Then check `results/test_diffs/` for logs

---

### All Tests Fail After Configuration Change

**Cause:** Configuration may not match your system

**Solution:**
1. Check thread count is reasonable:
   ```toml
   default_threads = 32  # Start conservative
   ```

2. Verify memory latency:
   ```toml
   latency = 2           # Start with default
   ```

3. Test with a single file first:
   ```bash
   python3 test_cardinal.py --src assembly --truth emu addi.s
   ```

---

### Output Files Not Generated

**Cause:** Tests cleanup artifacts after passing

**Solution:** Use `--skip-cleanup` to preserve files:
```bash
python3 test_cardinal.py --src assembly --truth emu --skip-cleanup
```

---

## Tips and Best Practices

1. **Start Small**: Test one file before running full suite
   ```bash
   python3 test_cardinal.py --src assembly --truth emu unit/addi.s
   ```

2. **Use Directories**: Organize tests and use pattern matching
   ```bash
   python3 test_cardinal.py --src assembly --truth emu unit/
   ```

3. **Preserve Artifacts**: Always use `--skip-cleanup` when debugging
   ```bash
   python3 test_cardinal.py --src assembly --truth emu --skip-cleanup
   ```

4. **Check Configuration**: Review `config.toml` before major test runs

5. **Monitor Cycles**: Use `--enable-cycle-limit` for new tests
   ```bash
   python3 test_cardinal.py --src assembly --truth emu \
     --enable-cycle-limit --max-cycles 20000
   ```

6. **Compare Modes**: Test same code in different modes
   ```bash
   # Assembly vs emulator
   python3 test_cardinal.py --src assembly --truth emu saxpy.s
   
   # Binary vs emulator (same test)
   python3 test_cardinal.py --src bin --truth emu saxpy.bin
   ```

---

## Contact and Support

For issues or questions:

1. Check this README for troubleshooting steps
2. Examine test output in `results/test_diffs/`
3. Review configuration in `config.toml`
4. Check error logs in `results/`

---

## Version History

- **1.0** (Current)
  - Semantic arguments (`--src`, `--truth`)
  - Unified configuration parameters
  - Directory pattern support
  - Cycle limiting
  - Artifact preservation
  - Full test suite automation
