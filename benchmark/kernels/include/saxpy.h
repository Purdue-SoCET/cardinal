#ifndef SAXPY_H
#define SAXPY_H

typedef struct {
    int n;
    float a;
    float *x;
    float *y;
} saxpy_arg_t;

#ifdef GPU_SIM
void main(void* arg);
#else
void kernel_saxpy(void* arg);
#endif

#endif