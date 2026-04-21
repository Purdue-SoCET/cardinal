// Standard Includes
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>
#include <time.h>
#include <limits.h>
#include <sys/mman.h>
#include <errno.h>
#include <string.h>
#include <math.h>

#include "include/kernel_run.h"
#include "include/shader_memdump.h"
#include "include/graphics_lib.h"

// Include pathFinder kernel
#include "../kernels/include/pathFinder.h"

#define ARGS_BASE_ADDR 0x00100000
#define HEAP_BASE_ADDR 0x10000000

#define INPUT_MEM_DUMP 1
#define OUTPUT_MEM_DUMP 1

// Allocation Macros
#define ALLOCATE_ARGS(dest, type, num) \
    type* dest = (type*) args_ptr; \
    args_ptr += (num) * sizeof(type);

#define ALLOCATE_HEAP(dest, type, num) \
    type* dest = (type*) heap_ptr; \
    heap_ptr += (num) * sizeof(type);

// --- Helper Functions ---

static void cpu_reference_row(const int* input_row, const int* weight_row, int* out, int width) {
    for (int idx = 0; idx < width; ++idx) {
        int left = idx > 0 ? idx - 1 : idx;
        int right = idx + 1 < width ? idx + 1 : idx;

        int min_val = input_row[idx];
        if (input_row[left] < min_val) min_val = input_row[left];
        if (input_row[right] < min_val) min_val = input_row[right];

        out[idx] = min_val + weight_row[idx];
    }
}

void save_binary(int* data, int count, const char* filename) {
    FILE* fp = fopen(filename, "wb");
    if (fp == NULL) {
        printf("error: failed to open %s for binary write\n", filename);
        return;
    }
    fwrite(data, sizeof(int), count, fp);
    fclose(fp);
}

void save_text(int* data, int width, int height, const char* filename) {
    FILE* fp = fopen(filename, "w"); 
    if (fp == NULL) {
        printf("error: failed to open %s for text write\n", filename);
        return;
    }
    for (int i = 0; i < height; ++i) {
        for (int j = 0; j < width; ++j) {
            fprintf(fp, "%d ", data[i * width + j]);
        }
        fprintf(fp, "\n");
    }
    fclose(fp);
}

// --- Main CPU Sim ---
int main(int argc, char** argv) {
    uint8_t* args_ptr;
    uint8_t* heap_ptr;

    // 1. Map the Arguments Space
    size_t args_size = 15 * 1024 * 1024;
    args_ptr = mmap((void*)ARGS_BASE_ADDR, args_size, 
                             PROT_READ | PROT_WRITE, 
                             MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, 
                             -1, 0);

    // 2. Map the Heap Space
    size_t heap_size = 256 * 1024 * 1024;
    heap_ptr = mmap((void*)HEAP_BASE_ADDR, heap_size, 
                             PROT_READ | PROT_WRITE, 
                             MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, 
                             -1, 0);

    if (args_ptr == MAP_FAILED || heap_ptr == MAP_FAILED) {
        fprintf(stderr, "mmap failed! Error: %s\n", strerror(errno));
        return -1;
    }

    const int width = 128;
    const int height = 128;

    // Allocate simulated GPU memory from Heap
    ALLOCATE_HEAP(weights, int, width * height);
    ALLOCATE_HEAP(row_a, int, width);
    ALLOCATE_HEAP(row_b, int, width);
    
    // Allocate standard CPU memory for reference checking
    int* row_ref = (int*)malloc(sizeof(int) * width);

    // Initialize weights
    for (int r = 0; r < height; ++r) {
        for (int c = 0; c < width; ++c) {
            weights[r * width + c] = (r * 17 + c * 7) % 101;
        }
    }

    // Initialize first row as zeros
    memset(row_a, 0, sizeof(int) * width);
    int* prev_out = row_a;
    int* curr_out = row_b;

    // Setup Kernel Arguments in Mapped Args Space
    ALLOCATE_ARGS(args_mem, pathfinder_arg_t, 1);
    pathfinder_arg_t* args = args_mem;
    args->width = width;

    // Dump Input Memory before processing starts
    if(INPUT_MEM_DUMP){
        size_t current_args_bytes = (size_t)args_ptr - (ARGS_BASE_ADDR);
        size_t current_heap_bytes = (size_t)heap_ptr - (HEAP_BASE_ADDR);
        dump_memory("build/mem_dump/pathFinderInput_args_dump.txt", (uint8_t*)ARGS_BASE_ADDR, (uint32_t)ARGS_BASE_ADDR, current_args_bytes);
        dump_memory("build/mem_dump/pathFinderInput_heap_dump.txt", (uint8_t*)HEAP_BASE_ADDR, (uint32_t)HEAP_BASE_ADDR, current_heap_bytes);
    }

    int block_dim = 128;
    int grid_dim = (width + block_dim - 1) / block_dim;
    int mismatches = 0;

    // Main Row-by-Row Execution
    for (int r = 0; r < height; ++r) {
        int* weight_row = &weights[r * width];
        args->input_row = prev_out;
        args->current_row_weight = weight_row;
        args->output_row = curr_out;

        // Run Kernel Simulation
        run_kernel(kernel_pathFinder, grid_dim, block_dim, (void*)args);

        // Run CPU Reference for current row
        cpu_reference_row(prev_out, weight_row, row_ref, width);

        // Verification
        for (int i = 0; i < width; ++i) {
            if (curr_out[i] != row_ref[i]) {
                mismatches++;
            }
        }

        // Pointer swap for next iteration
        int* tmp = prev_out;
        prev_out = curr_out;
        curr_out = tmp;
    }

    // Dump Output Memory after all rows processed
    if(OUTPUT_MEM_DUMP){
        size_t current_args_bytes = (size_t)args_ptr - (ARGS_BASE_ADDR);
        size_t current_heap_bytes = (size_t)heap_ptr - (HEAP_BASE_ADDR);
        dump_memory("build/mem_dump/pathFinderOutput_args_dump.txt", (uint8_t*)ARGS_BASE_ADDR, (uint32_t)ARGS_BASE_ADDR, current_args_bytes);
        dump_memory("build/mem_dump/pathFinderOutput_heap_dump.txt", (uint8_t*)HEAP_BASE_ADDR, (uint32_t)HEAP_BASE_ADDR, current_heap_bytes);
    }

    // Write Thread Config
    FILE* file_thread = fopen("build/threads/pathFinderThreads.txt", "w");
    if (file_thread) {
        fprintf(file_thread, "Grid Dim: %d, Block Dim: %d\n", grid_dim, block_dim);
        fclose(file_thread);
    }

    if (mismatches == 0) {
        printf("pathFinder cpu sim pass (%dx%d)\n", height, width);
    } else {
        printf("pathFinder cpu sim failed with %d mismatches\n", mismatches);
    }

    // Save final state results (last row is in prev_out due to final swap)
    save_text(weights, width, height, "pf_weights.txt");
    save_text(prev_out, width, 1, "pf_final_row.txt");
    save_binary(weights, width * height, "pf_weights.bin");
    save_binary(prev_out, width, "pf_final_row.bin");

    // Clean up
    free(row_ref);
    munmap((void*)ARGS_BASE_ADDR, args_size);
    munmap((void*)HEAP_BASE_ADDR, heap_size);

    return mismatches == 0 ? 0 : 1;
}