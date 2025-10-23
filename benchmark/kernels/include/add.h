#pragma once

typedef struct {
    int* a;
    int* b;
    int* out;
} add_arg_t;

void kernel_add(void*);