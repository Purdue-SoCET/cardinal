#include "include/kernel.h"
#include "include/saxpy.h"

void kernel_saxpy(void* arg) {
    saxpy_arg_t* args = (saxpy_arg_t*) arg;

    // Calculate the global thread index
    int i = blockIdx.x * blockDim.x + threadIdx.x;

    // Perform the calculation if the index is within bounds
    if (i < args->n) {
        args->y[i] = args->a * args->x[i] + args->y[i];
    }
}
