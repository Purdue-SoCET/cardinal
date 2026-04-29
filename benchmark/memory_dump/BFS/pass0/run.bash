python3 src/emulator.py --mem-format hex tests/complex_tests/BFS/pass0/BFS_Input_pass0_t1024_b1.hex -b 1 -t 1024 --start-pc 0x00000024 --arg-pointer 0x00100000

python diffs.py --compare --allow-approx memsim.hex tests/complex_tests/BFS/pass0/BFS_Mid_pass0_t1024_b1.hex diff_BFS_1.txt


python3 src/emulator.py --mem-format hex tests/complex_tests/BFS/pass0/BFS_Mid_pass0_t1024_b1.hex -b 1 -t 1024 --start-pc 0x00000024 --arg-pointer 0x00100000

python diffs.py --compare --allow-approx memsim.hex tests/complex_tests/BFS/pass0/BFS_Output_pass0_t1024_b1.hex diff_BFS_2.txt