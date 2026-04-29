#ifndef SAXPY_H
#define SAXPY_H

typedef struct {
    int n;
    float a;
    float *x;
    float *y;
} saxpy_arg_t;

#ifdef GPU_SIM
void kernel_saxpy();
#else
void kernel_saxpy(void* arg);
#endif

#endif