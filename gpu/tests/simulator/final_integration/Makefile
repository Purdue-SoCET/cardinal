PYTHON := python3
EMULATOR := ../../../emulator/src/emulator.py	# CHANGE THIS WHEN CHANGING DIRECTORY
SIMULATOR := dummy_sm.py						# CHANGE THIS WHEN CHANGING DIRECTORY

# Default Parameters (Overridden by the generic test script)
THREADS ?= 32
BLOCKS ?= 1
START_PC ?= 0
INPUT ?= meminit.hex
FORMAT ?= hex

# The Interface
run:
	$(PYTHON) $(EMULATOR) -t $(THREADS) -b $(BLOCKS) --start-pc $(START_PC) --mem-format $(FORMAT) $(INPUT)

simulator:
	@$(PYTHON) $(SIMULATOR) $(INPUT)

clean:
	rm -f *.out *.log *.hex