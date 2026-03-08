#ifndef MONTE_CARLO_PI_H
#define MONTE_CARLO_PI_H

// Philox Constants
#define PHILOX_M 0xD2511F53 
#define WEYL_C   0x9E3779B9
#define V1_INIT  0x12345678

#define low_part(x)  ((x) & 0xFFFF)
#define high_part(x) (((x) >> 16) & 0xFFFF)

typedef struct {
    int low;
    int high;
} int_pair_t;

typedef struct {
    int **circle_points;
    int base_seed;
    int num_points;
} monte_carlo_pi_arg_t;

void kernel_monte_carlo_pi(void*);

#endif