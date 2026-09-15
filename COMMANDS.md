# Simulator command reference

Scope: `gpu/src/simulator` and its direct tooling. Architecture, constraints and
documentation audit are in [AGENTS.md](AGENTS.md). These instructions do not grant
permission to edit implementation/configuration/tests or regenerate expected data.

## Status and environment

- **Verified**: successfully executed, or behavior directly confirmed by source;
  the entry states which. Syntax-only checks do not establish runtime correctness.
- **Discovered**: present in repository tooling/docs, or uses source-confirmed CLI
  options with an existing input; not successfully executed end to end.
- **Unverified**: plausible optional invocation without successful confirmation;
  kept outside the recommended run workflow.

Inspection baseline: 2026-09-13–14, commit `dfda013`, Python **3.12.3** on WSL/Linux.
The repository virtual environment at `venv/` now imports the declared runtime
dependencies (`bitstring`, `pandas`, `aenum`, `pydantic_settings`, `toml`, and
`polars`). pytest, Pyright and Ruff are absent. The emulator submodule was not
initialized; `gpu/src/emulator/src/emulator.py` is still missing.

Actual attempts from `gpu/`:

| Command | Result |
| --- | --- |
| `python3 -B test_cardinal.py --help` | Failed before argument parsing under the system interpreter: `ModuleNotFoundError: No module named 'toml'`. |
| `python3 -B validate_config.py --help` | Failed under the system interpreter while importing config. |
| `venv/bin/python -B -c 'import bitstring, pandas, aenum, pydantic_settings, toml, polars'` | **Verified**: all declared runtime dependencies import successfully. |

The login shell also printed a nonfatal pyenv rehash permission warning. The
system-interpreter import failures remain relevant when `python3` is used without
the virtual environment. A simulator execution was subsequently verified with
`../venv/bin/python`; no lint check or native build was run.

## Navigation and inspection

Run from repository root. **Verified — executed**, unless otherwise noted:

```bash
git status --short
git rev-parse --short HEAD
rg --files gpu/src/simulator
rg -n 'def tick|def compute|LatchIF|ForwardingIF' gpu/src/simulator
rg -n 'range\(32\)|length=32|num_iBuffer|num_entries|warp_id.*(%|//)' gpu/src/simulator
```

The first command establishes user changes; the searches locate stage order,
interfaces and coupled dimensions. A literal match is a lead to inspect, not
proof that it should become configurable.

**Discovered — source paths confirmed:**

```bash
cd gpu
```

Use `gpu/` for the Python commands below unless stated otherwise. Configured
relative file paths resolve against `gpu/config.py`'s directory, while several
runner outputs and memory's exit dump resolve against CWD. Mixing root and
`gpu/` invocation splits artifacts across directories.

## Setup / simulator build

This is Python source packaged with setuptools in [gpu/pyproject.toml](gpu/pyproject.toml).
There is no native simulator build target or simulator Make/CMake workflow.
Editable installation is the discovered setup flow; no C++ port work is underway.

**Discovered — extracted from [setup_dev_env.sh](setup_dev_env.sh), not executed.**
From repository root, when environment setup is wanted:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e gpu/
```

This writes a virtual environment/install metadata and downloads dependencies.
Use an interpreter that supports `match` (at least 3.10); package metadata's
`>=3.8` understates the source syntax requirement. Dependency-version compatibility
has not been established. The runner invokes subprocesses named `python3`, so
ensure the activated environment also supplies that executable.

For emulator comparisons only, the setup script also contains:

```bash
git submodule update --init --recursive
```

**Discovered — not executed.** Run at root; this populates `gpu/src/emulator` from
the SSH remote in `.gitmodules` and requires network/repository access. The root
`emulator/` directory is not this reference ISS. `--truth exp` uses checked-in
expected files and avoids the ISS dependency.

Do not run the entire setup script merely to inspect the repo: it can prompt to
delete/recreate an existing `venv`, upgrades pip, installs packages and initializes
submodules. No setup or cleanup was performed for this documentation task.

## Read-only syntax and configuration checks

**Verified — executed successfully at root.** This parses source without importing
the simulator, emitting bytecode or writing artifacts:

```bash
python3 -B - <<'PY'
import ast
from pathlib import Path

roots = [Path('gpu/src/simulator'), Path('gpu/src/common')]
files = sorted(p for root in roots for p in root.rglob('*.py'))
files += [Path('gpu') / name for name in (
    'config.py', 'test_cardinal.py', 'validate_config.py',
    'hex_bin_converter.py', 'parquet_to_csv.py',
)]
for path in files:
    ast.parse(path.read_text(), filename=str(path))
print(f'Parsed {len(files)} Python files')
PY
```

Result: **58 files parsed**. This does not check imports, types, stage contracts
or outputs. It intentionally excludes deprecated tests and unrelated systems.

**Verified — executed successfully at root.** Python 3.11+ standard-library TOML
syntax and sweep-path check; no Pydantic or simulation:

```bash
python3 -B - <<'PY'
from pathlib import Path
import tomllib

files = sorted(Path('gpu').rglob('*.toml'))
for path in files:
    tomllib.loads(path.read_text())
print(f'Parsed {len(files)} TOML files')
for path in sorted(Path('gpu').glob('sweep_cases*.toml')):
    spec = tomllib.loads(path.read_text())
    missing = [case['config'] for case in spec['cases']
               if not (path.parent / case['config']).is_file()]
    print(path, 'missing configs:', missing)
PY
```

Result: **40 TOML files parsed**. `sweep_cases.toml` references three missing
files (`baseline.toml`, `dcache_hitlat4.toml`, `dcache_hitlat8.toml` under
`config/sweeps/`). Phase A/B/C resolve all **9/6/6** case files. Syntax success
does not mean those settings describe a supported architecture.

After dependencies are available, from `gpu/`:

```bash
python3 -B validate_config.py --verbose
python3 -B validate_config.py --schema
python3 -B test_cardinal.py --help
```

**Discovered — implemented in the scripts; no successful runtime execution.**
Validation loads default `gpu/config.toml`; the validator has no `--config` flag.
`--schema` displays the Settings schema. Neither checks all geometric constraints,
configuration consumers, opcode support, or ability to complete a kernel.

## Simulator execution and targeted tests

The main invocation is `test_cardinal.py --src {assembly,bin} --truth {emu,exp}
[pattern]`. There is no separate simulator executable. `.bin` fixtures are addressed
text words, not raw byte binaries; TBS requires a launch header in the first nine
physical lines. See AGENTS for the exact layout.

**Verified — executed successfully through simulation, but correctness failed.**
This bounded program test from `gpu/` uses the installed virtual environment and
avoids the unavailable emulator:

```bash
../venv/bin/python -u -B test_cardinal.py --src bin --truth exp \
  'program/vertex/t32/vertex.bin' \
  --enable-cycle-limit --max-cycles 100000 --skip-cleanup
```

The vertex image has a 32-thread launch header, an expected hex file in the
matching `tests/exp/program/vertex/t32/` directory, and `program_config.toml`
with its comparison range. Observed result on 2026-09-14: execution completed in
76,325 cycles (about 41 seconds), but 152 of 401 compared words differed; 249
matched, with no address-set differences. The cycle bound is a guard, not an
expected runtime. The run used a fresh temporary output directory; evidence is
`/tmp/cardinal-vertex-03vwf_dh/`.
The checked-in config already enables TBS. Do not disable it: current completion
paths require the TBS object and forwarding connection.

Useful options (**Discovered** in `test_cardinal.py`):

| Option | Meaning / caveat |
| --- | --- |
| `--config PATH` | Select a complete settings TOML. Relative configured file paths still resolve from `gpu/`, not the custom file's location. Do not edit/create configs during documentation-only work. |
| `--enable-cycle-limit --max-cycles N` | Both are needed; default maximum is 100000 only when enabled. Does not bound initialization or external tools, and reaching the limit is not reliable failure in every mode. |
| `--skip-cleanup` | Retain end-of-run intermediates. Runner construction still deletes existing files in configured `diff_dir`. Preserve wanted artifacts before running. |
| `--src assembly` | Runs assembler and formatting/conversion before simulation. Raw assembled instructions do not by themselves supply a TBS header. |
| `--truth emu` | Runs the reference emulator then compares outputs; requires the missing submodule and its dependencies. |
| `--truth exp` | Uses expected hex fixtures, sometimes filtered to program-config address ranges. Normal mode can count a missing expected file as success after SKIP. |

Patterns are relative to `tests/bin` or `tests/assembly`, not arbitrary input
paths. Quote wildcard patterns to prevent shell expansion. Supply an explicit
pattern for binary runs: checked-in `default_pattern="*.s"` can otherwise become
`*.s.bin`. A directory pattern can include non-binary files such as
`program_config.toml`; prefer an exact `.bin` or a pattern ending in `.bin`.

The old guide recommends unit binaries and saxpy assembly against the emulator;
these are not established working workflows here. In particular, inspected
`tests/bin/unit/i_type/addi.bin` begins with instructions, not a launch header.
Do not run all unit files with TBS enabled or assume disabling TBS repairs this.
Inspect the input/expected/config relationship first.

For an honest result, inspect the simulator log for completion/exceptions/limit
warnings, verify an expected file was actually compared, and record the compared
range. A current completion baseline is 76,325 cycles for the vertex case, but
its output comparison failed. `run_simulator()` returns true after cycle-limit exits; normal
binary/expected mode ignores its return value. A PASS line or exit zero alone
is insufficient; the current completion baseline and comparison result are recorded above.

## Sweeps / broader characterization

**Discovered — runnable CLI shape and phase manifest paths confirmed, not executed.**
From `gpu/`, when a baseline program completes and broader evaluation is wanted:

```bash
python3 -B test_cardinal.py --sweep --sweep-config sweep_cases_phase_a.toml \
  --src bin --truth exp --sweep-inputs 'program/pixel/t1024/pixel.bin' \
  --enable-cycle-limit --max-cycles 100000 --skip-cleanup
```

This runs nine phase-A cases on the named 1024-thread image. The runner writes
case config copies, memory output, logs, telemetry and a summary CSV beneath the
manifest's `output_root`. Relative case/config output-root paths resolve from the
manifest directory. Phase B/C manifests exist but their winner assumptions have
not been validated. The default `sweep_cases.toml` is unsuitable until its missing
case references are resolved in an authorized task.

Sweep PASS requires completion; `--truth exp` additionally requests correctness.
Omitting `--truth` measures completion/performance only. Sweep outputs use test
stems and case IDs, so do not mix identically named inputs or concurrent runs in
the same tree. Workload costs and sufficient cycle limits remain unmeasured.

## Debugging, logs, and tracing

The runner captures simulator stdout to
`results/debug/<stem>.<extension>_simulator.log` by default, even without a debug
flag. For the vertex command above this is `vertex.bin_simulator.log`.

**Discovered — CLI confirmed, not run:** append the desired options to a targeted
invocation:

```text
--debug-file vertex_runner.log --debug-dual-output
--enable-simulator-output --simulator-output-file vertex_simulator.log
```

The first pair records harness diagnostics; the second displays/captures simulator
prints. Paths are under `results/debug/` for ordinary runs. Existing logs can be
large: stage print calls are extensive. RF/PRF/CSR/scheduler `dump()` and D-cache
`dump_stats()` methods are available for an authorized debugging harness.

Telemetry is configured in `[perf_counter]`, not by CLI trace flags. The normal
runner overrides output directory/prefix per test, typically
`results/perf_data/vertex.bin/vertex.bin_perf_summary.parquet`. Range tracing
requires `summary_only=false`, `trace_enabled=true` and a useful start/end range;
`(0,0)` disables traces. Actual unit names include `Alu_int_0`, `ICache_Stage`,
`dCache`. `flight_recorder_enabled` alone is not integrated in SM. Even disabled
mode currently retains enabled counters; see AGENTS before interpreting it.

**Discovered — existing conversion script, not executed:** from `gpu/`, after the
named summary exists:

```bash
python3 -B parquet_to_csv.py \
  results/perf_data/vertex.bin/vertex.bin_perf_summary.parquet
```

Writes a sibling `.csv`; an optional second argument selects an output file.
Requires Polars. Trace finalization combines `traces_part_*.parquet` into
`traces.parquet` and deletes the part files. `SM.finalize()` catches export errors,
so check artifacts rather than assuming simulation success proves trace export.

The existing `hex_bin_converter.py` documents `h2b input.hex output.bin` and
`b2h input.bin output.hex` (**Discovered**, not run). It writes output and can skip
malformed rows with warnings; do not use it to overwrite golden fixtures during
inspection. Memory also writes CWD `memsim.hex` automatically at process exit.

## Static analysis and legacy tests

**Unverified — optional, outside the recommended runtime workflow:**

```bash
pyright --project pyproject.toml
```

Run from `gpu/` if Pyright is separately installed. The project has
`[tool.pyright]` with `include=["src"]`, `extraPaths=["src"]`, basic checking;
there is no pinned/installed checker or observed passing baseline.

No supported pytest/unittest suite command or simulator lint CI target was found.
The sole discovered GitHub workflow builds/deploys mdBook. Python stage tests
reside under `tests/python/deprecated`; sampled issue/WB harnesses import the
missing `simulator.latch_forward_stage`. Inspect individual tests before selecting
one; a generic `pytest` run is not a documented verification workflow.

## Clean / rebuild

**Discovered — destructive behavior directly confirmed in runner source; not run:**

```bash
python3 -B test_cardinal.py --clean
```

From `gpu/`, removes the **parent of configured `diff_dir` recursively** (normally
`gpu/results`), not merely one test's files. It can remove evidence from prior
runs and should be used only when those artifacts are intentionally disposable.
`--clean` may also be combined with a test invocation. It is unnecessary for
documentation inspection and was not executed.

There is no native simulator rebuild command. Editable installs use the current
Python source; environment reinstall and configuration changes are separate from
result cleanup. Do not use broad deletion/reset commands as a substitute for
understanding the runner's paths.
