

#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "include/kernel_run.h"

// Include all needed kernels
#include "../kernels/include/saxpy.h"

// Defines
#define ARR_SIZE 1024
#define BASE_Y_ADDRESS 0x00001074

// for 32 bit: 
//gcc -o main cpu_sim/saxpy_main.c cpu_sim/kernel_run.c cpu_sim/include/* kernels/saxpy.c -DCPU_SIM -m32

void print_line(FILE* f, uintptr_t addr, uint32_t data) {
    fprintf(f, "0x%08X \t 0x%08X\n", (unsigned int)addr, data);
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
    uint8_t* mem_space = malloc(ARR_SIZE * sizeof(float) * 2);

    float* arr1 = (float*) mem_space;
    float* arr2 = &(((float*) mem_space)[ARR_SIZE]);

    for(int i = 0; i < ARR_SIZE; i++) {
        arr1[i] = i;
        arr2[i] = 2*i;
    }

    saxpy_arg_t arg;
    int n;
    float a;
    arg.x = arr1;
    arg.y = arr2;
    arg.n = ARR_SIZE;
    arg.a = 2.0f;

    int grid = 1;
    int block = ARR_SIZE;

    print_saxby_args("build/saxpyInput.txt", &arg);
    
    run_kernel(kernel_saxpy, grid, block, (void*)&arg);

    for (int i = 0; i < ARR_SIZE; i++) {
        uint32_t bits;
        memcpy(&bits, &arr2[i], sizeof bits);   // safe reinterp
        printf("0x%08x 0x%08x\n", (uint32_t)(BASE_Y_ADDRESS + 4*i), bits);
    }

    print_saxby_args("build/saxpyOutput.txt", &arg);

    free(mem_space);

    return 0;
}