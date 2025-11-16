PYTHON := venv/bin/python3
EMULATOR := src/emulator.py
INPUT_FILE := meminit.hex
KERNEL_DIM := 1024 1
START_PC := 0
TYPE := "hex"

run:
	$(PYTHON) $(EMULATOR) $(INPUT_FILE) $(KERNEL_DIM) $(START_PC) $(TYPE)

run-bin:
	$(MAKE) run TYPE="bin"

clean:
	rm -f *.out *.log