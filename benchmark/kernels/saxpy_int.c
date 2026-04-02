#include "include/kernel.h"
#include "include/saxpy.h"

#ifdef GPU_SIM
void main(void* arg)
#else
void kernel_saxpy_int(void* arg) 
#endif
{
    #ifdef GPU_SIM
    saxpy_arg_t* args = (saxpy_arg_t*) argPtr();
    // Calculate the global thread index
    int i = blockIdx() * blockDim() + threadIdx();
    #else
    saxpy_arg_t* args = (saxpy_arg_t*) arg;
    // Calculate the global thread index
    int i = blockIdx * blockDim + threadIdx;
    #endif

    // Perform the calculation if the index is within bounds
    if (i < args->n) {
        args->y[i] = args->a * args->x[i] + args->y[i];
    }
}
