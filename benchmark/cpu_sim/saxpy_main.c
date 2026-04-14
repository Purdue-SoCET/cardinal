

#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <errno.h>
#include <string.h>
#include <math.h>
#include "include/kernel_run.h"
#include "include/graphics_lib.h"
#include "include/shader_memdump.h"

// Include all needed kernels
#include "../kernels/include/saxpy.h"

// Defines
#define ARR_SIZE 1024
#define BASE_Y_ADDRESS 0x00001074

#define ARGS_BASE_ADDR 0x00100000
#define HEAP_BASE_ADDR 0x10000000

// Macros
uint8_t* memory_base;
uint8_t* memory_ptr;

#define ALLOCATE_ARGS(dest, type, num) \
    type* dest = (type*) args_ptr; \
    args_ptr += (num) * sizeof(type);

#define ALLOCATE_HEAP(dest, type, num) \
    type* dest = (type*) heap_ptr; \
    heap_ptr += (num) * sizeof(type);

// for 32 bit: 
//gcc -o main cpu_sim/saxpy_main.c cpu_sim/kernel_run.c cpu_sim/include/* kernels/saxpy.c -DCPU_SIM -m32

void print_line(FILE* f, uintptr_t addr, uint32_t data) {
    fprintf(f, "0x%08X \t %08X\n", (unsigned int)addr, data);
}

void print_saxby_args(char* fname, saxpy_arg_t* args) {
    FILE *f = fopen(fname, "w");
    if (!f) return;

    // 1. Struct Header (4 words)
    uint32_t* s_raw = (uint32_t*)args;
    for (int i = 0; i < 4; i++) print_line(f, (uintptr_t)&s_raw[i], s_raw[i]);

    for (int i = 0; i < args->n; i++) {
        uint32_t x_bits, y_bits;
        print_line(f, (uintptr_t)&args->x[i], args->x[i]);
        print_line(f, (uintptr_t)&args->y[i], args->y[i]);
    }
    
    fclose(f);
}


int main() {
    uint8_t* args_ptr;
    uint8_t* heap_ptr;

    // 1. Map the Arguments Space (Starts at 0x00100000, size ~15MB)
    size_t args_size = 15 * 1024 * 1024;
    args_ptr = mmap((void*)0x00100000, args_size, 
                             PROT_READ | PROT_WRITE, 
                             MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, 
                             -1, 0);

    // 2. Map the Heap Space (Starts at 0x10000000, size ~256MB)
    size_t heap_size = 256 * 1024 * 1024;
    heap_ptr = mmap((void*)0x10000000, heap_size, 
                             PROT_READ | PROT_WRITE, 
                             MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, 
                             -1, 0);

    if (args_ptr == MAP_FAILED || heap_ptr == MAP_FAILED) {
        fprintf(stderr, "mmap failed! OS refused to give us those exact addresses. Error: %s\n", strerror(errno));
        return -1;
    }

    printf("Successfully forced Arguments to %p and Heap to %p\n", args_ptr, heap_ptr);

    uint8_t* args_start_ptr = args_ptr;
    uint8_t* heap_start_ptr = heap_ptr;

    // Allocate arrays in the HEAP section
    ALLOCATE_HEAP(arr1, float, ARR_SIZE);
    ALLOCATE_HEAP(arr2, float, ARR_SIZE);

    for(int i = 0; i < ARR_SIZE; i++) {
        arr1[i] = (float)i;
        arr2[i] = (float)i * 2.0f;
    }

    // Allocate the argument struct in the ARGS section
    ALLOCATE_ARGS(kernel_args, saxpy_arg_t, 1);

    kernel_args->x = arr1;
    kernel_args->y = arr2;
    kernel_args->n = ARR_SIZE;
    kernel_args->a = 2.0f;

    // Kernel Launch Logic
    int grid_dim = (int)ceil(ARR_SIZE / 1024.0); 
    int block_dim = ARR_SIZE > 1024 ? 1024 : ARR_SIZE;

    // Memory Dumps (Using the actual pointers)
    dump_memory("build/mem_dump/saxpyInput_args.txt", args_start_ptr, 0x00100000, args_ptr - args_start_ptr);
    dump_memory("build/mem_dump/saxpyInput_heap.txt", heap_start_ptr, 0x10000000, heap_ptr - heap_start_ptr);
    
    printf("Launching SAXPY Kernel with grid_dim: %d, block_dim: %d\n", grid_dim, block_dim);
    run_kernel(kernel_saxpy, grid_dim, block_dim, (void*)kernel_args);

    dump_memory("build/mem_dump/saxpyOutput_args.txt", args_start_ptr, 0x00100000, args_ptr - args_start_ptr);
    dump_memory("build/mem_dump/saxpyOutput_heap.txt", heap_start_ptr, 0x10000000, heap_ptr - heap_start_ptr);

    // Cleanup
    munmap(args_start_ptr, args_size);
    munmap(heap_start_ptr, heap_size);

    return 0;
}