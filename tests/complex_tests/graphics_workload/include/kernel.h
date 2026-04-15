// CPU kernel simulator
#ifndef KERNEL_H
#define KERNEL_H

#ifdef CPU_SIM
#include "../../cpu_sim/include/cpu_kernel.h"
#include <stdio.h>
#include <math.h>

extern int blockIdx;
extern int blockDim;
extern int threadIdx;

#define isqrt(x) (1 / sqrt(x))
#define mod(a, b) ((a) % (b))
#define itof(i) ((float)(i))
#define ftoi(f) ((int)(f))

#endif

#ifndef CPU_SIM
// Functions
extern float cos(float);
extern float sin(float);
extern int ftoi(float);
extern float itof(int);
extern float isqrt(float);

extern int blockIdx();
extern int blockDim();
extern int threadIdx();
extern void* argPtr();

#define mod(a, b) ((a) - (b)*((a)/(b)))
#define threadIdx (threadIdx())
#define blockDim (blockDim())
#define blockIdx (blockIdx())

#endif

#endif