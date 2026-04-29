python3 src/emulator.py --mem-format hex tests/complex_tests/monte_carlo_pi/monte_carlo_piInput_memDump_t32_b32.txt -b 32 -t 32 --start-pc 0x00000024 --arg-pointer 0x00100000

diff -i memsim.hex tests/complex_tests/monte_carlo_pi/monte_carlo_piOutput_memDump_t32_b32.txt >> diff_mcp.txt