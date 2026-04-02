#include "include/kernel.h"
#include "include/add.h"

#ifdef GPU_SIM
void main(void* arg)
#else
void kernel_add(void* arg) 
#endif
{
    #ifdef GPU_SIM
    add_arg_t* args = (add_arg_t*) argPtr();
    int i = blockIdx() * blockDim() + threadIdx();
    #else
    add_arg_t* args = (add_arg_t*) arg;
    int i = blockIdx * blockDim + threadIdx;
    #endif

    args->out[i] = args->a[i] + args->b[i];
}