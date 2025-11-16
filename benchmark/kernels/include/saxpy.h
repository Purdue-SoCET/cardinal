#pragma once

typedef struct {
    int n;
    float a;
    float *x;
    float *y;
} saxpy_arg_t;

void kernel_saxpy(void*);