#include "include/kernel.h"
#include "include/monte_carlo_pi.h"

// From https://gist.github.com/reedacartwright/5406a00225c7508f5e9d3c47604d460d
#define MULTIPLY32X32(a, b, res_low, res_high) { \
    int _x0 = low_part(a) * low_part(b); \
    int _x1 = low_part(a) * high_part(b); \
    int _x2 = high_part(a) * low_part(b); \
    int _x3 = high_part(a) * high_part(b); \
    _x1 += high_part(_x0); \
    _x1 += low_part(_x2); \
    res_low = low_part(_x0) + (low_part(_x1) << 16); \
    res_high = _x3 + high_part(_x1) + high_part(_x2); \
}

#define PHILOX_ROUND(v0, v1, key) { \
    unsigned int _hi, _lo; \
    MULTIPLY32X32(v0, PHILOX_M, _lo, _hi); \
    unsigned int _new_v0 = (v1) ^ _hi ^ (key); \
    v0 = _new_v0; \
    v1 = _lo; \
}

// Generate a pair of random floats in [0,1) using Philox (https://dl.acm.org/doi/epdf/10.1145/2063384.2063405)
#define GET_RANDOM_PAIR(counter_index, seed, out_x, out_y) { \
    unsigned int _v0 = (counter_index); \
    unsigned int _v1 = V1_INIT; \
    unsigned int _key = (seed); \
    for (int _j = 0; _j < 10; _j++) { \
        PHILOX_ROUND(_v0, _v1, _key); \
        _key += WEYL_C; \
    } \
    out_x = (float)(_v0 & 0xFFFFFF) / 16777216.0; \
    out_y = (float)(_v1 & 0xFFFFFF) / 16777216.0; \
}

void kernel_monte_carlo_pi(void* arg) {
    monte_carlo_pi_arg_t* args = (monte_carlo_pi_arg_t*) arg;

    int i = blockIdx * blockDim + threadIdx;
    
    if (i >= args->num_points) {
        return;
    }

    float rand_x = 0.0;
    float rand_y = 0.0;

    GET_RANDOM_PAIR(i + args->base_seed, args->base_seed, rand_x, rand_y);

    float origin_dist = rand_x * rand_x + rand_y * rand_y;

    if (origin_dist <= 1.0){
        (*args->circle_points[i]) = 1;
    }

    return;
}