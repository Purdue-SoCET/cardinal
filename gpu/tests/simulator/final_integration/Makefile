PYTHON := python3
EMULATOR := ../../../emulator/src/emulator.py	# CHANGE THIS WHEN CHANGING DIRECTORY
SIMULATOR := ../integration3/sm-from-bin.py						# CHANGE THIS WHEN CHANGING DIRECTORY

# Default Parameters (Overridden by the generic test script)
THREADS ?= 32
BLOCKS ?= 1
START_PC ?= 0
INPUT ?= meminit.hex
SIM_INPUT ?= meminit.bin
FORMAT ?= hex

# The Interface
run:
	$(PYTHON) $(EMULATOR) -t $(THREADS) -b $(BLOCKS) --start-pc $(START_PC) --mem-format $(FORMAT) $(INPUT)

simulator:
	@$(PYTHON) $(SIMULATOR) $(SIM_INPUT)

clean:
	rm -f *.out *.log *.hex