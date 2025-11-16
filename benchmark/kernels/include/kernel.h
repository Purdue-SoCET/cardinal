#ifndef KERNEL_H
#define KERNEL_H 0

// CPU kernel simulator
#ifdef CPU_SIM
#include "../../cpu_sim/include/cpu_kernel.h"
#include <stdio.h>

extern dim_t blockIdx;
extern dim_t blockDim;
extern dim_t threadIdx;
#endif

#endif