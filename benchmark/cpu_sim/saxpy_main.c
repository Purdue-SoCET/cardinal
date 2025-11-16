

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

    dim_t grid; grid.x = 1; grid.y = 1; grid.z = 1;
    dim_t block; block.x = ARR_SIZE; block.y = 1; block.z = 1;
    run_kernel(kernel_saxpy, grid, block, (void*)&arg);

    for (int i = 0; i < ARR_SIZE; i++) {
        uint32_t bits;
        memcpy(&bits, &arr2[i], sizeof bits);   // safe reinterp
        printf("0x%08x 0x%08x\n", (uint32_t)(BASE_Y_ADDRESS + 4*i), bits);
    }

    free(mem_space);

    return 0;
}