#include "include/kernel_run.h"
#include "include/cpu_kernel.h"

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

// Global Vars
int blockIdx; // Current block in the larger grid
int blockDim; // Dimensions
int threadIdx; // Current thread in the block

void run_kernel(kernel_ptr_t kernel, int grid_dim, int block_dim, void* args) {
    blockDim = block_dim;
    // Iterate through grids
    for(blockIdx = 0; blockIdx < grid_dim; blockIdx++) {
        for(threadIdx = 0; threadIdx < block_dim; threadIdx++) {
            // printf("Launching kernel %d\n", threadIdx);
            kernel(args);
        }
    }
}

void createPPMFile(char* fileName, int* pixels, int width, int height) {
    FILE* file = fopen(fileName, "w");

    if (!file) {
        printf("Could not open file %s\n", fileName);
        perror("fopen");
        return;
    }
    
    fputs("P3\n", file);
    fprintf(file, "%d %d\n", width, height);
    fputs("255\n", file);

    char R[4], G[4], B[4];

    for(int i = 0; i < height; i++){     // Top to Bottom
        for(int j = 0; j < width; j++){ // Left to Right
            int idx = width * 3 * i + 3 * j;
                sprintf(R, "%d", pixels[idx + 0]);
                sprintf(G, "%d", pixels[idx + 1]);
                sprintf(B, "%d", pixels[idx + 2]);
                fputs(R, file);
                fputs(" ", file);
                fputs(G, file);
                fputs(" ", file);
                fputs(B, file);
                fputs("\n", file);
        }
    }
    fclose(file);
}
