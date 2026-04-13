#!/usr/bin/env python3
"""
Configuration validation script for GPU simulator.

This script validates the config.toml file against the pydantic schema
and provides detailed information about the loaded configuration.

Usage:
    python3 validate_config.py          # Validate config.toml
    python3 validate_config.py --schema # Print JSON schema
    python3 validate_config.py --verbose # Detailed output
"""

import json
import sys
from pathlib import Path

try:
    from config import Settings
except ImportError:
    print("Error: Could not import config module. Make sure you're in the project root.")
    sys.exit(1)


def print_header(text):
    """Print a formatted header."""
    print(f"\n{'=' * 80}")
    print(f"  {text}")
    print(f"{'=' * 80}\n")


def print_section(text):
    """Print a formatted section header."""
    print(f"\n{text}")
    print("-" * len(text))


def validate_config(verbose=False):
    """Validate configuration and print results."""
    print_header("GPU SIMULATOR CONFIGURATION VALIDATION")

    try:
        settings = Settings.load()
        print("✓ Configuration loaded successfully!")

        if verbose:
            print("\n[SUMMARY]")
            print(f"Functional Units:")
            print(f"  - Integer units: {settings.functional_units.int_unit_count}")
            print(f"  - FP units: {settings.functional_units.fp_unit_count}")
            print(f"  - Special units: {settings.functional_units.special_unit_count}")
            print(f"  - Memory/Branch/Jump units: {settings.functional_units.membranchjump_unit_count}")

            print(f"\nInteger Unit Config:")
            print(f"  - ALU count: {settings.functional_units.int_unit.alu_count}")
            print(f"  - Multiplier count: {settings.functional_units.int_unit.mul_count}")
            print(f"  - Divider count: {settings.functional_units.int_unit.div_count}")
            print(f"  - ALU latency: {settings.functional_units.int_unit.alu_latency} cycles")
            print(f"  - Multiply latency: {settings.functional_units.int_unit.mul_latency} cycles")
            print(f"  - Divide latency: {settings.functional_units.int_unit.div_latency} cycles")

            print(f"\nFloating-Point Unit Config:")
            print(f"  - ALU count: {settings.functional_units.fp_unit.alu_count}")
            print(f"  - Multiplier count: {settings.functional_units.fp_unit.mul_count}")
            print(f"  - Divider count: {settings.functional_units.fp_unit.div_count}")
            print(f"  - Square root count: {settings.functional_units.fp_unit.sqrt_count}")

            print(f"\nWrite-Back Configuration:")
            print(f"  - Count scheme: {settings.writeback.buffer_config.count_scheme.value}")
            print(f"  - Size scheme: {settings.writeback.buffer_config.size_scheme.value}")
            print(f"  - Structure: {settings.writeback.buffer_config.structure.value}")
            print(f"  - Primary policy: {settings.writeback.buffer_config.primary_policy.value}")
            print(f"  - Buffer size: {settings.writeback.buffer_config.size}")

            print(f"\nRegister File:")
            print(f"  - General RF banks: {settings.register_file.num_banks}")
            print(f"  - Predicate RF banks: {settings.predicate_register_file.num_banks}")

            print(f"\nStreaming Multiprocessor:")
            print(f"  - Warps: {settings.sm.num_warps}")
            print(f"  - Predicate registers: {settings.sm.num_preds}")
            print(f"  - Threads per warp: {settings.sm.threads_per_warp}")
            print(f"  - TBS enabled: {settings.sm.enable_tbs}")

            print(f"\nPerformance Counters:")
            print(f"  - Enabled: {settings.perf_counter.enabled}")
            print(f"  - Trace enabled: {settings.perf_counter.trace_enabled}")
            print(f"  - Output directory: {settings.perf_counter.output_dir}")
            print(f"  - Summary only: {settings.perf_counter.summary_only}")

        print("\n" + "=" * 80)
        print("✓ VALIDATION PASSED - Configuration is valid and ready to use")
        print("=" * 80 + "\n")
        return True

    except Exception as e:
        print_header("VALIDATION FAILED")
        print(f"✗ Configuration error:\n\n{e}\n")
        print("=" * 80)
        print("\nTips for fixing configuration errors:")
        print("  1. Check config.toml syntax (use 'taplo lint config.toml')")
        print("  2. Review CONFIG.md for valid options")
        print("  3. Ensure all required fields are present")
        print("  4. Check field types match documented types")
        print("  5. Verify enum values match exactly (case-sensitive)")
        print("\n" + "=" * 80 + "\n")
        return False


def print_schema():
    """Print JSON schema for configuration."""
    print_header("CONFIGURATION SCHEMA")

    try:
        schema = Settings.model_json_schema()
        print(json.dumps(schema, indent=2))
    except Exception as e:
        print(f"Error generating schema: {e}")
        return False

    return True


def print_config_sample():
    """Print a sample valid configuration."""
    print_header("SAMPLE CONFIGURATION (TOML)")

    sample = """
# Minimal valid configuration example

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

[functional_units.fp_unit]
alu_count = 1
mul_count = 1
div_count = 1
sqrt_count = 1
alu_latency = 1
mul_latency = 4
div_latency = 24
sqrt_latency = 20

[functional_units.special_unit]
trig_count = 1
inv_sqrt_count = 1
conv_count = 1
trig_latency = 16
inv_sqrt_latency = 12
conv_latency = 1

[functional_units.membranchjump_unit]
ldst_count = 1
branch_count = 1
jump_count = 1
ldst_buffer_size = 1
ldst_queue_size = 4

[writeback]
[writeback.buffer_config]
count_scheme = "buffer_per_fsu"
size_scheme = "fixed"
structure = "queue"
primary_policy = "capacity_priority"
secondary_policy = "age_priority"
size = 8

[register_file]
num_banks = 4

[predicate_register_file]
num_banks = 2
"""
    print(sample)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate GPU simulator configuration"
    )
    parser.add_argument(
        "--schema",
        action="store_true",
        help="Print JSON schema for configuration"
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Print sample valid configuration"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed configuration summary"
    )

    args = parser.parse_args()

    if args.schema:
        return 0 if print_schema() else 1

    if args.sample:
        print_config_sample()
        return 0

    return 0 if validate_config(verbose=args.verbose) else 1


if __name__ == "__main__":
    sys.exit(main())
