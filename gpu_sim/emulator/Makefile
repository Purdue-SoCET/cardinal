PYTHON := venv/bin/python3
EMULATOR := src/emulator.py
INPUT_FILE := meminit.hex
BLOCK_DIM := 4 4 2
START_PC := 0
TYPE := "hex"

run:
	$(PYTHON) $(EMULATOR) $(INPUT_FILE) $(BLOCK_DIM) $(START_PC) $(TYPE)

clean:
	rm -f *.out *.log