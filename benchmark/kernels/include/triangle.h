#pragma once


// Triangle Inputs
//  - Bounding Box Starting pixel
//  - 3 Projected Verticies for the known triangle
//  - Precomputed Barycentric Coordinates inverse matrix
//  - Triangle Tag
//  - Pixel Buffer
//  - Tag Buffer

#define GET_1D_INDEX(idx_w, idx_h, arr_w) idx_h*arr_w + idx_w

typedef struct {
    int bb_start[2];
    float bc_im[3][3];
    int tag;
    float* pVs[3];

    // buffer info
    int buff_w, buff_h;
    float* depth_buff;
    int*    tag_buff;
} triangle_arg_t;

void kernel_triangle(void*);