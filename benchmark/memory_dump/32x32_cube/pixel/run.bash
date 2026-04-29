python3 src/emulator.py --mem-format hex tests/complex_tests/pixel/pixelInput_memDump_1024.hex -b 1 -t 1024 --start-pc 0x00000024 --arg-pointer 0x001000AC

python diffs.py --compare --allow-approx memsim.hex tests/complex_tests/pixel/pixelOutput_memDump_1024.hex diff_pix.txt