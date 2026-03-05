#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <assert.h>
#include <stdbool.h>
#include "include/kernel_run.h"
#include "../kernels/include/lavaMD.h"

#define THREAD_BLOCK_SIZE 128
#define NUMBER_PAR_PER_BOX 100
#define BOX_DIM 1

#define INPUT_DEBUG 0

void init_particles(dim_str dim, box_str* boxes, four_vec* rv, float* qv) {
    int total_boxes = dim.boxes1d_arg * dim.boxes1d_arg * dim.boxes1d_arg;
    int total_particles = total_boxes * NUMBER_PAR_PER_BOX;

    // Metadata & Neighbors 
    int nh = 0;
    for (int i = 0; i < dim.boxes1d_arg; i++) {
        for (int j = 0; j < dim.boxes1d_arg; j++) {
            for (int k = 0; k < dim.boxes1d_arg; k++) {
                boxes[nh].x = k;
                boxes[nh].y = j;
                boxes[nh].z = i;
                boxes[nh].number = nh;
                boxes[nh].offset = nh * NUMBER_PAR_PER_BOX;
                boxes[nh].nn = 0;

                for (int l = -1; l <= 1; l++) {
                    for (int m = -1; m <= 1; m++) {
                        for (int n = -1; n <= 1; n++) {
                            int nx = k + n;
                            int ny = j + m;
                            int nz = i + l;
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

    // Global Position Generation 
    // Altis calls srand(0) and then fills ALL rv vectors first
    srand(0); 
    for (int idx = 0; idx < total_particles; idx++) {
        rv[idx].v = (float)(rand() % 10 + 1) / 10.0;
        rv[idx].x = (float)(rand() % 10 + 1) / 10.0;
        rv[idx].y = (float)(rand() % 10 + 1) / 10.0;
        rv[idx].z = (float)(rand() % 10 + 1) / 10.0;
    }

    if(BOX_DIM != 1) srand(1); //Added to match Atlis rand()
    
    // Global Charge Generation 
    // Altis fills ALL qv values after ALL rv values
    for (int idx = 0; idx < total_particles; idx++) {
        qv[idx] = (float)(rand() % 10 + 1) / 10.0;
    }

    // --- Debug Output ---
    if (INPUT_DEBUG) {
        FILE *finput = fopen("build/lavaMD_inputs_debug.txt", "w");
        if (finput) {
            fprintf(finput, "Index | Distances (x, y, z, v) | Charge\n");
            for (int idx = 0; idx < total_particles; idx++) {
                fprintf(finput, "%d | %f %f %f %f | %f\n", 
                        idx, rv[idx].x, rv[idx].y, rv[idx].z, rv[idx].v, qv[idx]);
            }
            fclose(finput);
        }
    }
}

int main() {
    dim_str dim;
    dim.boxes1d_arg = BOX_DIM;
    dim.number_boxes = (float)(dim.boxes1d_arg * dim.boxes1d_arg * dim.boxes1d_arg);
    int num_boxes = (int)dim.number_boxes;
    int num_particles = num_boxes * NUMBER_PAR_PER_BOX;
    float alpha = 0.5f;

    size_t boxes_sz = num_boxes * sizeof(box_str);
    size_t rv_sz    = num_particles * sizeof(four_vec);
    size_t qv_sz    = num_particles * sizeof(float);
    size_t fv_sz    = num_particles * sizeof(four_vec);

    size_t total_sz = boxes_sz + rv_sz + qv_sz + fv_sz;
    uint8_t* mem_space = (uint8_t*)malloc(total_sz);
    if (!mem_space) {
        fprintf(stderr, "Memory allocation failed!\n");
        return 1;
    }
    memset(mem_space, 0, total_sz);

    box_str* d_box   = (box_str*) mem_space;
    four_vec* d_rv   = (four_vec*) (mem_space + boxes_sz);
    float* d_qv      = (float*)    (mem_space + boxes_sz + rv_sz);
    four_vec* d_fv   = (four_vec*) (mem_space + boxes_sz + rv_sz + qv_sz);

    printf("Initializing %d particles across %d boxes...\n", num_particles, num_boxes);
    init_particles(dim, d_box, d_rv, d_qv); 

    lavaMD_kernel_arg_t args;
    args.alpha = alpha;
    args.dim = dim; 
    args.box = d_box;
    args.rv = d_rv;
    args.qv = d_qv;
    args.fv = d_fv;

    int grid = num_boxes;
    int block = THREAD_BLOCK_SIZE; 

    printf("Launching Initialization Kernel ...\n");
    run_kernel(kernel_lavaMD_init, grid, block, (void*)&args);

    printf("Launching Calculation Kernel ...\n");
    run_kernel(kernel_lavaMD_calc, grid, block, (void*)&args);

    printf("\nLavaMD Completed.\n");

    char outfile[30] = "build/result.txt";
    if (outfile != "") {
        FILE *fptr;
        fptr = fopen(outfile, "w");	
        for(int i=0; i<NUMBER_PAR_PER_BOX; i=i+1){
            fprintf(fptr, "%f, %f, %f, %f\n", args.fv[i].v, args.fv[i].x, args.fv[i].y, args.fv[i].z);
        }
        fclose(fptr);
    }

    free(mem_space);
    return 0;
}