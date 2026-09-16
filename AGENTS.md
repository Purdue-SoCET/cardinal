# Repository guidance

## Focus, phase, and authorization

The primary area of active development is **`gpu/src/simulator`**. Inspect
`gpu/config.py`, `gpu/config.toml`, `gpu/test_cardinal.py`, `gpu/src/common`,
the assembler, fixtures, and emulator integration when they directly support
understanding or verifying the simulator. Keep unrelated repository work out of scope.

The current phase is **architecture understanding and characterization**.
Understanding existing behavior takes priority over refactoring. Priorities are:

1. Understand the simulator and its execution order.
2. Characterize each stage, its state, and its interfaces.
3. Identify hard-coded assumptions and all their consumers.
4. Parameterize stages incrementally, when authorized.
5. Make interfaces and assumptions explicit where needed.
6. Eventually prepare for a C++ port; the port is future work.

Development rules:

- **Never overwrite, edit, or remove user-authored comments.** Preserve their
  exact text; add any explanation as a separate comment.
- **Do not modify simulator source or other implementation code without explicit
  user permission.** The reconnaissance task authorizes only `AGENTS.md` and
  `COMMANDS.md`. It does not authorize configuration, build, test, or fixture edits.
  Findings and proposed changes below are not permission to implement them.
- Inspect before editing; verify claims against executable statements, not just
  comments, documentation, annotations, or configuration field names.
- Preserve behavior unless a behavioral change is explicitly requested. Timing,
  arbitration, completion, numerical results, and output formats are behavior.
- Prefer small, reviewable changes. Separate cleanup/refactoring from functional
  changes. Do not fix incidental bugs during an unrelated task.
- Trace both data and control interfaces before changing a stage. Before
  parameterization, identify every consumer of a dimension, value, or assumption,
  including telemetry, test inputs, and result comparison.
- Do not introduce abstractions solely for a hypothetical C++ port. Record
  portability concerns while retaining an accurate model of the Python code.
- State uncertainty explicitly. A parsed TOML field is not proof of a supported
  configuration, and a passing harness summary is not sufficient evidence alone.
- Inspect the working tree before and after work. Preserve user changes and
  existing results; the runner has destructive artifact cleanup behavior.

## Evidence and reading map

This characterization was made on 2026-09-13–14 against commit `dfda013`.
Source observations were inspected, and a bounded vertex execution was run on
2026-09-14 with the newly installed virtual environment. See [COMMANDS.md](COMMANDS.md)
for command provenance, output evidence, environment limitations, setup, and verification.

Start with [SM construction and tick](gpu/src/simulator/sm.py), then
[interfaces](gpu/src/simulator/interfaces.py),
[Instruction](gpu/src/simulator/instruction.py), and
[the runner](gpu/test_cardinal.py). `Stage` is a light base class, not a central
event scheduler. There is no simulator native-code build or standalone SM CLI.
`test_cardinal.py` imports `SM` and drives it in-process.

Useful supporting boundaries:

- [Settings](gpu/config.py) and [checked-in configuration](gpu/config.toml):
  Pydantic settings, TOML loading, adapters, paths, and test options.
- [Shared opcode enums](gpu/src/common/custom_enums_multi.py): the enum families
  used by decode and execution. The other enum file is not interchangeable by
  assumption. The local ISA CSV is a reference, not the runtime decode table.
- [Memory packets](gpu/src/simulator/mem_types.py) and
  [D-cache](gpu/src/simulator/mem/dcache.py): overlapping packet definitions;
  follow actual imports and conversions.
- [Active CSR implementation](gpu/src/simulator/scheduler/csrtable.py): used by
  `SM`; `simulator/csr_table.py` is a separate, less capable duplicate.
- [Emulator submodule declaration](.gitmodules): the reference ISS belongs at
  `gpu/src/emulator`. The root `emulator/` graphics code is a different component.

## Execution and interface contracts

Logical data flow:

```text
launch image -> TBS -> warp scheduler -> I-cache -> decode/PRF -> issue/RF
                                                                  |
                                                                  v
                                                        execute FUs/FSUs
                                                                  |
                                                                  v
                                                     WB buffers -> RF/PRF

I-cache ----------------------> memory controller <---- D-cache <---- LSU
                                         |                |
                                         v                +----> LSU responses
                                  sparse byte memory
```

Writeback retirement, issue occupancy, I-cache fetch/EOP status, jumps, and
LSU flush completion feed the scheduler. Branch comparisons produce predicate
results; jumps redirect the PC. Do not substitute conventional GPU branch or
scoreboard semantics for this implementation.

`SM.tick()` performs this exact order, mutating objects immediately:

```text
wb.tick
ex.tick -> ex.compute
dcache.compute
issue.compute
decode.compute
memc.compute
icache.compute
scheduler.compute
tbs.compute (if present)
PRF counter sample
SM cycle increment; finished = tbs.kern_finished
```

There is **no global current/next-state commit**. For example, WB writes are
visible to issue and decode later in the same tick; a D-cache memory request
can reach the controller that tick, whereas I-cache runs after the controller.
An LSU request can reach D-cache that tick; its response is consumed by LSU on
a later tick. Stage counters are independent and have different increment points.

| Boundary | Payload and consumption contract |
| --- | --- |
| `LatchIF` | One slot with `valid`, `payload`, and optional `forward_if.wait`. `push()` can fail; `pop()` clears validity; `snoop()` returns the same object; `force_push()` overwrites. `valid=True` can coexist with a `None` payload. |
| `ForwardingIF` | One overwriteable payload; `pop()` clears it. `push()` also clears `wait`. It is not a queue or broadcast bus. Multiple readers need explicitly ordered access. |
| TBS -> scheduler | Tuple `(block_id, block_thread_count, start_pc)`; no explicit kernel identity or completion token. Static initialization uses a three-element list. |
| Scheduler -> I-cache -> decode -> issue -> execute | The same mutable `Instruction` accumulates PC, warp/group, active mask, instruction bytes, opcode, operands, predicate list, selected FSU, results, and timing fields. `intended_FU` actually identifies an FSU. |
| I-cache/issue/jump/WB -> scheduler | I-cache dict `{fetch,eop,warp_id}`; issue list of full flags by group; jump dict `{warp,dest}`; WB list of `{warp_group_id,warp_id,new_mask}`. These shapes and their per-cycle availability are implicit contracts. |
| LSU <-> D-cache | Address/size/read-write/store-value/halt request; response types include `MISS_ACCEPTED`, `HIT_COMPLETE`, `MISS_COMPLETE`, `HIT_STALL`, `FLUSH_COMPLETE`. Miss completion can require load replay; it is not necessarily returned load data. |
| Caches <-> controller | Request dictionaries normalize `warp`/`warp_id` and `warpGroup`/`warp_group_id`. Responses reuse `Instruction.packet` or dynamically attached `status`. D-cache uses response `warp_id` as **bank ID**, not execution warp ID. |
| Shared resources | Execute writes the shared FUST (`True` means unavailable); decode selects by FSU name and issue reads availability. Issue and WB share the RF; decode and WB share PRF; scheduler and decode share CSR state. |

Some wired signals are not active consumers: scheduler does not read decode's
packet forwarding dict; EOP comes from I-cache. The issue-to-decode wait interface
is not attached to the decode/issue latch in `SM`. Decode tests the bound
`ready_for_push` method without calling it and does not retain a failed push.
Several other stages ignore push failure. Characterize stalls before altering
capacity or ordering; the interface type alone does not guarantee lossless flow.

Initialization loads settings and memory, creates telemetry, constructs the
controller before caches (for telemetry's published memory latency), creates
launch/scheduler state, then wires decode, execute, WB, and issue. PRF entries
are explicitly initialized to all true by `SM`; RF entries start at zero.
`golden_rf` is allocated but is not a live reference-execution model.

Completion follows predicated HALT retirement -> warp/group drain -> scheduler
halt signal -> LSU drain/flush request -> D-cache dirty-line writeback -> LSU
flush acknowledgement -> scheduler block completion -> TBS `kern_finished`.
RF/PRF reset between launches is not implemented by that completion path.
`SM.finalize()` exports telemetry; the runner explicitly dumps memory afterward.
Every `Mem` instance also registers an `atexit` dump to CWD `memsim.hex`, retaining
the instance and potentially overwriting that file after multi-case runs.

## Module and parameterization reconnaissance

Parameter classes used below:

- **A — architectural:** lane/warp geometry, register counts, address/data width,
  ISA-visible predicates and launch limits. Changes require cross-stage/ISA review.
- **M — microarchitectural:** queues, banks, scheduling, pipeline latency and
  resource count, subject to current numerical and timing couplings.
- **I — internal:** host containers, trace buffering, IDs, paths, diagnostic
  formatting, settings lifetime. Some still affect modeled behavior today.
- **C — semantic constants:** opcode encodings, field positions, byte order,
  masks derived from the fixed ISA, arithmetic algorithm constants. Preserve
  unless deliberately changing that contract; do not make every literal a knob.

### Launch, scheduling, and front end

| Module | Responsibility, inputs -> outputs; owned state | Knobs, hard-coded assumptions, candidates and risks |
| --- | --- | --- |
| [SM](gpu/src/simulator/sm.py) | Composition/lifecycle: input image + Settings -> stage graph, cycles, finished flag, telemetry. Owns graph/resources through a heterogeneous dict. | A: one constructed SM and one kernel pointer slot. M: controller policy is passed as literal `rr`, issue latency as `1`; only `MemBranchJumpUnit_0/Jump_0` and `Ldst_Fu_0` get external wiring. Candidate: explicit construction contracts after tracing every stage consumer; changing construction or tick order can change behavior. |
| [TBS](gpu/src/simulator/tbs/tbs.py) | Launch header + completed block IDs -> block tuples. Owns block records, pending/done ID lists, SM availability, kernel-finished flag. | A: constructor defaults `threads_per_sm=1024`, `min_thread_division=32` are not derived from Settings. Single-SM protocol; block count is derived from total threads and block size. Header grid count/argument size are unused. M: launch loop has no bandwidth check, mutates pending list while iterating, and ignores failed latch pushes. Capacity changes risk lost launch bookkeeping. |
| [Scheduler](gpu/src/simulator/scheduler/scheduler.py) / [warp](gpu/src/simulator/warp.py) | Launch and feedback -> fetch Instruction, flush and block completion. Owns paired warp groups, PCs, masks, in-flight counts, packet completion, RR/GTO pointers, launch allocation; mutates CSR. | Configured warp count and `RR`/`GTO` policy. A: 32-lane masks, default warp size 32, fixed two-warps-per-group parity and PC+4. Odd warp counts still allocate a partner. M: one fetch per call, packet drain gating; static issue buffer count must match consumers. `BARRIER`/`at_barrier` exist without a demonstrated barrier protocol. Candidate: derived group dimensions and launch capacity; characterize multi-block reuse, partial warps, RR/GTO first. |
| [I-cache](gpu/src/simulator/mem/icache_stage.py) | Fetch Instruction + controller response -> instruction packet and scheduler fetch/EOP dict. Owns set/way lists with LRU timestamps, one pending miss, held request, cycle. | M: size/block size/associativity affect indexing; one pending miss globally stalls fetch. `hit_latency` feeds counters, not a hit pipeline. Stored response is reused without selecting an instruction offset within a larger cache line; current `block_size=4` matches one instruction. Candidate: characterize capacity/associativity first; larger lines or concurrency require interface/timing work. |
| [Decode](gpu/src/simulator/decode/decode_class.py) | Raw instruction + active mask + PRF/CSR/kernel pointers/FUST -> enriched Instruction and packet-marker dict. Holds resource references; processes one input per call. | A/C: 32-bit instruction, 7-bit opcode, 6-bit register fields, 5-bit predicate selectors, EOP bit 31/EOS bit 30, per-op immediate layouts. Hard-coded 32-lane data, AUIPC and predicate-load/store masks, kernel slot 0, RF parity banks and predicate bank 0. Chooses first matching FSU name, not an available unit. Candidate: lane count and routing contracts only after tracing enums, execution support, RF/PRF, issue and WB. |
| [Issue](gpu/src/simulator/issue/stage.py) | Decoded Instruction + RF + FUST -> one dispatch and occupancy flags. Owns 16 group FIFOs of depth 4, heads/counts, even/odd staged operands, progress counters, ready deque and cycle. | M: fixed 16 groups, depth 4, full threshold `depth-2`, two operand-read steps, parity banking; selects at most one new staged instruction per call. Dispatch precedes reads, selection, then insertion. `fust_latency_cycles` and countdown storage exist but active dispatch uses FUST instead. Candidate: depth/reserved headroom and derived group count; include scheduler lookahead, non-retaining upstream pushes and unbounded ready deque in analysis. |
| [RF](gpu/src/simulator/issue/regfile.py), [PRF](gpu/src/simulator/decode/predicate_reg_file.py), [CSR](gpu/src/simulator/scheduler/csrtable.py), [kernel pointers](gpu/src/simulator/kernel_base_pointers.py) | Persistent register/predicate/launch state. RF reads return lane-list references; WB mutates individual entries. CSR maps warp to base thread ID/block ID/block size and active blocks. | A: SM creates default RF with 2 banks, 32 warps, 64 registers, 32 lanes and default CSR with 32 warps. RF uses `% banks` but hard-coded `//2`. PRF count/warp count come from Settings; its own lane count=32 and banks=1. SM repairs the extra nesting produced by PRF reset. RF register 0 ignores writes (C). Candidate: coherent storage geometry/reset semantics; changing WB bank settings alone does not resize these resources. |

### Back end, memory, and instrumentation

| Module | Responsibility, inputs -> outputs; owned state | Knobs, hard-coded assumptions, candidates and risks |
| --- | --- | --- |
| [Execute/FUs](gpu/src/simulator/execute/stage.py), [FU factories](gpu/src/simulator/execute/functional_unit.py) | Dispatch by `intended_FU`, tick/compute FSUs, publish FUST and per-FSU EX/WB latches. Own named FU/FSU dictionaries. | M: counts and arithmetic latencies are already configured. Names use `i * (num + 1)`, causing duplicate subunit identities across multiple outer FUs; FUST/latch/telemetry dictionaries can collide. MemBranchJump construction loops over `ldst_count` for all three subunit kinds, ignoring independent branch/jump counts. Candidate: characterize factory/routing identity before scaling resources. Decode's first-match selection also prevents assuming load balancing. |
| [Arithmetic FSUs](gpu/src/simulator/execute/arithmetic_sub_unit.py) | Lane operands/predicates -> 32-bit results; own compacting pipelines, readiness, counters; trig additionally owns precomputed tables. | M: configured latency creates `max(1, latency-1)` internal slots. Latency=1 advances again during compute. A: all arithmetic loops use 32 lanes. **Trig latency changes CORDIC iteration count; inverse-sqrt latency changes Newton iterations**, so these knobs can alter numerical results. C: overflow masks, floating representation and inverse-sqrt seed `0x5f3759df` are semantic choices. Do not treat algorithm accuracy as purely timing. |
| [Branch/Jump](gpu/src/simulator/execute/functional_sub_unit.py) | Branch compares operands -> `wdat_pred`; HALT carries masks to WB. Jump -> scheduler destination plus link results. Each owns one instruction slot. | M: fixed single-slot/single-cycle design. A: 32 lanes; JALR requires all operand lane values equal; JPNZ uses any active predicate. Branch supports BEQ/BNE/HALT although decode routes other branch enums here. Candidate: latency/slot characterization; changing redirection timing or opcode coverage is a behavioral change. |
| [LSU / pending_mem](gpu/src/simulator/execute/functional_sub_unit.py) | Queued Instructions -> lane memory requests -> result Instruction; scheduler halt -> flush acknowledgement. Owns LD/ST queue, completed buffer, one outstanding request flag and per-lane completion/miss/address arrays. | M: queue and WB-buffer capacities configured; only head instruction issues memory work, one request at a time. A: fixed 32 lanes and byte/half/word formats. D-cache line/word sizes override FU config in SM; LSU constructs a configured `pending_mem` for printing but enqueues a second object with defaults. Candidate: queue capacity, replay/response contract, consistent geometry; preserve lane/address coalescing, store ordering and flush timing. |
| [D-cache/banks/MSHRs](gpu/src/simulator/mem/dcache.py) | LSU requests and memory responses -> hit/miss/replay/flush responses. Owns per-bank sets/ways/LRU, hit pipelines, MSHR deques, miss-ID map, bank state machines, pending request, unbounded response deque, shadow cache statistics. | M: banks, sets/bank, ways, line words, hit latency, MSHR depth already drive structures. Real bytes = banks × sets × ways × line words × word bytes. `cache_size` sizes the shadow statistics model; legacy `block_size`/`associativity` do not define real geometry. **MSHR depth also initializes miss countdown**, coupling capacity and delay. I: UUID width partitions bank/local IDs; wrap must not collide with live misses. A/C: address slicing assumes 32 bits and power-of-two geometry; several byte/word paths still assume 4 bytes. Candidate: coherent geometry and capacity/latency characterization; shared memory latch, bank iteration priority and replay/flush state are consumers. |
| [Memory controller](gpu/src/simulator/mem/mem_controller.py) | Arbitrates I/D request latches -> sparse-memory reads/writes -> response latches. Owns in-flight request list and RR toggle. | M: latency from Settings; constructor offers `max_inflight=1` and `icache_prio`, neither exposed by SM. Ages, completes at most one, then starts at most one per call. No extra ingress queues. Fixed 4-byte list-word serialization and synthesized 32-lane predicates. Candidate: policy/capacity with response ordering, D-cache bank-ID reuse and backpressure characterized first. |
| [Memory backend](gpu/src/simulator/mem/memory.py) | Addressed text image -> sparse `dict[int,int]` bytes; read/write Bits and sorted nonzero-word hex dump. Owns memory and exit callback. | A/C: 4-byte little-endian input/dump words, absent bytes read as zero; no fixed allocated RAM capacity. I: serialization and automatic dump lifetime. `start_pc` does not relocate explicitly addressed input. Candidate: explicit I/O/lifetime contracts; preserve sparse zero semantics and ordering. |
| [Writeback](gpu/src/simulator/writeback/stage.py), [buffers](gpu/src/simulator/writeback/writeback_buffer.py) | FSU results -> per-bank selected results -> RF/PRF writes and scheduler retirement. Owns configured queues/stacks/circular buffers, arbitration, saved previous selection and counters. | M: per-FSU/per-bank organization, fixed/variable sizes, two distinct age/capacity/FSU priority policies. Selects at most one result per bank; stage commits the previous tick's selection. A: 32 lanes and decode's bank mapping. Buffer capacity changes affect stalls and timing; policy ties depend on traversal and helpers. Variable sizes/priorities require actual FSU names. Stack changes ordering; circular buffer overwrites if called while full, so retain admission guards. |
| [Containers](gpu/src/simulator/utils/data_structures) / [telemetry](gpu/src/simulator/utils/performance_counter) | Containers retain instruction references. Telemeter owns counters, trace rows/index, publish/receive store, optional trigger state and snapshot callbacks; exports Parquet. | I: trace window/unit filtering/buffer limit and output paths. `CompactQueue` shifts holes and reports `capacity=length-1`; circular/stack fullness APIs differ. Do not normalize these silently. Telemetry is per-SM but also distributes controller latency to cache counters. Counters are derived observations, not an independent timing oracle; cache average latency is an estimate, not measured end-to-end service. |

Checked-in baseline (distinct from class defaults): 32 warps, 32 lanes,
32 predicates, TBS enabled, RR scheduling; I-cache 32 KiB with 4-byte lines and
one way; D-cache 2 banks × 16 sets × 8 ways × 32 words × 4 bytes = 32 KiB,
hit latency 2 and MSHR depth 8; controller latency 2; LSU queue 32/completed
buffer 1; WB per-FSU compact queues of size 8, capacity then age priority;
2 RF banks plus 1 PRF bank. Each outer FU count is 1; FP sqrt count is 0.

## Configuration, inputs, and known characterization gaps

`Settings` uses init arguments, then TOML, then environment settings. Default
TOML is beside `gpu/config.py`; custom files are separate complete settings
sources, not sweep overlays. Missing fields can use class defaults, which differ
from checked-in TOML. `get_settings()` caches a mutable module-global instance;
an explicit path reloads it. `resolve_paths()` anchors configured relative paths
to `gpu/` even for custom TOML elsewhere. Runner results/debug paths additionally
depend on CWD; use `gpu/` as the run directory. Pydantic type/enum parsing is not
cross-module geometry or architectural validation.

Simulator `.bin` files are **text**, one `address 32-binary-digit-word` per line;
`.hex` is `address hex-word`. `Mem` accepts comments and blank lines, but TBS is
stricter: it reads exactly the first nine physical lines and extracts second
columns from lines 4–9, ignoring their addresses. Expected launch locations are
0x0C entry PC, 0x10 block threads, 0x14 grid blocks, 0x18 total threads,
0x1C argument pointer, 0x20 argument bytes. TBS uses entry/block/total/argument
pointer; it does not call `Settings.read_mmio_from_meminit()` or its fallbacks.
Instruction words starting at line 1 are therefore not valid TBS launch headers.

Important limits to carry into future characterization:

- No-TBS construction exists, but runner and `SM.tick()` unconditionally read
  `pipeline['tbs']`; scheduler flush completion also assumes `Scheduler_TBS`.
  Do not recommend disabling TBS as a working workaround.
- `sm.threads_per_warp`, RF/PRF bank fields, kernel count/ID, memory policy, and
  independent FU counts are not uniformly propagated. Validate consumers, not
  just field existence. Keep ISA widths separate from lane counts despite both
  frequently being 32.
- `perf_counter.enabled=false` constructs `PerfConfig.disabled()`, which has
  the same empty enabled-unit set as all-units summary mode. Telemeter still
  creates a directory and enables registered counters. `summary_only` takes
  precedence over trace configuration and does not pass the configured unit
  filter. `flight_recorder_enabled` is not wired to triggers/providers or
  `advance_flight_recorder()` by `SM`.
- Scheduler counter calls currently pass `is_stalled=fetch` and
  `is_busy=not fetch`; verify that meaning before using those rates. Scheduler
  PC-spread and PRF occupancy counters retain per-cycle lists, so summary mode
  does not imply bounded host-memory usage.
- Functional test truth can be emulator output or checked-in expected hex.
  Program-local `program_config.toml` can restrict the compared address range.
  A matching memory region does not establish RF/PRF correctness or timing.
- Normal binary/expected mode ignores `run_simulator()`'s Boolean result;
  missing expected files return a successful `TestResult` after printing SKIP.
  A cycle-limit exit warns and `run_simulator()` still returns true. Sweep mode
  additionally checks `last_sim_finished`, and checks truth only if requested.
  Require completion and actual comparison evidence, not just PASS/exit zero.
- Many unit images have no TBS header (inspected `unit/i_type/addi.bin`), while
  program vertex/pixel images do. Test thread defaults, image header and expected
  filename/directory must agree. Do not apply old unit-test commands blindly.
- Runner construction clears all files in `diff_dir` even with
  `--skip-cleanup`; `--clean` removes its parent directory recursively. Filenames
  and sweep paths often use only the test stem, so cases can collide. Concurrent
  runs in one output tree are not isolated.

These are source-based findings, not newly reproduced runtime defects. Proposed
future work is to establish completion/output/cycle baselines, characterize
full/empty and flush transitions, inventory configuration consumers, then choose
one bounded parameter change. Add behavior characterization where needed after
authorization; do not turn this list into an unsolicited bug-fix batch.

## Future C++ port notes (no port work authorized)

- Preserve object identity and aliasing: `Instruction` is progressively mutated,
  RF reads expose lists, latches retain references, and `SM.pipeline['ldst']`
  aliases an execute-owned subunit. The CSR/PRF/FUST objects have multiple users.
- Annotations do not describe every runtime shape: predicates annotated as Bits
  become lists, some register fields vary in width, result lists acquire `None`,
  and controller requests/instructions gain `.inst`, `.src`, `.status` dynamically.
  Similar packet class names come from different modules.
- Preserve `Bits` bit indexing versus little-endian bytes, `.int` versus `.uint`,
  explicit overflow masking, arbitrary-precision Python intermediates, float
  conversion/rounding and division semantics. Latency-dependent numerical
  approximations need their own characterization.
- Dictionary insertion order, list mutation during iteration, `set` iteration,
  truthiness, `False` versus `None` sentinels, callbacks/lambdas, runtime `type_`
  checks and string-based dispatch all influence control or ordering. Container
  substitution is not automatically behavior-preserving.
- Composition and inheritance coexist: Stage subclasses, abstract FSUs, factories
  that instantiate temporary FUs just to build FUST, and dataclass initialization
  all affect lifecycle. Constructor registration, `sys.path` mutation, settings
  globals, process-wide stdout capture/logging, and `atexit` ownership need explicit
  treatment later. No parallel simulation execution was found in the active path.
- Serialization includes sparse addressed text, enum/Bits values and heterogeneous
  Parquet rows. Telemetry snapshot callbacks and published configuration create
  dependencies beyond instruction flow. Do not begin replacing them now.

## Verification expectations

Use [COMMANDS.md](COMMANDS.md), and distinguish syntax checks from functional
validation. Record revision, Python/dependency environment, exact config, input,
truth source, compared address range, completion, cycles and output location.
For future behavior-preserving source work, compare baseline and changed runs
with the same inputs/configuration; include cycle/control-flow evidence relevant
to the change. Do not regenerate golden outputs to hide differences.

This inspection verified Python 3.12.3, AST parsing of 58 relevant Python files,
TOML syntax parsing of 40 files, sweep manifest path existence, and imports of all
declared runtime dependencies from `venv`. The configured ISS entry point remains
absent. The package declares Python >=3.8, but active source uses `match` syntax
requiring at least 3.10; the full supported version range is not established.
Python syntax success is not import/runtime compatibility.

The first runtime execution used `venv/bin/python` on
`gpu/tests/bin/program/vertex/t32/vertex.bin`, default `gpu/config.toml`,
`--truth exp`, and a 100000-cycle limit. It completed in **76,325 cycles**
(about 41 seconds), flushed the D-cache, and exported telemetry, but failed the
expected-output comparison: 401 addresses were compared, 249 matched and 152
differed. There were no missing or unexpected addresses. Temporary evidence is
under `/tmp/cardinal-vertex-03vwf_dh/`; its `summary.json`, diff log, and
simulator log are the authoritative run artifacts. This is a completion and
characterization baseline, not a passing correctness baseline.

The discovered GitHub workflow builds/deploys mdBook documentation, not simulator
tests. `gpu/pyproject.toml` has basic Pyright configuration but no installed checker
or enforced simulator lint/test workflow was found. Python stage tests are under
`gpu/tests/python/deprecated`; sampled tests import the absent
`simulator.latch_forward_stage`. Their intent is useful, but they are not a verified
regression suite. Runtime verification may be expensive due to full lane loops,
verbose prints, memory images and telemetry; start with one bounded program.

## Documentation audit

Classifications apply to the named scope: **CURRENT** appears accurate/useful;
**REVIEW** is questionable; **OUTDATED** demonstrably conflicts; **BLOAT** is
duplicated/excess context; **UNKNOWN** lacks evidence. No listed document was
rewritten during this task. External papers and linked ISA sheets were not audited.

| Document/scope | Classification | Evidence / review action |
| --- | --- | --- |
| [Root README](README.md), project distinction | CURRENT | Functional ISS versus cycle simulator distinction remains useful; use actual paths from SM/runner. |
| [GPU README](gpu/README.md) | REVIEW | Placeholder with a promised update, no current simulator workflow. COMMANDS supplies the inspected workflow. |
| [Directory structure source](dir_structure_source.md) and [CONTRIBUTING directory tree](CONTRIBUTING.md#directory-structure-work-in-progress) | OUTDATED | Show `gpu/simulator/src`, `gpu/common`, `schedule/`, `fetch/`, and old test hierarchy. Actual paths are `gpu/src/simulator`, `gpu/src/common`, `scheduler/`, `mem/icache_stage.py`, and `gpu/tests/{assembly,bin,exp}`. |
| CONTRIBUTING branching/process sections | UNKNOWN | Repository inspection alone does not establish current team branch policy. |
| [CONFIG guide](gpu/CONFIG.md), static/TBS modes, validation/ranges, memory/cache descriptions | OUTDATED | No-TBS completion is broken by unconditional TBS references; documented address-based MMIO fallbacks are not TBS's positional loader; memory latency is controller latency; D-cache geometry uses bank/set/way fields. See `SM`, `tbs.load`, `config.py`, and `dcache.py`. Several documented ranges are not enforced. |
| [Test guide](gpu/README_TESTS.md), repeated status, quick-start, mode and workflow sections | BLOAT | Two "Current Test Status" sections and repeated commands overlap QUICK_REFERENCE and later workflow sections. Condense after reconciling them against `test_cardinal.py`; do not preserve contradictory copies. |
| Test guide working/broken claims and paths | REVIEW | No current pass evidence; `program/saxpy.s` examples omit the actual `program/saxpy/` directory, and unit images may lack launch headers. SIN/COS implementations exist, so "not implemented" explanations need rechecking separately from whether tests pass. |
| [Quick reference](gpu/QUICK_REFERENCE.md) | REVIEW | Helpful option index, but repeats unverified test claims/no-TBS advice and broad binary patterns. Current flags and discovery behavior are in `test_cardinal.py`. |
| [Sweep guide](gpu/README_SWEEPS.md), default invocation | OUTDATED | `sweep_cases.toml` names missing `baseline.toml`, `dcache_hitlat4.toml`, `dcache_hitlat8.toml`. Phase A/B/C manifests resolve to existing files. File-format explanation remains useful. |
| [Sweep plan](gpu/README_SWEEP_PLAN.md) | REVIEW | Phase files and fixed 128-byte D-cache line assumptions exist. Winner/anchor claims are planning assumptions, not verified results; evaluate completion/correctness before comparing cycles. |
| [Frontend architecture](docs/src/architecture/front_end.md) | REVIEW | Predication concept is useful, but fixed 16 predicates differs from checked-in 32 and blanket mask/branch descriptions need per-op verification in decode/Branch/WB. Fetch section is a placeholder. |
| [Backend architecture](docs/src/architecture/back_end.md), [kernel start](docs/src/architecture/kernel_start.md) | UNKNOWN | Empty files; contain no implementation description to validate. |
| [Architecture reading list](docs/src/architecture.md) | CURRENT | Useful background index; not evidence for this implementation. Linked publications were not evaluated. |
| [Execute README](gpu/src/simulator/execute/docs/README.md), single-cycle helper instructions | OUTDATED | Says to call helper at end of `tick()`; active arithmetic subclasses call it from `compute()`. Actual name is `single_cycle_latency_compute_tick`; class is `FpUnit`, not `FloatUnit`. See `arithmetic_sub_unit.py` and `functional_unit.py`. |
| Execute README, introductory teaching/context | BLOAT | Generic Python terminology, external OOP tutorials, repeated caveats and empty subclass sections obscure the useful FU/FSU model. Condense around actual factories/interfaces/timing above; retain that model. |
| [Telemetry README](gpu/src/simulator/utils/performance_counter/README.md), disabled-mode claim | OUTDATED | "Completely disabled (zero overhead)" conflicts with empty-set-means-all in `PerfConfig`/`Telemeter.register_unit`. |
| Telemetry README, flight recorder/snapshot examples | REVIEW | Framework APIs exist, but example names/shapes and loop integration are not SM wiring. Verify providers against actual RF/cache structures before use. |
| [Assembler README](gpu/assembler/README.md) | REVIEW | It explicitly says much is unverified; simulator input needs addresses/launch data beyond raw assembler words. Check assembler plus runner formatting, and decoder, before relying on examples. |
| [Unit notes](gpu/tests/assembly/unit/notes.md) | REVIEW | Broad coverage claims are not test evidence; branch enum routing exceeds active Branch support. Validate against fixtures and execution paths. |
| Uninspected graphics/compiler/benchmark/research documents | UNKNOWN | Outside the focused simulator investigation; no conclusion based on age. |
