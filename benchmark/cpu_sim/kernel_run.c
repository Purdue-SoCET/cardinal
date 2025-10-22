#include "include/kernel_run.h"
#include "include/cpu_kernel.h"

#include <stdio.h>

// Global Vars
dim_t blockIdx; // Current block in the larger grid
dim_t blockDim; // Dimensions of each block
dim_t threadIdx; // Current thread in the block

void run_kernel(kernel_ptr_t kernel, dim_t grid_dim, dim_t block_dim, void* args) {
    blockDim = block_dim;

    // Iterate through grids
    for(int x = 0; x < grid_dim.x; x++) {
        for(int y = 0; y < grid_dim.y; y++) {
            for(int z = 0; z < grid_dim.z; z++) {
                // assign blockIdx
                blockIdx.x = x; blockIdx.y = y; blockIdx.z = z;

                // Iterate through threads
                for(int gx = 0; gx < block_dim.x; gx++) {
                    for(int gy = 0; gy < block_dim.y; gy++) {
                        for(int gz = 0; gz < block_dim.z; gz++) {
                            threadIdx.x = gx; threadIdx.y = gy; threadIdx.z = gz;
                            kernel(args);
                        }
                    }
                }
            }
        }
    }
}