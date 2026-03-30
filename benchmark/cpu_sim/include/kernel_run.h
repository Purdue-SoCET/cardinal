#include "cpu_kernel.h"

// Defines
#define MEMORY_SIZE (1024ULL * 1024ULL * 1024ULL * 4ULL) // 4GB using 64-bit math
#define STACK_SIZE (MEMORY_SIZE/4) // Assume 1/4 of memory is consumed by stack for now
#define TEXT_SIZE (MEMORY_SIZE/8) // Assume 1/4 of memory is consumed by text for now


// Types
typedef void (*kernel_ptr_t)(void*);

// Function Headers
void run_kernel(kernel_ptr_t, int, int, void*);
void createPPMFile(char*, int*, int, int);