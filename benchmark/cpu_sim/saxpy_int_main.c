

#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "include/kernel_run.h"

// gcc -o main cpu_sim/saxpy_int_main.c cpu_sim/kernel_run.c cpu_sim/include/* kernels/saxpy_int.c -DCPU_SIM

// Include all needed kernels
#include "../kernels/include/saxpy_int.h"

// Defines
#define ARR_SIZE 1024
#define BASE_Y_ADDRESS 0x00001074

int main() {
    uint8_t* mem_space = malloc(ARR_SIZE * sizeof(float) * 2);

    int* arr1 = (int*) mem_space;
    int* arr2 = &(((int*) mem_space)[ARR_SIZE]);

    for(int i = 0; i < ARR_SIZE; i++) {
        arr1[i] = i;
        arr2[i] = 2*i;
    }

    saxpy_arg_t arg;
    int n;
    int a;
    arg.x = arr1;
    arg.y = arr2;
    arg.n = ARR_SIZE;
    arg.a = 2;

    int grid = 1;
    int block = ARR_SIZE;
    run_kernel(kernel_saxpy_int, grid, block, (void*)&arg);

    for (int i = 0; i < ARR_SIZE; i++) {
        uint32_t bits;
        memcpy(&bits, &arr2[i], sizeof bits);   // safe reinterp
        printf("0x%08x 0x%08x\n", (uint32_t)(BASE_Y_ADDRESS + 4*i), bits);
    }

    free(mem_space);

    return 0;
}