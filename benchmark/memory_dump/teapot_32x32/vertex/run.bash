python3 src/emulator.py --mem-format hex tests/complex_tests/teapot_32x32/vertex/vertexInput_memDump_529.hex -b 1 -t 529 --start-pc 0x00000024 --arg-pointer 0x00100000

diff -i tests/complex_tests/teapot_32x32/vertex/vertexOutput_memDump_529.hex memsim.hex >> diff_vert.txt