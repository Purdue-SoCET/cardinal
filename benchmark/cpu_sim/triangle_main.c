

#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include "include/kernel_run.h"

// Include all needed kernels
#include "../kernels/include/triangle.h"

// Macros
#define MAKE_VERTEX(Vs, idx, x, y, z) Vs[idx*3] = x; Vs[idx*3 + 1] = y; Vs[idx*3 + 2] = z;

kernel_ptr_t* kernel_functions;

int main() {
    // Test Constants
    int SCREEN_WIDTH = 5;
    int SCREEN_HEIGHT = 5;
    int NUM_PIXELS = SCREEN_WIDTH * SCREEN_HEIGHT;

    int NUM_VERTEX = 5;
    int NUM_TRI = 5;

    // Allocate Memory space
    int depth_buff_sz = sizeof(float) * NUM_PIXELS;
    int tag_buff_sz = sizeof(int) * NUM_PIXELS;
    int vertexs_sz = sizeof(float) * 3 * NUM_VERTEX;
    int mem_space_sz = depth_buff_sz + tag_buff_sz + vertexs_sz;

    uint8_t* mem_space = malloc(mem_space_sz);

    float* depth_buff = (float*) &mem_space[0];
    int* tag_buff = (int*)&mem_space[depth_buff_sz];
    float* verts = (float*)&mem_space[depth_buff_sz + tag_buff_sz];

    for(int i = 0; i < NUM_PIXELS; i++) { // Default depth and tags
        depth_buff[i] = -1;
        tag_buff[i] = 0;
    }

    // Manually defining 2D vertexs
    MAKE_VERTEX(verts, 0, 0, 0, 1.0f/1.0f);

    // Tri 1
    MAKE_VERTEX(verts, 1, 5.0f, 0.0f, 1.0f/2.0f);
    MAKE_VERTEX(verts, 2, 0.0f, 5.0f, 1.0f/2.0f);

    // Tri 2
    MAKE_VERTEX(verts, 3, 5.0f, 0.0f, 1.0f/2.0f);
    MAKE_VERTEX(verts, 4, 5.0f, 5.0f, 1.0f/9.0f);

    triangle_arg_t arg;
    arg.bb_start[0] = 0; arg.bb_start[1] = 0;
    arg.buff_w = SCREEN_WIDTH;
    arg.buff_h = SCREEN_HEIGHT;
    arg.depth_buff = depth_buff;
    arg.tag_buff = tag_buff;
    

    for(int tag = 0; tag < 2; tag++)
    {

        // Calculate bc_im
        arg.tag = tag+1;

        arg.pVs[0] = &verts[0];
        if(tag == 0) {
            arg.pVs[1] = &verts[1*3];
            arg.pVs[2] = &verts[2*3];
        } else {
            arg.pVs[1] = &verts[3*3];
            arg.pVs[2] = &verts[4*3];
        }

        // Matrix Inversion

        float m[3][3] = {
            {1, 1, 1},
            {arg.pVs[0][0], arg.pVs[1][0], arg.pVs[2][0]},
            {arg.pVs[0][1], arg.pVs[1][1], arg.pVs[2][1]}
        };

        double det = (double)m[0][0] * (m[1][1] * m[2][2] - m[2][1] * m[1][2]) -
                    (double)m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
                    (double)m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);

        double invDet = 1.0 / det;

        arg.bc_im[0][0] = (m[1][1] * m[2][2] - m[2][1] * m[1][2]) * invDet;
        arg.bc_im[0][1] = (m[0][2] * m[2][1] - m[0][1] * m[2][2]) * invDet;
        arg.bc_im[0][2] = (m[0][1] * m[1][2] - m[0][2] * m[1][1]) * invDet;
        
        arg.bc_im[1][0] = (m[1][2] * m[2][0] - m[1][0] * m[2][2]) * invDet;
        arg.bc_im[1][1] = (m[0][0] * m[2][2] - m[0][2] * m[2][0]) * invDet;
        arg.bc_im[1][2] = (m[0][2] * m[1][0] - m[0][0] * m[1][2]) * invDet;
        
        arg.bc_im[2][0] = (m[1][0] * m[2][1] - m[2][0] * m[1][1]) * invDet;
        arg.bc_im[2][1] = (m[2][0] * m[0][1] - m[0][0] * m[2][1]) * invDet;
        arg.bc_im[2][2] = (m[0][0] * m[1][1] - m[1][0] * m[0][1]) * invDet;

        // Call Kernel
        dim_t grid; grid.x = 1; grid.y = 1; grid.z = 1;
        dim_t block; block.x = SCREEN_WIDTH; block.y = SCREEN_HEIGHT; block.z = 1;
        run_kernel(kernel_triangle, grid, block, (void*)&arg);
    }


    for(int xi = 0; xi < 3; xi++) {
        for(int yi = 0; yi < 3; yi++) {
            printf("%.2f ", arg.bc_im[xi][yi]);
        }
        printf("\n");
    }

    for(int xi = 0; xi < SCREEN_WIDTH; xi++) {
        for(int yi = 0; yi < SCREEN_HEIGHT; yi++) {
            printf("%.2f ", depth_buff[GET_1D_INDEX(xi, yi, SCREEN_WIDTH)]);
        }
        printf("\n");
    }

    for(int xi = 0; xi < SCREEN_WIDTH; xi++) {
        for(int yi = 0; yi < SCREEN_HEIGHT; yi++) {
            printf("%01d ", tag_buff[GET_1D_INDEX(xi, yi, SCREEN_WIDTH)]);
        }
        printf("\n");
    }

    free(mem_space);

    return 0;
}