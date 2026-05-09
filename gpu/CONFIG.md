# GPU Simulator Configuration Guide

This document provides comprehensive documentation for the GPU simulator configuration file (`config.toml`). For quick reference about specific settings, see inline comments in the TOML file.

## Table of Contents

1. [Overview](#overview)
2. [Configuration Sections](#configuration-sections)
3. [Thread Block Scheduler & MMIO](#thread-block-scheduler--mmio)
4. [Functional Units](#functional-units)
5. [Write-Back Configuration](#write-back-configuration)
6. [Performance Counter Settings](#performance-counter-settings)
7. [Example Configurations](#example-configurations)
8. [Configuration Validation](#configuration-validation)

---

## Overview

The simulator is configured using `config.toml`, a human-readable TOML file that's automatically parsed by `pydantic-settings`. All configuration values have sensible defaults to provide a working minimal configuration out of the box.

### Key Principles

- **Type Safety**: Configuration values are validated against Python type hints
- **Nested Organization**: Related settings are grouped under section headers
- **Comprehensive Documentation**: Each field includes type, range, default, and rationale
- **Flexible Validation**: Enum options are validated at load time
- **Easy Modification**: Change values without touching Python code

### Loading Configuration

```python
from config import Settings

# Load configuration from config.toml
settings = Settings.load()

# Access sections
functional_units = settings.functional_units
writeback_config = settings.writeback
perf_counters = settings.perf_counter
```

---

## Configuration Sections

### Test Suite Configuration

#### `[paths]`
File paths for tools and scripts.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `assembler_script` | str | `assembler/assembler.py` | Path to RISC-V assembler |
| `opcodes` | str | `assembler/opcodes.txt` | Opcode definitions file |
| `emulator` | str | `src/emulator/src/emulator.py` | Path to reference emulator |
| `hex_bin_converter` | str | `hex_bin_converter.py` | Hex/binary conversion tool |

#### `[directories]`
Directory structure for test organization.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `diff_dir` | str | `results/test_diffs` | Output directory for test diffs |
| `test_root_asm` | str | `tests/assembly` | Root directory for assembly tests |
| `test_root_bin` | str | `tests/bin` | Root directory for binary tests |
| `expected_dir` | str | `tests/exp` | Expected output directory |

#### `[files]`
Output file locations for test results and intermediate data.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `raw_asm_output` | str | `results/raw_instr.hex` | Raw assembler output |
| `formatted_instr` | str | `results/formatted_instr.hex` | Formatted instruction hex |
| `meminit` | str | `results/meminit.hex` | Memory initialization hex |
| `meminit_bin` | str | `results/meminit.bin` | Memory initialization binary |
| `emu_output` | str | `results/memgolden.hex` | Reference emulator output |
| `emu_temp_output` | str | `src/emulator/src/memsim.hex` | Emulator temporary file |
| `sim_output` | str | `results/memsim.hex` | Simulator output |
| `final_expected` | str | `results/final_expected_combined.hex` | Combined expected output |
| `temp_cmd_log` | str | `results/temp_command_output.txt` | Debug log file |

#### `[test_parameters]`
Default parameters for test execution.

| Field | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| `default_start_pc` | int | 0+ | 0 | Starting program counter |
| `default_threads` | int | 1-32 (power of 2) | 32 | Threads per warp/block |
| `default_blocks` | int | 1+ | 1 | Number of thread blocks |
| `format` | enum | "hex", "bin" | "hex" | Output format |
| `default_pattern` | str | glob | "*.s" | Test discovery pattern |

**Important Notes on `default_threads` and `default_blocks`:**

- `default_threads` must be derivable from `num_warps × threads_per_warp`
  - For `num_warps = 1, threads_per_warp = 32`: use `default_threads = 32`
  - For `num_warps = 32, threads_per_warp = 32`: use `default_threads = 1024`

- Thread counts can be overridden by directory structure in new test format
  - Example: `tests/bin/program/<test>/t1024/<test>.bin` specifies 1024 threads for that test
  - Thread count validation ensures directory, expected file, and MMIO values all match

### Test Directory Structure

The test suite supports both old and new directory structures:

#### New Structure (Program Tests)
Used for tests with thread counts specified in directory names:
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

**Thread count extraction:** Extracted from directory name (e.g., `t1024` → 1024 threads)

#### Old Structure (Unit Tests)
Used for tests with fixed thread configurations:
```
tests/
├── bin/unit/
│   └── <category>/
│       └── <test_name>.bin
└── exp/unit/
    └── <category>/
        └── <test_name>_exp_t<threads>_b<blocks>.hex
```

**Thread count extraction:** Parsed from expected filename (e.g., `_exp_t32_b1` → 32 threads, 1 block)

### Streaming Multiprocessor (SM) Configuration

#### `[sm]`
Streaming Multiprocessor parameters.

| Field | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| `sm_no` | int | 0+ | 0 | SM number (for multi-SM systems) |
| `num_warps` | int | 1-4 | 1 | Warps per SM |
| `num_preds` | int | 8-32 | 16 | Predicate registers |
| `threads_per_warp` | int | 32 | 32 | Threads per warp (usually fixed) |
| `enable_tbs` | bool | - | false | Enable Thread Block Scheduler |
| `kernel_base_addr` | hex | 0-4GB | 0x0 | Kernel base address |
| `tb_size` | int | 4-256 | 32 | Thread block size |

**Notes:**
- `num_warps`: Higher values mean more parallelism but more register file contention
- `enable_tbs`: Static assignment (false) vs dynamic scheduling (true)
- `tb_size`: Usually equals or is multiple of `threads_per_warp`

### Memory System Configuration

#### `[memory]`
Memory system parameters.

| Field | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| `start_pc` | hex | 0-4GB | 0x0 | Starting program counter |
| `latency` | int | 1-10 cycles | 2 | L1 cache hit latency |
| `policy` | enum | "rr" | "rr" | Arbitration policy (round-robin) |

#### `[kernel]`
Kernel execution parameters.

| Field | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| `max_kernels_per_sm` | int | 1+ | 1 | Concurrent kernels per SM |
| `kernel_id` | hex | 0-4GB | 0x20000000 | Kernel ID base address |

#### `[icache]` / `[dcache]`
Cache configuration.

| Field | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| `cache_size` | int | 8KB-64KB | 32KB | Cache size in bytes |
| `block_size` | int | 4-64 bytes | 4 | Cache line size |
| `associativity` | int | 1,2,4,8 | 1 | Set associativity |

**Typical Configurations:**
- Direct-mapped: `associativity = 1`
- 2-way associative: `associativity = 2`
- 4-way associative: `associativity = 4` (most common)

---

## Thread Block Scheduler & MMIO

### Overview

The Thread Block Scheduler (TBS) enables dynamic scheduling of thread blocks onto the SM. When enabled, kernel launch parameters are read from memory-mapped I/O (MMIO) registers in the meminit file instead of being statically configured in config.toml.

### Two Modes of Operation

#### Mode 1: Static Configuration (enable_tbs = false)

The default mode. Kernel parameters are defined in config.toml:

```toml
[sm]
enable_tbs = false
tb_size = 32

[memory]
start_pc = 0x0
```

All threads in a block execute identically with these fixed parameters.

#### Mode 2: Dynamic TBS (enable_tbs = true)

Kernel parameters are read from MMIO locations in the meminit file:

```toml
[sm]
enable_tbs = true

[mmio]
# These are fallback defaults if values not found in meminit
kernel_entry_point = 0x0
threads_per_block = 32
num_blocks = 1
total_threads = 32
kernel_args_address = 0x20000000
kernel_args_size = 0
```

### MMIO Register Layout

When TBS is enabled, kernel launch parameters must be provided in the meminit file at these addresses:

| Address | Register | Field | Width | Description |
|---------|----------|-------|-------|-------------|
| 0x0C | Kernel Entry Point | `kernel_entry_point` | 32-bit | Virtual address where kernel code starts |
| 0x10 | Block Register | `threads_per_block` | 32-bit | Number of threads per block |
| 0x14 | Grid Register | `num_blocks` | 32-bit | Number of blocks in grid |
| 0x18 | Total Threads Register | `total_threads` | 32-bit | Total threads = num_blocks × threads_per_block |
| 0x1C | Arguments Address | `kernel_args_address` | 32-bit | Virtual address of kernel arguments |
| 0x20 | Arguments Size | `kernel_args_size` | 32-bit | Bytes to load from arguments address |

See `MMIO_details.md` for complete memory map including control/status registers.

### Memory Initialization File Format

The meminit file contains instruction code and optional MMIO configuration:

```hex
0x00000000 0xXXXXXXXX    # MMIO region (for TBS, address 0x00-0x20)
0x00000004 0xXXXXXXXX
...
0x0000000C 0xAABBCCDD    # Kernel entry point (if TBS enabled)
0x00000010 0x00000020    # 32 threads per block (if TBS enabled)
0x00000014 0x00000001    # 1 block total (if TBS enabled)
0x00000018 0x00000020    # 32 total threads (if TBS enabled)
...
0x00000024 0xXXXXXXXX    # Start of instruction code
0x00000028 0xXXXXXXXX
...
```

When enable_tbs=false, MMIO data is ignored and instruction code can start at address 0x00.

### Reading MMIO from Meminit

The simulator automatically reads MMIO values when TBS is enabled:

```python
from config import get_settings

settings = get_settings()
mmio_config = settings.read_mmio_from_meminit(Path("results/meminit.hex"))

print(f"Entry point: {hex(mmio_config.kernel_entry_point)}")
print(f"Threads/block: {mmio_config.threads_per_block}")
print(f"Total threads: {mmio_config.total_threads}")
```

Fallback behavior:
- If MMIO address not found in meminit → use config.toml `[mmio]` default
- If config.toml `[mmio]` not specified → use hardcoded defaults
- If meminit file doesn't exist → error (file must exist for simulator to load)

### Configuration Precedence

When TBS is enabled, the precedence order is:

1. MMIO values from meminit file (highest priority)
2. `[mmio]` defaults from config.toml
3. Hardcoded defaults in MMIOConfig class (lowest priority)

---

## Functional Units

The GPU simulator supports configurable execution units with adjustable latencies and counts.

### Unit Types

1. **Integer Units**: ALU, multiply, divide operations
2. **Floating-Point Units**: FP ALU, multiply, divide, square root
3. **Special Units**: Trigonometric, inverse square root, conversions
4. **Memory/Branch/Jump Units**: Load/store, branches, jumps

### Configuration Structure

```toml
[functional_units]
int_unit_count = 1           # Number of integer units
fp_unit_count = 1            # Number of FP units
special_unit_count = 1       # Number of special units
membranchjump_unit_count = 1 # Number of memory units

[functional_units.int_unit]
alu_count = 1                # ALUs per integer unit
mul_count = 1                # Multipliers per unit
div_count = 1                # Dividers per unit
alu_latency = 1              # ALU operation latency
mul_latency = 2              # Multiply latency
div_latency = 17             # Divide latency
```

### Latency Guidelines

#### Integer Operations

| Operation | Typical Range | Default | Notes |
|-----------|---------------|---------|-------|
| ADD/SUB | 1-3 cycles | 1 | Can be pipelined to 1 cycle |
| AND/OR/XOR | 1-3 cycles | 1 | Same as ADD |
| MULT | 2-5 cycles | 2 | Depends on multiplier type |
| DIV | 10-20 cycles | 17 | Iterative, expensive operation |

#### Floating-Point Operations

| Operation | Typical Range | Default | Notes |
|-----------|---------------|---------|-------|
| FADD/FSUB | 1-3 cycles | 1 | Can be pipelined |
| FMUL | 4-8 cycles | 4 | More complex than integer |
| FDIV | 10-30 cycles | 24 | Very slow, avoid if possible |
| FSQRT | 15-30 cycles | 20 | Specialized hardware |

#### Special Operations

| Operation | Typical Range | Default | Notes |
|-----------|---------------|---------|-------|
| SIN/COS/TAN | 10-20 cycles | 16 | Iterative approximation |
| RSQRT | 8-15 cycles | 12 | Reciprocal square root |
| INT→FP | 1-5 cycles | 1 | Format conversion |
| FP→INT | 1-5 cycles | 1 | Format conversion |

### Unit Count Recommendations

| Scenario | Int Units | FP Units | Special | Mem/Br/Jp | Rationale |
|----------|-----------|----------|---------|-----------|-----------|
| Minimal | 1 | 1 | 1 | 1 | Baseline single-issue |
| FP-Heavy | 1 | 2 | 2 | 1 | Science/ML workloads |
| Memory-Heavy | 2 | 1 | 0 | 2 | Stream processing |
| Balanced | 2 | 2 | 1 | 2 | General purpose |
| High-Performance | 4 | 4 | 2 | 4 | GPU-class design |

### Example: FP-Heavy Configuration

```toml
[functional_units]
int_unit_count = 1
fp_unit_count = 3            # More FP units
special_unit_count = 2       # More special functions
membranchjump_unit_count = 1

[functional_units.fp_unit]
alu_count = 2                # Parallel FP operations
mul_count = 2
div_count = 1
sqrt_count = 2
```

---

## Write-Back Configuration

The write-back stage is where execution results are written back to registers.

### Buffer Organization Schemes

#### `count_scheme`: How buffers are counted

- **`buffer_per_fsu`** (default): One buffer per functional subunit
  - Fine-grained control per ALU/multiplier/divider
  - More buffers, more complex
  - Best for detailed simulation

- **`buffer_per_bank`**: One buffer per register file bank
  - Coarser granularity
  - Simpler implementation
  - Better for register file contention studies

#### `size_scheme`: Buffer sizing

- **`fixed`** (default): All buffers same size
  ```toml
  size_scheme = "fixed"
  size = 8  # All buffers: 8 entries
  ```

- **`variable`**: Per-unit customizable
  ```toml
  size_scheme = "variable"
  size = 8  # Default size
  variable_sizes = {
      "Alu_int_0": 16,
      "Mul_int_0": 8,
      "Div_int_0": 4,
  }
  ```

#### `structure`: Buffer internal organization

- **`queue`** (FIFO, default): First in, first out
  - Preserves instruction order
  - Fair scheduling
  - Better for deterministic behavior

- **`stack`** (LIFO): Last in, first out
  - May cause starvation
  - Cache-friendly for stack data
  - Rarely used

- **`circular`** (wraparound): Fixed memory wrap-around
  - Efficient memory usage
  - Complex pointer management
  - Good for real hardware

### Eviction Policies

When write-back buffer is full, determines which result gets evicted.

#### Primary Policy Options

- **`capacity_priority`** (default): Frees up space immediately
  - Evicts oldest instruction
  - Prevents write-back bottlenecks
  - Recommended for most scenarios

- **`age_priority`**: Considers instruction age
  - More fair scheduling
  - Prevents starvation
  - Good for latency studies

- **`fsu_priority`**: Uses FSU-specific priorities
  - Allows biasing toward certain units
  - Requires `fsu_priorities` table
  - Advanced configuration

#### Example: FSU Priority Configuration

```toml
[writeback.buffer_config]
primary_policy = "fsu_priority"
secondary_policy = "age_priority"

fsu_priorities = {
    "Alu_int_0": 3,      # Critical operations, high priority
    "Mul_int_0": 2,      # Medium priority
    "Div_int_0": 1,      # Low priority (long-running)
}
```

### Register File Configuration

#### `[register_file]`

| Field | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| `num_banks` | int | 1-8 | 4 | Independent RF banks |

**Bank Count Guidance:**
- **1 bank**: Simple, single write port (bottleneck)
- **2-4 banks**: Typical GPU configuration
- **8 banks**: High-bandwidth, complex arbitration
- **Rule of thumb**: Match or exceed functional unit count

#### `[predicate_register_file]`

| Field | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| `num_banks` | int | 1-4 | 2 | Independent predicate RF banks |

**Notes:**
- Predicate registers smaller than general registers
- Usually fewer banks needed
- Used for conditional execution masks

---

## Performance Counter Settings

#### `[perf_counter]`
Performance monitoring and telemetry.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | true | Enable performance counter collection |
| `trace_enabled` | bool | false | Enable detailed instruction tracing |
| `trace_start_cycle` | int | 0 | Cycle to start tracing |
| `trace_end_cycle` | int | 0 | Cycle to stop (0 = until end) |
| `output_dir` | string | `results/perf_data` | Output directory for metrics |
| `summary_only` | bool | true | Write only summaries (faster) |
| `enabled_units` | array | [] | Units to monitor ([] = all) |
| `buffer_limit` | int | 100000 | Event buffer size |
| `flight_recorder_enabled` | bool | false | Enable circular trace buffer |

### Enabling Trace for Debugging

```toml
[perf_counter]
trace_enabled = true
trace_start_cycle = 0
trace_end_cycle = 1000          # Trace first 1000 cycles
summary_only = false            # Write all events
buffer_limit = 1000000          # Larger buffer for trace
flight_recorder_enabled = false
```

### Selective Unit Monitoring

```toml
[perf_counter]
enabled_units = ["Alu_int_0", "Mul_int_0"]  # Monitor only these units
```

---

## Example Configurations

### Minimal Configuration (Default)

Smallest working configuration with 1 unit of each type:

```toml
[functional_units]
int_unit_count = 1
fp_unit_count = 1
special_unit_count = 1
membranchjump_unit_count = 1

[functional_units.int_unit]
alu_count = 1
mul_count = 1
div_count = 1
alu_latency = 1
mul_latency = 2
div_latency = 17

# ... other sections with defaults
```

**Use Case:** Testing, baseline measurements

### Floating-Point Intensive (ML/Science)

```toml
[functional_units]
int_unit_count = 1
fp_unit_count = 3      # More FP units
special_unit_count = 2
membranchjump_unit_count = 1

[functional_units.fp_unit]
alu_count = 2
mul_count = 2
div_count = 1
sqrt_count = 1

[register_file]
num_banks = 8          # High-bandwidth RF
```

**Use Case:** ML inference, scientific computing

### Memory-Intensive (Streaming)

```toml
[functional_units]
int_unit_count = 2
fp_unit_count = 1
special_unit_count = 0
membranchjump_unit_count = 4  # Many load/store units

[functional_units.membranchjump_unit]
ldst_count = 4
ldst_queue_size = 16   # Large queue for prefetch
```

**Use Case:** Stream processing, data parallel workloads

### High-Performance (GPU-class)

```toml
[functional_units]
int_unit_count = 4
fp_unit_count = 4
special_unit_count = 2
membranchjump_unit_count = 2

[register_file]
num_banks = 8

[writeback.buffer_config]
size = 16              # Larger write-back buffers
```

**Use Case:** Detailed performance modeling, architecture research

---

## Configuration Validation

### Using Python Script

```python
from config import Settings

# Load and validate configuration
try:
    settings = Settings.load()
    print("✓ Configuration valid!")
except Exception as e:
    print(f"✗ Configuration error: {e}")
```

### Using Taplo (TOML Linter)

```bash
# Check TOML syntax
taplo lint config.toml

# Format TOML file
taplo format config.toml

# Format with inline comments preserved
taplo format --check config.toml
```

### Validation Rules

1. **Type Checking**: All values must match declared types
2. **Range Validation**: Integer values in specified ranges
3. **Enum Validation**: String values in allowed enum options
4. **Required Fields**: Certain fields have no defaults
5. **Consistency**: Related fields validated together

### Common Validation Errors

**Error**: `Field 'int_unit_count' must be >= 1`
- **Fix**: Ensure unit counts are at least 1

**Error**: `'invalid_option' is not a valid WritebackBufferStructure`
- **Fix**: Use only: "queue", "stack", or "circular"

**Error**: `Field 'num_banks' must be <= 8`
- **Fix**: Reduce bank count to 8 or less

---

## Best Practices

### Configuration Management

1. **Version Control**: Keep config.toml in version control
2. **Documentation**: Document custom configurations with comments
3. **Testing**: Validate configuration before deployment
4. **Staging**: Use different configs for dev/test/production

### Performance Tuning

1. **Start Simple**: Begin with minimal configuration
2. **Measure**: Collect performance data before changing
3. **One Change**: Modify one parameter at a time
4. **Document**: Note why each change was made

### Common Adjustments

**For Faster Simulation:**
```toml
summary_only = true          # Skip detailed traces
trace_enabled = false        # Disable tracing
buffer_limit = 50000         # Smaller buffers
```

**For Detailed Analysis:**
```toml
trace_enabled = true
trace_start_cycle = 0
trace_end_cycle = 10000
summary_only = false
flight_recorder_enabled = true
```

**For Balanced Configuration:**
```toml
[functional_units]
int_unit_count = 2
fp_unit_count = 2
membranchjump_unit_count = 2

[register_file]
num_banks = 4

[writeback.buffer_config]
size = 8
```

---

## See Also

- `config.toml` - Actual configuration file with inline comments
- `config.py` - Pydantic models defining configuration structure
- `src/simulator/sm.py` - Code loading and using configuration

---

**Last Updated**: 2026-04-13  
**Version**: 1.0
