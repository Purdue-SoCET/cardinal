// CPU kernel simulator

#ifdef CPU_SIM
#include "../../cpu_sim/include/cpu_kernel.h"
#include <stdio.h>
#include <math.h>

extern int blockIdx;
extern int blockDim;
extern int threadIdx;

#define isqrt(x) (1 / sqrt(x))

#define mod(a, b) ((a) % (b))

#endif

#ifdef GPU_SIM
// Functions
extern float cos(float);
extern float sin(float);
extern int ftoi(float);
extern float itof(int);
extern float isqrt(float);

extern int blockIdx();
extern int blockDim();
extern int threadIdx();

#define threadIdx (ThreadIdx())
#define blockDim (blockDim())
#define blockIdx (blockIdx())

#define mod(a, b) (a - b*(a/b))
#endif