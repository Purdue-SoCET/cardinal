# GPU Test Suite - Quick Reference

## ⚡ Current Status - Tests That Work

### Configuration Requirements

**Unit Tests Configuration:**
```toml
default_threads = 32
default_blocks = 1
num_warps = 1
threads_per_warp = 32
```
Constraint: `1 × 32 = 32` ✅

**Saxpy Configuration:**
```toml
default_threads = 1024
default_blocks = 1
num_warps = 32
threads_per_warp = 32
```
Constraint: `32 × 32 = 1024` ✅

**⚠️ CRITICAL:** `num_warps × threads_per_warp` MUST equal `default_threads`!

### ✅ Working Commands (Use These ONLY)

```bash
# Unit tests (ALL PASS - RECOMMENDED)
# ⚠️  MUST use bin mode with emu! Assembly or exp modes will fail (jpnz issue)
# ⚠️  Config: 32 threads, 1 block
python3 test_cardinal.py --src bin --truth emu unit/

# Saxpy program (ONLY working program test)
# ⚠️  MUST use assembly mode with emu! Other modes will fail
# ⚠️  Config: 1024 threads, 1 block
python3 test_cardinal.py --src assembly --truth emu program/saxpy.s
```

### ❌ Broken/Don't Run

```bash
# DON'T run these (they WILL FAIL):

# Unit tests with wrong mode (jpnz instruction fails):
python3 test_cardinal.py --src assembly --truth emu unit/  # ❌ WRONG - use bin mode
python3 test_cardinal.py --src bin --truth exp unit/       # ❌ WRONG - use emu mode

# Non-working instructions:
# cos, sin        - estimation functions (slight precision differences EXPECTED)
# prlw, prsw      - print instructions not implemented
# lb, lh          - load operations not fully implemented

# Any other program tests (only saxpy works):
python3 test_cardinal.py --src assembly --truth emu program/       # ❌ WRONG
python3 test_cardinal.py --src assembly --truth emu program/cos.s  # ❌ WRONG
```

### ✅ Correct Example Commands

```bash
# Debug a unit test
python3 test_cardinal.py --src bin --truth emu unit/addi.bin --skip-cleanup

# Debug saxpy with cycle limit
python3 test_cardinal.py --src assembly --truth emu program/saxpy.s --enable-cycle-limit --max-cycles 20000

# Test all units (takes a while)
python3 test_cardinal.py --src bin --truth emu unit/ --skip-cleanup
```

---

## Basic Commands

```bash
# Assembly vs Emulator (full pipeline)
python3 test_cardinal.py --src assembly --truth emu

# Binary vs Emulator (skip compilation)
python3 test_cardinal.py --src bin --truth emu

# Assembly vs Expected (compile & compare to reference)
python3 test_cardinal.py --src assembly --truth exp

# Binary vs Expected (compare binaries to reference)
python3 test_cardinal.py --src bin --truth exp
```

## With Patterns

```bash
# Test one file
python3 test_cardinal.py --src assembly --truth emu addi.s

# Test directory
python3 test_cardinal.py --src assembly --truth emu unit/

# Test pattern
python3 test_cardinal.py --src assembly --truth emu program/saxpy*

# Test subdirectory with pattern
python3 test_cardinal.py --src bin --truth exp benchmarks/*.bin
```

## Common Options

```bash
# Keep artifacts for inspection
python3 test_cardinal.py --src assembly --truth emu --skip-cleanup

# Prevent hangs (limit cycles)
python3 test_cardinal.py --src assembly --truth emu --enable-cycle-limit --max-cycles 10000

# Use custom config
python3 test_cardinal.py --src assembly --truth emu --config custom.toml

# Debug with output to file only
python3 test_cardinal.py --src bin --truth exp --debug-file test_debug.log

# Debug with output to both terminal and file
python3 test_cardinal.py --src bin --truth exp --debug-file test_debug.log --debug-dual-output

# Combine options
python3 test_cardinal.py --src assembly --truth exp unit/ --skip-cleanup --enable-cycle-limit --max-cycles 50000
```

## Mode Mapping

| What You Want | Command |
|---|---|
| Full pipeline (source → binary → emu vs sim) | `--src assembly --truth emu` |
| Skip compilation (binary → emu vs sim) | `--src bin --truth emu` |
| Compare to golden files (binary → sim vs golden) | `--src bin --truth exp` |
| Compile then compare to golden | `--src assembly --truth exp` |

## Output Files

All output goes to `results/`:

| File | Contains |
|---|---|
| `test_diffs/` | Per-test detailed results |
| `test_diffs/*_sim.hex` | Simulator output |
| `test_diffs/*_exp.hex` | Expected output |
| `test_diffs/*_error.log` | Diff showing differences |
| `meminit.hex` | Memory initialization |
| `memgolden.hex` | Emulator output |
| `memsim.hex` | Simulator output |

## Debugging Failed Test

```bash
# Run with skip-cleanup to preserve files
python3 test_cardinal.py --src assembly --truth emu test.s --skip-cleanup

# View the error
cat results/test_diffs/test_tX_bY_error.log

# Compare outputs
diff results/test_diffs/test_tX_bY_exp.hex \
     results/test_diffs/test_tX_bY_sim.hex
```

## Configuration Changes

Edit `config.toml`:

```toml
# Change thread count (affects all tests)
[test_parameters]
default_threads = 64

# Change block count
default_blocks = 2

# Change memory latency
[memory]
latency = 3

# Disable ThreadBlockScheduler
[sm]
enable_tbs = false
```

## Common Issues

| Problem | Solution |
|---|---|
| "No files found" | Check file extensions and directory path |
| Test hangs | Use `--enable-cycle-limit --max-cycles 10000` |
| Can't find error | Use `--skip-cleanup` to preserve files |
| All tests fail | Try single test first: `python3 test_cardinal.py --src assembly --truth emu addi.s` |

## Arguments Reference

```
--src {assembly|bin}        Source file type (REQUIRED)
--truth {emu|exp}           Ground truth source (REQUIRED)
[pattern]                   Optional file search pattern
--config FILE               Config file path
--skip-cleanup              Don't delete artifacts after passing
--enable-cycle-limit        Enforce max cycles
--max-cycles N              Max cycles (default: 100000)
--debug-file FILE           Write debug output to results/debug/FILE
--debug-dual-output         Print debug output to both terminal and file (use with --debug-file)
-h, --help                  Show help
```

## File Organization

**New Structure (Program Tests with Thread Metadata):**
```
tests/
├── bin/program/          # Pre-compiled binary tests with thread counts
│   └── <test_name>/
│       └── t<threads>/
│           └── <test_name>.bin
├── exp/program/          # Expected outputs with thread counts
│   └── <test_name>/
│       └── t<threads>/
│           └── <test_name>.hex
├── bin/unit/             # Unit tests (legacy structure)
│   └── <category>/
│       └── <test_name>.bin
└── exp/unit/             # Expected outputs for unit tests
    └── <category>/
        └── <test_name>_exp_t<threads>_b<blocks>.hex

results/
├── debug/                # Debug output files (if --debug-file used)
├── test_diffs/           # Per-test detailed results
├── meminit.hex
├── memgolden.hex
└── memsim.hex
```

## Pattern Examples

```bash
*.s                     # All .s files
unit/                   # Everything in unit/ directory
program/saxpy*         # Files matching "saxpy*" in program/
unit/*.s               # Only .s files in unit/
test.bin               # Specific file
```

## Tips

1. **Start simple:** Test one file first
   ```bash
   python3 test_cardinal.py --src assembly --truth emu addi.s
   ```

2. **Use skip-cleanup when debugging:**
   ```bash
   python3 test_cardinal.py --src assembly --truth emu addi.s --skip-cleanup
   ```

3. **Combine modes to verify:**
   ```bash
   # Test same code as assembly and binary
   python3 test_cardinal.py --src assembly --truth emu saxpy.s
   python3 test_cardinal.py --src bin --truth emu saxpy.bin
   ```

4. **Use cycle limits for new tests:**
   ```bash
   python3 test_cardinal.py --src assembly --truth emu --enable-cycle-limit --max-cycles 5000
   ```

5. **Enable debug logging to investigate issues:**
   ```bash
   # File-only debug output
   python3 test_cardinal.py --src bin --truth exp --debug-file debug.log
   
   # Debug output to both terminal and file
   python3 test_cardinal.py --src bin --truth exp --debug-file debug.log --debug-dual-output
   ```

## Thread Count Validation

⚠️ **IMPORTANT:** The test suite validates that thread counts match across:
1. **Directory structure** (e.g., `t1024` → 1024 threads)
2. **Expected file path** (e.g., `program/pixel/t1024/pixel.hex` → 1024 threads)
3. **MMIO configuration** (when TBS enabled)

**If thread counts don't match:**
- Test is marked as **FAILED**
- Error logged to `results/test_diffs/<test_name>_validation.log`
- Error message shown in console and debug output (if enabled)

**Example mismatch error:**
```
[FAIL]     pixel (Thread count validation failed)
THREAD COUNT MISMATCH: directory has 1024 threads but expected file has 512 threads
```

---

For full details, see `README_TESTS.md`
