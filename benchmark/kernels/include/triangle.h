#ifndef TRIANGLE_H
#define TRIANGLE_H

// Triangle Inputs
//  - Bounding Box Starting pixel
//  - 3 Projected Verticies for the known triangle
//  - Precomputed Barycentric Coordinates inverse matrix
//  - Triangle Tag
//  - Pixel Buffer
//  - Tag Buffer
#include "../../cpu_sim/include/graphics_lib.h"

typedef struct {
    // Per Triangle Information
    int bb_start[2];
    int bb_size[2];
    float bc_im[3][3];
    int tag;
    vector_t triangle_verts[3];

    // Buffer Information
    int buffer_w, buffer_h;
    float* depth_buffer;
    int*    tag_buffer;
} triangle_arg_t;

void kernel_triangle(void*);

#endif