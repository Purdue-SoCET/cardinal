#include "cpu_kernel.h"

// Defines
#define MEMORY_SIZE 2147483648*2 // Assuming 2GB for now
#define STACK_SIZE (MEMORY_SIZE/4) // Assume 1/4 of memory is consumed by stack for now
#define TEXT_SIZE (MEMORY_SIZE/8) // Assume 1/4 of memory is consumed by text for now

// Types
typedef void (*kernel_ptr_t)(void*);

// Function Headers
void run_kernel(kernel_ptr_t, dim_t, dim_t, void*);
void createPPMFile(char*, int*);