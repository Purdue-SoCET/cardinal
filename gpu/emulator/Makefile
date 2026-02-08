PYTHON := venv/bin/python3
EMULATOR := src/emulator.py
GOLDEN_MODEL := src/golden_model.py
INPUT_FILE := meminit.hex
KERNEL_DIM := 1024 1
START_PC := 0
TYPE := "hex"

# Defaults for golden runs / diffs (aligns with existing expected/*_exp_32.hex naming)
THREADS ?= 32
TRACE ?= 0

run:
	$(PYTHON) $(EMULATOR) $(INPUT_FILE) $(KERNEL_DIM) $(START_PC) $(TYPE)

run-bin:
	$(MAKE) run TYPE="bin"

clean:
	rm -f *.out *.log

.PHONY: golden diffs

# Usage:
#   make golden -- tests/unit_tests/simple_tests/tests
#   make golden -- tests/unit_tests/simple_tests/tests/add.s
#   make golden -- tests/unit_tests/simple_tests/tests --threads 32 --trace
#   make golden -- tests/unit_tests/simple_tests/tests THREADS=32 TRACE=1
#
# Output folders are created next to the lowest-level folder provided:
#   <base>/golden_dumps/
#   <base>/golden_traces/   (only when --trace / TRACE=1)
golden:
	@bash -eu -o pipefail -c '\
		ARGS="$(filter-out golden,$(MAKECMDGOALS))"; \
		threads="$(THREADS)"; \
		trace="$(TRACE)"; \
		test_path=""; \
		set -- $$ARGS; \
		while [ $$# -gt 0 ]; do \
			case "$$1" in \
				--) shift ;; \
				--trace) trace=1; shift ;; \
				--threads) threads="$$2"; shift 2 ;; \
				--threads=*) threads="$${1#--threads=}"; shift ;; \
				*) \
					if [ -z "$$test_path" ]; then test_path="$$1"; shift; else echo "Unknown arg: $$1" 1>&2; exit 2; fi ;; \
			esac; \
		done; \
		if [ -z "$$test_path" ]; then \
			echo "Usage: make golden -- <tests_dir|test.s> [--threads N] [--trace]" 1>&2; \
			exit 2; \
		fi; \
		test_path="$$(realpath -m "$$test_path")"; \
		if [ -d "$$test_path" ]; then \
			called_dir="$$test_path"; \
			base_dir="$$(dirname "$$called_dir")"; \
			mapfile -t asm_files < <(find "$$called_dir" -maxdepth 1 -type f -name "*.s" | sort); \
		elif [ -f "$$test_path" ]; then \
			called_dir="$$(dirname "$$test_path")"; \
			base_dir="$$(dirname "$$called_dir")"; \
			asm_files=("$$test_path"); \
		else \
			echo "Error: path not found: $$test_path" 1>&2; \
			exit 2; \
		fi; \
		if [ $${#asm_files[@]} -eq 0 ]; then \
			echo "Error: no .s tests found in: $$test_path" 1>&2; \
			exit 2; \
		fi; \
		dump_dir="$$base_dir/golden_dumps"; \
		mkdir -p "$$dump_dir"; \
		if [ "$$trace" = "1" ]; then \
			trace_dir="$$base_dir/golden_traces"; \
			mkdir -p "$$trace_dir"; \
		fi; \
		echo "Golden: threads=$$threads trace=$$trace"; \
		echo "Input:  $$test_path"; \
		echo "Dumps:  $$dump_dir"; \
		if [ "$$trace" = "1" ]; then echo "Traces: $$trace_dir"; fi; \
		for asm in "$${asm_files[@]}"; do \
			name="$$(basename "$$asm" .s)"; \
			out="$$dump_dir/$${name}_exp_$${threads}.hex"; \
			if [ "$$trace" = "1" ]; then \
				trace_out="$$trace_dir/$${name}_trace_$${threads}.log"; \
				$(PYTHON) $(GOLDEN_MODEL) --asm "$$asm" --threads "$$threads" --out "$$out" --trace > "$$trace_out" 2>&1; \
			else \
				$(PYTHON) $(GOLDEN_MODEL) --asm "$$asm" --threads "$$threads" --out "$$out"; \
			fi; \
			echo "Wrote:  $$out"; \
		done; \
	'

# Usage:
#   make diffs -- tests/unit_tests/simple_tests/.
#   make diffs -- tests/unit_tests/simple_tests/.
#
# Requires:
#   <base>/expected/
#   <base>/golden_dumps/
# Writes:
#   <base>/diffs/
diffs:
	@bash -eu -o pipefail -c '\
		ARGS="$(filter-out diffs,$(MAKECMDGOALS))"; \
		base_path=""; \
		set -- $$ARGS; \
		while [ $$# -gt 0 ]; do \
			case "$$1" in \
				--) shift ;; \
				*) \
					if [ -z "$$base_path" ]; then base_path="$$1"; shift; else echo "Unknown arg: $$1" 1>&2; exit 2; fi ;; \
			esac; \
		done; \
		if [ -z "$$base_path" ]; then \
			echo "Usage: make diffs -- <base_test_dir>" 1>&2; \
			exit 2; \
		fi; \
		base_dir="$$(realpath -m "$$base_path")"; \
		case "$$(basename "$$base_dir")" in \
			expected|golden_dumps|diffs) base_dir="$$(dirname "$$base_dir")" ;; \
		esac; \
		expected_dir="$$base_dir/expected"; \
		golden_dir="$$base_dir/golden_dumps"; \
		diffs_dir="$$base_dir/diffs"; \
		missing=0; \
		if [ ! -d "$$expected_dir" ]; then echo "Error: expected/ folder not found: $$expected_dir" 1>&2; missing=1; fi; \
		if [ ! -d "$$golden_dir" ]; then echo "Error: golden_dumps/ folder not found: $$golden_dir" 1>&2; missing=1; fi; \
		if [ "$$missing" = "1" ]; then exit 2; fi; \
		mkdir -p "$$diffs_dir"; \
		echo "Base:  $$base_dir"; \
		echo "Out:   $$diffs_dir"; \
		shopt -s nullglob; \
		exp_files=("$$expected_dir"/*.hex); \
		if [ $${#exp_files[@]} -eq 0 ]; then \
			echo "Error: no expected dumps matching *.hex in: $$expected_dir" 1>&2; \
			exit 2; \
		fi; \
		fail=0; \
		for exp in "$${exp_files[@]}"; do \
			base="$$(basename "$$exp")"; \
			gold="$$golden_dir/$$base"; \
			diff_out="$$diffs_dir/$${base%.hex}.diff"; \
			if [ ! -f "$$gold" ]; then \
				echo "MISSING: $$base (no golden dump at $$gold)" 1>&2; \
				fail=1; \
				continue; \
			fi; \
			if diff -u --label "expected/$$base" --label "golden_dumps/$$base" \
				<(awk "{print tolower(\$$0)}" "$$exp") \
				<(awk "{print tolower(\$$0)}" "$$gold") \
				> "$$diff_out"; then \
				rm -f "$$diff_out"; \
				echo "OK: $$base"; \
			else \
				echo "DIFF: $$base (see $$diff_out)" 1>&2; \
				fail=1; \
			fi; \
		done; \
		exit $$fail; \
	'

# Swallow extra positional args (paths / pseudo-flags) passed as make goals.
%:
	@: