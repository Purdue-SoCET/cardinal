PYTHON := python3
EMULATOR := ../../../emulator/src/emulator.py	# CHANGE THIS WHEN CHANGING DIRECTORY
SIMULATOR := sm-from-bin.py						# CHANGE THIS WHEN CHANGING DIRECTORY

# Default Parameters (Overridden by the generic test script)
THREADS ?= 32
BLOCKS ?= 1
START_PC ?=0x0
INPUT ?= ./tests/unit_tests/r_type/add_exp_t32_b1.hex
FORMAT ?= hex

# The Interface
run:
	$(PYTHON) $(EMULATOR) -t $(THREADS) -b $(BLOCKS) --start-pc $(START_PC) --mem-format $(FORMAT) $(INPUT)

simulator:
	@$(PYTHON) $(SIMULATOR) $(INPUT) -f ${FORMAT} -pc ${START_PC}

clean:
	rm -f *.out *.log *.hex