#include "include/kernel.h"
#include "include/lavaMD.h"

//Adopted from https://github.com/utcs-scea/altis/blob/master/src/cuda/level2/lavamd/kernel/kernel_gpu_cuda.cu

// Fast approximation of exp(-x) with (2x2) Padé Approximant
#define FAST_EXP_NEG(x) ( (12.0 - 6.0*(x) + (x)*(x)) / (12.0 + 6.0*(x) + (x)*(x)) )

// Formula: rA.v + rB.v - (rA.x*rB.x + rA.y*rB.y + rA.z*rB.z)
#define DOT(a, b) ((a).x * (b).x + (a).y * (b).y + (a).z * (b).z)

#ifdef GPU_SIM
void main(void* arg)
#else
void kernel_lavaMD_calc(void* args) 
#endif
{
    #ifdef GPU_SIM
    lavaMD_kernel_arg_t* kernel_args = (lavaMD_kernel_arg_t*)argPtr();
    int bx = blockIdx();
    int tx = threadIdx();
    #else
    lavaMD_kernel_arg_t* kernel_args = (lavaMD_kernel_arg_t*)args;
    int bx = blockIdx;
    int tx = threadIdx;
    #endif

    if (bx >= kernel_args->dim.number_boxes) return;

    // Identify Home Particle
    int first_i = kernel_args->box[bx].offset;
    int my_particle_idx = first_i + tx;
    if (tx >= NUMBER_PAR_PER_BOX) return;

    // Load Home Particle
    four_vec my_pos = kernel_args->rv[my_particle_idx];
    float a2 = 2.0 * kernel_args->alpha * kernel_args->alpha;

    float acc_v = 0, acc_x = 0, acc_y = 0, acc_z = 0;

    // Neighbor Box Loop 
    for (int k = 0; k < (1 + kernel_args->box[bx].nn); k++) {
        int pointer;
        if (k == 0) {
            pointer = bx;
        } else {
            pointer = kernel_args->box[bx].nei[k-1].number;
        }
        int first_j = kernel_args->box[pointer].offset;

        four_vec* rB_ptr = &kernel_args->rv[first_j];
        float* qB_ptr = &kernel_args->qv[first_j];

        // Calculate interactions with all particles in the current neighbor box
        for (int j = 0; j < NUMBER_PAR_PER_BOX; j++) {
            four_vec n_pos = rB_ptr[j];
            float n_q = qB_ptr[j];

            float r2 = my_pos.v + n_pos.v - DOT(my_pos, n_pos);
            float u2 = a2 * r2;
            float vij = FAST_EXP_NEG(u2);  // exp(-u2) 
            float fs = 2.0 * vij;

            float dx = my_pos.x - n_pos.x;
            float dy = my_pos.y - n_pos.y;
            float dz = my_pos.z - n_pos.z;

            acc_v += n_q * vij;
            acc_x += n_q * fs * dx;
            acc_y += n_q * fs * dy;
            acc_z += n_q * fs * dz;
        }
    }

    kernel_args->fv[my_particle_idx].v = acc_v;
    kernel_args->fv[my_particle_idx].x = acc_x;
    kernel_args->fv[my_particle_idx].y = acc_y;
    kernel_args->fv[my_particle_idx].z = acc_z;
}