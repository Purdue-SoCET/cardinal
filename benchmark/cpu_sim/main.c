

#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include "include/kernel_run.h"

// Include all needed kernels
#include "../kernels/include/add.h"

kernel_ptr_t* kernel_functions;

int main() {
    int THREAD_NUM = 100;

    uint8_t* mem_space = malloc(THREAD_NUM * sizeof(int) * 3);

    int* arg1 = (int*) mem_space;
    int* arg2 = &(((int*) mem_space)[THREAD_NUM]);
    int* ret = &(((int*) mem_space)[2*THREAD_NUM]);

    for(int i = 0; i < THREAD_NUM; i++) {
        arg1[i] = i;
        arg2[i] = i+21;
        ret[i] = 0;
    }

    add_arg_t arg;
    arg.a = arg1;
    arg.b = arg2;
    arg.out = ret;

    dim_t grid; grid.x = 1; grid.y = 1; grid.z = 1;
    dim_t block; block.x = THREAD_NUM; block.y = 1; block.z = 1;
    run_kernel(kernel_add, grid, block, (void*)&arg);

    for(int i = 0; i < THREAD_NUM; i++) {
        if(2*i+21 != ret[i]) {
            printf("Failed on i = %d\n", i);
            printf("Expected: %d\tGot: %d\n", 2*i+21, ret[i]);
            return 1;
        }
    }

    free(mem_space);

    return 0;
}