python3 src/emulator.py --mem-format hex tests/complex_tests/lavaMD/lavaMDInput_memDump_t128_b1.hex -b 1 -t 128 --start-pc 0x00000024 --arg-pointer 0x00100000

python diffs.py --compare --allow-approx memsim.hex tests/complex_tests/lavaMD/lavaMDOutput_memDump_t128_b1.hex diff_lavaMD.txt