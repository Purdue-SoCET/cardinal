// Standard Includes
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>
#include <time.h>
#include <limits.h>
#include <sys/mman.h>
#include <errno.h>
#include <string.h>
#include <math.h>
#include "include/kernel_run.h"
#include "include/shader_memdump.h"
#include "include/graphics_lib.h"

// Include all needed kernels
#include "../kernels/include/monte_carlo_pi.h"

#define ARGS_BASE_ADDR 0x00100000
#define HEAP_BASE_ADDR 0x10000000

#define INPUT_MEM_DUMP 1
#define OUTPUT_MEM_DUMP 1

uint8_t* memory_base;
uint8_t* memory_ptr;
#define ALLOCATE_MEM(dest, type, num) \
    type* dest = (type*) memory_ptr; \
    memory_ptr += num * sizeof(type);

#define ALLOCATE_ARGS(dest, type, num) \
    type* dest = (type*) args_ptr; \
    args_ptr += (num) * sizeof(type);

#define ALLOCATE_HEAP(dest, type, num) \
    type* dest = (type*) heap_ptr; \
    heap_ptr += (num) * sizeof(type);

// gcc -o main cpu_sim/monte_carlo_pi_main.c cpu_sim/kernel_run.c cpu_sim/shader_memdump.c kernels/monte_carlo_pi.c -DCPU_SIM 

int main(int argc, char** argv) {

    uint8_t* args_ptr;
    uint8_t* heap_ptr;

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

    srand(time(NULL));

    const int num_points = 1024 * 1024; 

    ALLOCATE_HEAP(circle_points_arr, int*, num_points);
    for (int i = 0; i < num_points; i++) {
        ALLOCATE_HEAP(point_counter, int, 1);
        *point_counter = 0;
        circle_points_arr[i] = point_counter;
    }

    monte_carlo_pi_arg_t* mcpi_args;
    ALLOCATE_ARGS(mcpi_args_mem, monte_carlo_pi_arg_t, 1);
    mcpi_args = mcpi_args_mem;
    mcpi_args->circle_points = circle_points_arr;
    mcpi_args->base_seed = rand();
    mcpi_args->num_points = num_points;

    if(INPUT_MEM_DUMP){
        size_t current_args_bytes = (size_t)args_ptr - (ARGS_BASE_ADDR);
        size_t current_heap_bytes = (size_t)heap_ptr - (HEAP_BASE_ADDR);
        dump_memory("build/mem_dump/input_mcp_args_dump.txt", (uint8_t*)ARGS_BASE_ADDR, (uint32_t)ARGS_BASE_ADDR, current_args_bytes);
        dump_memory("build/mem_dump/input_mcp_heap_dump.txt", (uint8_t*)HEAP_BASE_ADDR, (uint32_t)HEAP_BASE_ADDR, current_heap_bytes);
    }

    {
        int block_dim = 1024;
        //int grid_dim = (num_points + block_dim - 1) / block_dim;
        int grid_dim = 1;
        run_kernel(kernel_monte_carlo_pi, grid_dim, block_dim, (void*)mcpi_args);
    }

    if(OUTPUT_MEM_DUMP){
        size_t current_args_bytes = (size_t)args_ptr - (ARGS_BASE_ADDR);
        size_t current_heap_bytes = (size_t)heap_ptr - (HEAP_BASE_ADDR);
        dump_memory("build/mem_dump/output_mcp_args_dump.txt", (uint8_t*)ARGS_BASE_ADDR, (uint32_t)ARGS_BASE_ADDR, current_args_bytes);
        dump_memory("build/mem_dump/output_mcp_heap_dump.txt", (uint8_t*)HEAP_BASE_ADDR, (uint32_t)HEAP_BASE_ADDR, current_heap_bytes);
    }

    int inside_circle = 0;
    for (int i = 0; i < num_points; i++) {
        inside_circle += *(circle_points_arr[i]);
    }

    float pi_estimate = (4.0f * inside_circle) / num_points;
    printf("Estimated Pi: %f\n", pi_estimate);

    free(memory_base);
    return 0;
}