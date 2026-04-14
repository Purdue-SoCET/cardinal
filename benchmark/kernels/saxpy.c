#include "include/kernel.h"
#include "include/saxpy.h"

#ifdef GPU_SIM
void kernel_saxpy() 
#else
void kernel_saxpy(void* arg)
#endif
{
    #ifdef GPU_SIM
    saxpy_arg_t* args = (saxpy_arg_t*) argPtr();
    #else
    saxpy_arg_t* args = (saxpy_arg_t*) arg;
    #endif

    // Calculate the global thread index
    int i = blockIdx * blockDim + threadIdx;

    // Perform the calculation if the index is within bounds
    if (i < args->n) {
        args->y[i] = args->a * args->x[i] + args->y[i];
    }
}
