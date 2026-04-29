python3 src/emulator.py --mem-format hex tests/complex_tests/teapot_32x32/pixel/pixelInput_memDump_1024.hex -b 1 -t 1024 --start-pc 0x00000024 --arg-pointer 0x001000A8

diff -i tests/complex_tests/teapot_32x32/pixel/pixelOutput_memDump_1024.hex memsim.hex >> diff_pix.txt