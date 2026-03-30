## CPU Sim

## Custom Kernels

1. Create a yaml file inside yaml_structs of the arguments for the kernel
2. Run 
``` 
make new_custom KERNEL=$(KernelName)
```
3. Write GPU kernel in kernels/$(KernelName).c
4. Write Host/CPU side call in cpu_sim/main_$(KernelName).c
5. Compile and run with 
``` 
make custom KERNEL=$(KernelName)
```
or 
``` 
make custom32 KERNEL=$(KernelName) #32 bit version
```

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
