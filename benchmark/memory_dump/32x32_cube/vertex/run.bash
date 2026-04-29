python3 src/emulator.py --mem-format hex tests/complex_tests/vertex/vertexInput_memDump_8.hex -b 1 -t 8 --start-pc 0x00000024 --arg-pointer 0x00100000

diff -i tests/complex_tests/vertex/vertexOutput_memDump_8.hex memsim.hex >> diff_vert.txt