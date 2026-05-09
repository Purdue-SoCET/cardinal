# GPU Sweep Cases

`sweep_cases.toml` defines the list of simulator configurations to run in sweep mode.

## Command

Run a sweep with:

```bash
python3 test_cardinal.py --sweep --sweep-config sweep_cases.toml --src bin --sweep-inputs unit/
```

You can provide more than one input pattern:

```bash
python3 test_cardinal.py --sweep --sweep-config sweep_cases.toml --src bin --sweep-inputs unit/ program/pixel/
```

## File Format

Each case points to a real config file:

```toml
output_root = "results/sweeps"

[[cases]]
id = "baseline"
config = "configs/sweeps/baseline.toml"

[[cases]]
id = "ldst_q8"
config = "configs/sweeps/ldst_q8.toml"
```

## Fields

- `output_root`: Root directory for sweep outputs.
- `[[cases]]`: One sweep case entry.
- `id`: Short name for the case. Used in output directory names.
- `config`: Path to the case's standalone `config.toml`. Relative paths are resolved from the directory containing `sweep_cases.toml`.

## Output Layout

Sweep results are written under:

```text
results/sweeps/<test_name>/<case_id>/
```

Typical outputs per case:

- `memsim.hex`
- simulator log
- performance counter outputs
- sweep summary row in `results/sweeps/summary.csv`

## Workflow

1. Copy `gpu/config.toml` to create a case config.
2. Edit only the knobs you want to vary in that case.
3. Add a `[[cases]]` entry in `sweep_cases.toml`.
4. Run `test_cardinal.py` in sweep mode.

## Example

If you want to compare two LDST queue sizes, create two case configs and list both:

```toml
[[cases]]
id = "ldst_q4"
config = "configs/sweeps/ldst_q4.toml"

[[cases]]
id = "ldst_q8"
config = "configs/sweeps/ldst_q8.toml"
```
