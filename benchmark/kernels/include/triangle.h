#ifndef TRIANGLE_H
#define TRIANGLE_H

// Triangle Inputs
//  - Bounding Box Starting pixel
//  - 3 Projected Verticies for the known triangle
//  - Precomputed Barycentric Coordinates inverse matrix
//  - Triangle Tag
//  - Pixel Buffer
//  - Tag Buffer
#include "graphics_lib.h"

typedef struct {
    // Flattened Bounding Box
    int bb_start_x, bb_start_y;
    int bb_size_x, bb_size_y;

    // Flattened Barycentric Inverse Matrix (Uniforms for this triangle)
    float bc_00, bc_01, bc_02;
    float bc_10, bc_11, bc_12;
    float bc_20, bc_21, bc_22;

    int tag;

    // Only Z-values are needed for the rasterization depth test
    float v0z, v1z, v2z;

    // Buffer Information
    int buff_w, buff_h;
    float* depth_buff;
    int* tag_buff;
} triangle_arg_t;

/*

typedef struct {
    // Per Triangle Information
    int bb_start[2];
    int bb_size[2];
    float bc_im[3][3];
    int tag;
    vector_t pVs[3];

    // Buffer Information
    int buff_w, buff_h;
    float* depth_buff;
    int*    tag_buff;
} triangle_arg_t;
 */

#ifdef CPU_SIM
void kernel_triangle(void* arg);
#else
void kernel_triangle();
#endif

#endif