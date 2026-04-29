#include "include/kernel.h"
#include "include/lavaMD.h"

//Adopted from https://github.com/utcs-scea/altis/blob/master/src/cuda/level2/lavamd/kernel/kernel_gpu_cuda.cu

// Fast approximation of exp(-x) with (2x2) Padé Approximant
#define FAST_EXP_NEG(x) ( (12.0f - 6.0f*(x) + (x)*(x)) / (12.0f + 6.0f*(x) + (x)*(x)) )

// Formula: rA.v + rB.v - (rA.x*rB.x + rA.y*rB.y + rA.z*rB.z)
#define DOT(a, b) ((a).x * (b).x + (a).y * (b).y + (a).z * (b).z)
#ifdef GPU_SIM
void kernel_lavaMD_init()
#else
void kernel_lavaMD_init(void* arg)
#endif
{
    #ifdef GPU_SIM
    lavaMD_kernel_arg_t* kernel_args = (lavaMD_kernel_arg_t*)argPtr();
    #else
    lavaMD_kernel_arg_t* kernel_args = (lavaMD_kernel_arg_t*)args;
    #endif

    int bx = blockIdx;
    int tx = threadIdx;

    if (bx < kernel_args->dim.number_boxes){
        int first_i = kernel_args->box[bx].offset;
        int my_particle_idx = first_i + tx;

        // Boundary check for particles in the box
        if (tx < NUMBER_PAR_PER_BOX) {
            kernel_args->fv[my_particle_idx].v = 0.0;
            kernel_args->fv[my_particle_idx].x = 0.0;
            kernel_args->fv[my_particle_idx].y = 0.0;
            kernel_args->fv[my_particle_idx].z = 0.0;
        }
    }
}
