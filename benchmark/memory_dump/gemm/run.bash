python3 src/emulator.py --mem-format hex tests/complex_tests/gemm/gemmInput_memDump_t32_b32.hex -b 32 -t 32 --start-pc 0x00000024 --arg-pointer 0x00100000

python diffs.py --compare --allow-approx memsim.hex tests/complex_tests/gemm/gemmOutput_memDump_t32_b32.hex diff_gemm.txt