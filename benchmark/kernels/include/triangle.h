#pragma once

// Triangle Inputs
//  - Bounding Box Starting pixel
//  - 3 Projected Verticies for the known triangle
//  - Precomputed Barycentric Coordinates inverse matrix
//  - Triangle Tag
//  - Pixel Buffer
//  - Tag Buffer
#include "graphics_lib.h"

typedef struct {
    // Per Triangle Information
    int bb_start[2];
    float bc_im[3][3];
    int tag;
    vector_t pVs[3];

    // Buffer Information
    int buff_w, buff_h;
    float* depth_buff;
    int*    tag_buff;
} triangle_arg_t;

void kernel_triangle(void*);