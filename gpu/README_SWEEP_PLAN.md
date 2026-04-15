# GPU Sweep Plan

## Assumptions
- Requested `i$ 65KB (512 * 1024)` is interpreted here as `64 KiB = 65536 bytes` because the simulator knob is byte-sized and 65536 is the nearest standard capacity.
- D$ line size stays fixed at 32 words x 4 bytes = 128 bytes, matching the current baseline.
- For D$ geometries, `num_sets_per_bank` is derived as `cache_size / (num_banks * num_ways * 128)`.
- Phase B/C configs are staged off prior winners; update the anchor comments before running those phases.

## Run Order
1. Phase A: run `gpu/sweep_cases_phase_a.toml` against the target workloads.
2. Select one D$ winner using cycle count as the primary metric and perf counters as tie-breakers.
3. If the winner is not `16KB 4B4W`, update the D$ fields in `gpu/config/sweeps/phase_b_*.toml` and `gpu/config/sweeps/phase_c_*.toml`.
4. Phase B: run `gpu/sweep_cases_phase_b.toml`.
5. For each scheduler family (`RR`, `GTO`), note whether the LD/ST queue winner differs. If one queue depth dominates both, keep that depth fixed for Phase C. Otherwise, keep the scheduler-specific queue depth in the corresponding phase C configs.
6. Phase C: run `gpu/sweep_cases_phase_c.toml` and choose the smallest I$ capacity that does not cause an unacceptable regression.

## Recommended Evaluation Scheme
- Workloads: run each phase on `program/pixel/` and `program/triangle/`. Add `program/vertex/` only after a `t1024` binary exists.
- Metric order:
  1. total cycles
  2. completion/pass rate
  3. D$/I$ miss behavior from perf counters
  4. LD/ST backpressure / queue occupancy indicators
- Tie-break policy:
  - Prefer lower cycles.
  - If cycles are within ~1-2%, prefer the smaller cache or smaller queue.
  - For scheduler ties, prefer `RR` unless `GTO` shows a clear repeatable win.

## Commands
```bash
python3.11 gpu/test_cardinal.py --sweep --sweep-config gpu/sweep_cases_phase_a.toml --src bin --sweep-inputs program/pixel/ program/triangle/
python3.11 gpu/test_cardinal.py --sweep --sweep-config gpu/sweep_cases_phase_b.toml --src bin --sweep-inputs program/pixel/ program/triangle/
python3.11 gpu/test_cardinal.py --sweep --sweep-config gpu/sweep_cases_phase_c.toml --src bin --sweep-inputs program/pixel/ program/triangle/
```
