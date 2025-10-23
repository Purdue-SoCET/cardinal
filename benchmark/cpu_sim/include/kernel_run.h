#include "cpu_kernel.h"

// Types
typedef void (*kernel_ptr_t)(void*);

// Function Headers
void run_kernel(kernel_ptr_t, dim_t, dim_t, void*);