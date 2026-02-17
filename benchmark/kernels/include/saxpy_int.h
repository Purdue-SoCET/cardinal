#ifndef SAXPY_INT_H
#define SAXPY_INT_H

typedef struct {
    int n;
    int a;
    int *x;
    int *y;
} saxpy_arg_t;

void kernel_saxpy_int(void*);

#endif