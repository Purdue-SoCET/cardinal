## CPU Sim

## File Structure:
* Benchmark/
  * kernels/ -> Contains the various gpu kernels for the benchmark
    * eg: pixel.C, triangle.C, test.C
  * cpu_sim/ -> Top-level CPU C code which can compile kernels and run them serially
    * eg: cpu_main.c
  * gpu_emulator/ -> Top-level script to run emulator
    * eg: esim_main.py
  * gpu_funcsim/ -> Top-level script to run functional simulator
    * eg: fsim_main.py
  * Makefile