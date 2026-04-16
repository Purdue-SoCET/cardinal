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

// Include all needed kernels
#include "../kernels/include/gemm.h"

#define ARGS_BASE_ADDR 0x00100000
#define HEAP_BASE_ADDR 0x10000000

#define INPUT_MEM_DUMP 1
#define OUTPUT_MEM_DUMP 1

uint8_t* memory_base;
uint8_t* memory_ptr;

#define ALLOCATE_MEM(dest, type, num) \
    type* dest = (type*) memory_ptr; \
    memory_ptr += num * sizeof(type);

#define ALLOCATE_ARGS(dest, type, num) \
    type* dest = (type*) args_ptr; \
    args_ptr += (num) * sizeof(type);

#define ALLOCATE_HEAP(dest, type, num) \
    type* dest = (type*) heap_ptr; \
    heap_ptr += (num) * sizeof(type);


// --- Helper Functions ---
static void generate_float_matrix(float* m, int rows, int cols) {
    for (int i = 0; i < rows; ++i) {
        for (int j = 0; j < cols; ++j) {
            m[i * cols + j] = (float)((i * cols + j) % 97) / 97.0f; // random number between 0 and 1
        }
    }
}

static void cpu_reference(const float* A, const float* B, float* C, int M, int N, int K) {
    for (int i = 0; i < M; ++i) {
        for (int j = 0; j < N; ++j) {
            float sum = 0.0f;
            for (int k = 0; k < K; ++k) {
                sum += A[i * K + k] * B[k * N + j];
            }
            C[i * N + j] = sum;
        }
    }
}

void save_binary(float* data, int count, const char* filename) {
    FILE* fp = fopen(filename, "wb");
    if (fp == NULL) {
        printf("error: failed to open %s for binary write\n", filename);
        return;
    }
    int written = fwrite(data, sizeof(float), count, fp);
    if (written != count) {
        printf("Error: write counting wrong for %s\n", filename);
    }
    fclose(fp);
}

void save_text(float* data, int M, int N, const char* filename) {
    FILE* fp = fopen(filename, "w"); 
    if (fp == NULL) {
        printf("error: failed to open %s for text write\n", filename);
        return;
    }
    for (int i = 0; i < M; ++i) {
        for (int j = 0; j < N; ++j) {
            fprintf(fp, "%.4f ", data[i * N + j]); // print with 4 decimal places
        }
        fprintf(fp, "\n");
    }
    fclose(fp);
}

// --- Main CPU Sim ---
int main(int argc, char** argv) {
    uint8_t* args_ptr;
    uint8_t* heap_ptr;

    // 1. Map the Arguments Space (Starts at 0x00100000, size ~15MB)
    size_t args_size = 15 * 1024 * 1024;
    args_ptr = mmap((void*)0x00100000, args_size, 
                             PROT_READ | PROT_WRITE, 
                             MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, 
                             -1, 0);

    // 2. Map the Heap Space (Starts at 0x10000000, size ~256MB)
    size_t heap_size = 256 * 1024 * 1024;
    heap_ptr = mmap((void*)0x10000000, heap_size, 
                             PROT_READ | PROT_WRITE, 
                             MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, 
                             -1, 0);

    if (args_ptr == MAP_FAILED || heap_ptr == MAP_FAILED) {
        fprintf(stderr, "mmap failed! OS refused to give us those exact addresses. Error: %s\n", strerror(errno));
        return -1;
    }

    printf("Successfully forced Arguments to %p and Heap to %p\n", args_ptr, heap_ptr);

    // Matrix dimensions
    const int M = 32;
    const int N = 32;
    const int K = 32;

    // Allocate simulated GPU memory
    ALLOCATE_HEAP(A, float, M * K);
    ALLOCATE_HEAP(B, float, K * N);
    ALLOCATE_HEAP(C, float, M * N);

    // Allocate standard CPU memory for reference checking
    float* C_ref = (float*)malloc(sizeof(float) * M * N);

    if (!A || !B || !C || !C_ref) {
        printf("Memory allocation failed\n");
        return 1;
    }

    // Initialize matrices
    generate_float_matrix(A, M, K);
    generate_float_matrix(B, K, N);
    memset(C, 0, sizeof(float) * M * N);

    // Setup Arguments
    gemm_arg_t* args;
    ALLOCATE_ARGS(args_mem, gemm_arg_t, 1);
    args = args_mem;
    
    args->M = M;
    args->N = N;
    args->K = K;
    args->A = A;
    args->B = B;
    args->C = C;

    // Dump Input Memory
    if(INPUT_MEM_DUMP){
        size_t current_args_bytes = (size_t)args_ptr - (ARGS_BASE_ADDR);
        size_t current_heap_bytes = (size_t)heap_ptr - (HEAP_BASE_ADDR);
        dump_memory("build/mem_dump/gemmInput_args_dump.txt", (uint8_t*)ARGS_BASE_ADDR, (uint32_t)ARGS_BASE_ADDR, current_args_bytes);
        dump_memory("build/mem_dump/gemmInput_heap_dump.txt", (uint8_t*)HEAP_BASE_ADDR, (uint32_t)HEAP_BASE_ADDR, current_heap_bytes);
    }

    // Run Kernel
    int total = M * N;
    int block_dim = 32;
    int grid_dim = (total + block_dim - 1) / block_dim;

    {
        run_kernel(kernel_gemm, grid_dim, block_dim, (void*)args);
        
        // Dump Thread Config
        FILE* file_thread = fopen("build/threads/gemmThreads.txt", "w");
        if (file_thread) {
            fprintf(file_thread, "Grid Dim: %d, Block Dim: %d\n", grid_dim, block_dim);
            fclose(file_thread);
        } else {
            printf("Warning: Could not open threads file for writing.\n");
        }
    }

    // Dump Output Memory
    if(OUTPUT_MEM_DUMP){
        size_t current_args_bytes = (size_t)args_ptr - (ARGS_BASE_ADDR);
        size_t current_heap_bytes = (size_t)heap_ptr - (HEAP_BASE_ADDR);
        dump_memory("build/mem_dump/gemmOutput_args_dump.txt", (uint8_t*)ARGS_BASE_ADDR, (uint32_t)ARGS_BASE_ADDR, current_args_bytes);
        dump_memory("build/mem_dump/gemmOutput_heap_dump.txt", (uint8_t*)HEAP_BASE_ADDR, (uint32_t)HEAP_BASE_ADDR, current_heap_bytes);
    }

    // Run CPU Reference
    cpu_reference(A, B, C_ref, M, N, K);

    // Compare Outputs
    int pass = 1;
    for (int i = 0; i < total; ++i) {
        if(C[i] != C_ref[i]) {
            printf("gemm cpu sim failed at index %d (Expected: %f, Got: %f)\n", i, C_ref[i], C[i]);
            pass = 0;
            break;
        }
    }
    if (pass) {
        printf("gemm cpu sim pass\n");
    }

    // Write to text files
    save_text(A, M, K, "matrix_a.txt"); 
    save_text(B, K, N, "matrix_b.txt");
    save_text(C_ref, M, N, "matrix_c_output.txt");

    // Write to binary files
    save_binary(A, M * K, "matrix_a.bin");
    save_binary(B, K * N, "matrix_b.bin");
    save_binary(C_ref, M * N, "matrix_c_output.bin");

    // Clean up
    free(C_ref);
    munmap((void*)0x00100000, args_size);
    munmap((void*)0x10000000, heap_size);

    return 0;
}