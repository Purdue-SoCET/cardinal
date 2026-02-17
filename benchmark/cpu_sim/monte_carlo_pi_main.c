// Standard Includes
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>
#include <limits.h>
#include "include/kernel_run.h"

// Include all needed kernels
#include "../kernels/include/monte_carlo_pi.h"

// gcc -o main cpu_sim/monte_carlo_pi.c cpu_sim/kernel_run.c cpu_sim/include/* kernels/monte_carlo_pi.c -DCPU_SIM

// Globals
uint8_t* memory_ptr;  

// Macros
#define ALLOCATE_MEM(dest, type, num) \
    type* dest = (type*) memory_ptr; \
    memory_ptr += num * sizeof(type);

int main(int argc, char** argv) {

    srand(time(NULL));

    const int memory_size = 1024 * 1024 * 50;
    uint8_t* memory_base = (uint8_t*) malloc(memory_size);
    memory_ptr = memory_base;

    const int num_points = 1024 * 1024; 

    ALLOCATE_MEM(circle_points_arr, int*, num_points);
    for (int i = 0; i < num_points; i++) {
        ALLOCATE_MEM(point_counter, int, 1);
        *point_counter = 0;
        circle_points_arr[i] = point_counter;
    }

    monte_carlo_pi_arg_t* mcpi_args;
    ALLOCATE_MEM(mcpi_args_mem, monte_carlo_pi_arg_t, 1);
    mcpi_args = mcpi_args_mem;
    mcpi_args->circle_points = circle_points_arr;
    mcpi_args->base_seed = rand();
    mcpi_args->num_points = num_points;

    {
        int block_dim = 1024;
        int grid_dim = (num_points + block_dim - 1) / block_dim;
        run_kernel(kernel_monte_carlo_pi, grid_dim, block_dim, (void*)mcpi_args);
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