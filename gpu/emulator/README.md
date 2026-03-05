# SoCET GPU Emulator

## Setup
To setup the program, please run the following from the gpu/emulator directory. This should be ran once per terminal instance.

```
source setup.sh
```

## Usage
The emulator runs off a single compiled file repersenting the initial state of the memory. This should include all instructions and needed initial data for testing.

For Basic running, use the following commands:
```
python3 src/emulator.py meminit.bin                     # Default: 32 threads, 1 block
python3 src/emulator.py --mem-format hex meminit.hex    # Allow hex format (see input file section)
python3 src/emulator.py -t 1024 meminit.bin             # Run with 1024 threads
python3 src/emulator.py -h                              # Show help menu with all options
```

## Input File
The emulator allows two main input types: "**bin**" and "**hex**". Despite their file extensions, these are all encoded as standard text files in UTF-8 encoding. This allows direct reading and modification through standard text editors.

### bin
The bin file is the most basic format. It has no addressing, assuming memory starts at 0. Each word is made up 32 charecters, either '0' or '1', ended with a new-line. This are then placed one after the other, making up memory.

Example:
```
00000000111111110000000011111111            # 0x00FF00FF at 0x0
11110000111100001111000011110000            # 0xF0F0F0F0 at 0x4
...
```

### Hex
The hex file is slightly more versatile, in that it can be done as a basic format, like the above binary, or it can be done with an addressible format for larger more complex data inputs.

The most basic format is akin to the binary, but instead using a hexadecimal encoding. Each word is 8 characters, between '0' and 'f', and assumes data starts at address 0. For Example:
```
00FF00FF                # 0x00FF00FF at 0x0
DEADBEEF                # 0xDEADBEEF at 0x4
...
```

Alternativley, for more complex inputs, you can use an addressable structure. This takes the form of "0xADDR 0xDATA". For example:
```
0x00000004 0x00FF00FF   # 0x00FF00FF at 0x4
0x00000F00 0xDEADBEEF   # 0xDEADBEEF at 0xF00
...
```

## Emulator Testing

### Running the emulator
To test the emulator during development, a test structure has been setup. To go through all tests, run the following in the emulator directory (after setup):
```
./test.sh           # Run all tests through the emulator
./test.sh "test.s"  # Run only the given test
./test.sh "b*.s"    # Run tests that match wildcard (b*.s in this example)
```
This wil indicate how many of the tests pass, fail, and do not have a reference (tests expected output does not exist). Any failed tests will place logs in a "test_diffs" folder.

### Adding a test
A test requires two base components:
1. The core .s file (i.e. add.s, saxpy.s)
2. The expected output file (i.e. add_exp_t32_b1.hex, saxpy_exp_t1024_b1)

The .s file is the assembly code to be compiled for the test and ran. The expected output file is an address based hex file (see input file type section), whose job is both to outline the parameters of the test, and to contain the expected output. For an assembly test case "test.s", the expected output file **test_exp_tXX_bYY.hex** means to run the test for *XX* threads and and *YY* thread blocks. You can have multiple expected files for a single assembly file, creating multiple tests of the same program with different parameters.

Alongside the base test files, an additional file, **test_data.hex** can be created to act as the initial data in memory. This will then be placed alongside the compiled **test.s** for compilation.