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
#include <assert.h>
#include <stdbool.h>

#include "include/kernel_run.h"
#include "include/shader_memdump.h"
#include "include/graphics_lib.h"

// Include needed kernels
#include "../kernels/include/lavaMD.h"

// --- Configuration ---
#define ARGS_BASE_ADDR 0x00100000
#define HEAP_BASE_ADDR 0x10000000

#define THREAD_BLOCK_SIZE 128
#define NUMBER_PAR_PER_BOX 100
#define BOX_DIM 1
#define NUMBER_PASSES 1

// Toggle memory dumps
#define INPUT_MEM_DUMP 1
#define OUTPUT_MEM_DUMP 1

// --- Macro Toolkit ---
#define ALLOCATE_ARGS(dest, type, num) \
    type* dest = (type*) args_ptr; \
    args_ptr += (num) * sizeof(type);

#define ALLOCATE_HEAP(dest, type, num) \
    type* dest = (type*) heap_ptr; \
    heap_ptr += (num) * sizeof(type);

// --- Original Helper Functions ---

void init_particles(dim_str dim, box_str* boxes, four_vec* rv, float* qv) {
    int total_boxes = dim.boxes1d_arg * dim.boxes1d_arg * dim.boxes1d_arg;
    int total_particles = total_boxes * NUMBER_PAR_PER_BOX;

    // Neighbor/Box Metadata Initialization
    int nh = 0;
    for (int i = 0; i < dim.boxes1d_arg; i++) {
        for (int j = 0; j < dim.boxes1d_arg; j++) {
            for (int k = 0; k < dim.boxes1d_arg; k++) {
                boxes[nh].x = k; boxes[nh].y = j; boxes[nh].z = i;
                boxes[nh].number = nh;
                boxes[nh].offset = nh * NUMBER_PAR_PER_BOX;
                boxes[nh].nn = 0;

                for (int l = -1; l <= 1; l++) {
                    for (int m = -1; m <= 1; m++) {
                        for (int n = -1; n <= 1; n++) {
                            int nx = k + n; int ny = j + m; int nz = i + l;
                            if (l == 0 && m == 0 && n == 0) continue;
                            if (nx >= 0 && nx < dim.boxes1d_arg && 
                                ny >= 0 && ny < dim.boxes1d_arg && 
                                nz >= 0 && nz < dim.boxes1d_arg) {
                                
                                int nei_idx = boxes[nh].nn;
                                int nei_num = (nz * dim.boxes1d_arg * dim.boxes1d_arg) + 
                                              (ny * dim.boxes1d_arg) + nx;
                                boxes[nh].nei[nei_idx].number = nei_num;
                                boxes[nh].nei[nei_idx].offset = nei_num * NUMBER_PAR_PER_BOX;
                                boxes[nh].nn++;
                            }
                        }
                    }
                }
                nh++;
            }
        }
    }

    // Global Position/Charge Generation
    srand(0); 
    for (int idx = 0; idx < total_particles; idx++) {
        rv[idx].v = (float)(rand() % 10 + 1) / 10.0;
        rv[idx].x = (float)(rand() % 10 + 1) / 10.0;
        rv[idx].y = (float)(rand() % 10 + 1) / 10.0;
        rv[idx].z = (float)(rand() % 10 + 1) / 10.0;
    }
    for (int idx = 0; idx < total_particles; idx++) {
        qv[idx] = (float)(rand() % 10 + 1) / 10.0;
    }
}

void save_text(four_vec* data, int count, const char* filename) {
    FILE* fp = fopen(filename, "w"); 
    if (fp == NULL) {
        printf("error: failed to open %s\n", filename);
        return;
    }
    for (int i = 0; i < count; ++i) {
        fprintf(fp, "%f, %f, %f, %f\n", data[i].v, data[i].x, data[i].y, data[i].z);
    }
    fclose(fp);
}

// --- Main CPU Sim ---

int main(int argc, char** argv) {
    // Silence unused parameter warnings
    (void)argc;
    (void)argv;

    uint8_t *args_ptr, *heap_ptr;
    uint8_t *args_start_ptr, *heap_start_ptr;

    // 1. Map Argument and Heap space to specific addresses
    size_t args_size = 15 * 1024 * 1024;
    size_t heap_size = 256 * 1024 * 1024;

    args_start_ptr = mmap((void*)ARGS_BASE_ADDR, args_size, 
                          PROT_READ | PROT_WRITE, 
                          MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, 
                          -1, 0);

    heap_start_ptr = mmap((void*)HEAP_BASE_ADDR, heap_size, 
                          PROT_READ | PROT_WRITE, 
                          MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, 
                          -1, 0);

    if (args_start_ptr == MAP_FAILED || heap_start_ptr == MAP_FAILED) {
        fprintf(stderr, "mmap failed! OS Error: %s\n", strerror(errno));
        return -1;
    }

    // Set rolling pointers for ALLOCATE macros
    args_ptr = args_start_ptr;
    heap_ptr = heap_start_ptr;

    // 2. Setup Dimensions
    dim_str dim;
    dim.boxes1d_arg = BOX_DIM;
    dim.number_boxes = (float)(dim.boxes1d_arg * dim.boxes1d_arg * dim.boxes1d_arg);
    int num_boxes = (int)dim.number_boxes;
    int num_particles = num_boxes * NUMBER_PAR_PER_BOX;

    // 3. Allocate Memory on Heap
    ALLOCATE_HEAP(d_box, box_str, num_boxes);
    ALLOCATE_HEAP(d_rv,  four_vec, num_particles);
    ALLOCATE_HEAP(d_qv,  float,    num_particles);
    ALLOCATE_HEAP(d_fv,  four_vec, num_particles);

    // 4. Initialize Input Data
    printf("Initializing %d particles...\n", num_particles);
    init_particles(dim, d_box, d_rv, d_qv);

    // 5. Setup Kernel Arguments
    lavaMD_kernel_arg_t* args;
    ALLOCATE_ARGS(args_mem, lavaMD_kernel_arg_t, 1);
    args = args_mem;

    args->alpha = 0.5f;
    args->dim = dim; 
    args->box = d_box;
    args->rv = d_rv;
    args->qv = d_qv;
    args->fv = d_fv;

    // Calculate current allocated sizes for dumping
    size_t current_args_bytes = (uintptr_t)args_ptr - (uintptr_t)args_start_ptr;
    size_t current_heap_bytes = (uintptr_t)heap_ptr - (uintptr_t)heap_start_ptr;

    // 6. Execution Loop
    for(int p = 0; p < NUMBER_PASSES; p++) {
        printf("\n--- Pass %d ---\n", p);

        // --- Step A: Reset Force Vectors (INIT between calls) ---
        printf("Reseting Force Vectors to 0.0f...\n");
        for(int i = 0; i < num_particles; i++) {
            args->fv[i].v = 0.0f; args->fv[i].x = 0.0f;
            args->fv[i].y = 0.0f; args->fv[i].z = 0.0f;
        }

        // --- Step B: Pre-Run Memory Dump ---
        if(INPUT_MEM_DUMP){
            char filename_args[50] = "build/mem_dump/lavaMDInput_args_dump.txt";
            char filename_heap[50] = "build/mem_dump/lavaMDInput_heap_dump.txt";
            //sprintf(filename_args, "build/mem_dump/lavaMDInput%d_args_dump.txt", p); 
            //sprintf(filename_heap, "build/mem_dump/lavaMDInput%d_heap_dump.txt", p); 
            dump_memory(filename_args, args_start_ptr, ARGS_BASE_ADDR, (uint32_t)current_args_bytes);
            dump_memory(filename_heap, heap_start_ptr, HEAP_BASE_ADDR, (uint32_t)current_heap_bytes);
        }

        // --- Step C: Kernel Execution ---
        printf("Launching Calculation Kernel...\n");
        run_kernel(kernel_lavaMD, num_boxes, THREAD_BLOCK_SIZE, (void*)args);

        FILE* file_thread = fopen("build/threads/lavaMDThreads.txt", "w");
        if (file_thread) {
            fprintf(file_thread, "Grid Dim: %d, Block Dim: %d\n", num_boxes, THREAD_BLOCK_SIZE);
            fclose(file_thread);
        } else {
            printf("Warning: Could not open threads file for writing.\n");
        }

        // --- Step D: Post-Run Memory Dump ---
        if(OUTPUT_MEM_DUMP){
            char filename_args[50] = "build/mem_dump/lavaMDOutput_args_dump.txt";
            char filename_heap[50] = "build/mem_dump/lavaMDOutput_heap_dump.txt";
            //sprintf(filename_args, "build/mem_dump/lavaMDOutput%d_args_dump.txt", p); 
            //sprintf(filename_heap, "build/mem_dump/lavaMDOutput%d_heap_dump.txt", p); 
            dump_memory(filename_args, args_start_ptr, ARGS_BASE_ADDR, (uint32_t)current_args_bytes);
            dump_memory(filename_heap, heap_start_ptr, HEAP_BASE_ADDR, (uint32_t)current_heap_bytes);
        }
    }

    // 7. Save Final Result to file
    printf("\nSaving output to build/result.txt...\n");
    save_text(args->fv, num_particles, "build/result.txt");

    // 8. Cleanup
    munmap((void*)args_start_ptr, args_size);
    munmap((void*)heap_start_ptr, heap_size);

    printf("Done.\n");
    return 0;
}