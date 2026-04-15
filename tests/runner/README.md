# GPU Testing Framework: JSON Configuration Guide

This document outlines the complete schema for the suite.json configuration files used by the test runner. The runner strictly enforces these parameters and their types.

## Root Level (TestSuite)

The root of the JSON file must be an object defining the overarching suite.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `suite_name` | String | No | The human-readable name of the test suite. Defaults to "Unnamed Suite". |
| `shared_config` | Object | No | Defines global defaults for different pipeline stage types. See **SharedConfig**. |
| `tests` | Array of Objects | **Yes** | A list of individual test cases to execute. See **TestCase**. |

## Shared Configuration (SharedConfig)

Used to prevent repetition. Values defined here are automatically inherited by any pipeline stage of the matching type, unless that stage explicitly overrides them.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `c_source` | Object | No | Contains defaults for C compilation. Accepts `source` (String) and `compiler_flags` (String). |
| `asm_source` | Object | No | Contains defaults for Assembly. Accepts `source` (String) and `compiler_flags` (String). |

## Test Case (TestCase)

Represents a single scenario consisting of an execution pipeline and an optional verification step.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `name` | String | No | The name of the specific test case. Defaults to "Unnamed Test". |
| `pipeline` | Array of Objects | **Yes** | A sequential list of execution stages. Must contain at least one stage. See **PipelineStage**. |
| `verification` | Object | No | Defines how to validate the final memory state. See **VerificationConfig**. |

## Pipeline Stage (PipelineStage)

A single step in the execution chain. The required parameters depend on the type of the stage.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `type` | String | **Yes** | Must be exactly one of: `"script"`, `"c_source"`, or `"asm_source"`. |
| `name` | String | No | Label for the stage in console output. |
| `source` | String | Conditional | The path to the .c or .s file. Required for c_source and asm_source unless inherited from shared_config. |
| `command` | String | Conditional | The terminal command to execute. **Required** if type is `"script"`. |
| `compiler_flags` | String | No | Arguments passed to the twig compiler (e.g., `"-O2 --freestanding"`). |
| `execution` | Object | No | Defines emulator parameters. Only applicable to C and ASM stages. See **ExecutionConfig**. |

## Execution Configuration (ExecutionConfig)

Dictates how the emulator runs the compiled hardware instructions and how it handles memory dependencies between pipeline stages.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `threads` | Integer | No | Number of threads to simulate. Must be > 0. Defaults to 32. |
| `blocks` | Integer | No | Number of thread blocks to simulate. Must be > 0. Defaults to 1. |
| `consumes` | Array of Strings | No | A list of .hex filenames to append to the instructions before running the emulator. Used to pass data from a previous stage into this stage. |
| `produces_mem` | String | No | A filename to save the emulator's final memory state into upon completion. This file can then be consumed by the next stage. |

## Verification Configuration (VerificationConfig)

If included, the runner will compare the emulator's final memory output against a golden reference file.

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `expected_file` | String | **Yes** | The path to the golden reference .hex file. |
| `check_start` | String | No | The starting hex address for the diff (e.g., `"0x40000000"`). Highly recommended for C code to ignore stack garbage. |
| `check_end` | String | No | The ending hex address for the diff. If omitted, the verifier checks from check_start to the end of the file. |

---

## Complete Example Schema

```json
{
  "suite_name": "Graphics Pipeline Integration",
  "shared_config": {
    "c_source": {
      "source": "benchmark/kernels/vertex_shader.c",
      "compiler_flags": "-O2 -Ibenchmark/kernels/include"
    }
  },
  "tests": [
    {
      "name": "Integration Test - Standard Resolution",
      "pipeline": [
        {
          "type": "script",
          "name": "Generate Geometry",
          "command": "python3 tools/gen_geo.py --res 1024 --out geo.hex"
        },
        {
          "type": "c_source",
          "name": "Vertex Processing",
          "execution": {
            "threads": 1024,
            "blocks": 4,
            "consumes": ["geo.hex"],
            "produces_mem": "stage1_out.hex"
          }
        },
        {
          "type": "asm_source",
          "name": "Hardware Rasterization (Mock)",
          "source": "tests/mocks/rasterizer.s",
          "execution": {
            "threads": 32,
            "blocks": 1,
            "consumes": ["stage1_out.hex"]
          }
        }
      ],
      "verification": {
        "expected_file": "golden_framebuffer.hex",
        "check_start": "0x80000000",
        "check_end": "0x80100000"
      }
    }
  ]
}