#pragma once

#include "graphics_lib.h"

typedef struct {
    // Transformed Verticies
    vertex_t* verts;
    int num_verts;

    // Triangle Data
    triangle_t* tris;
    int num_tris;

    // Pixel buffers
    int buff_w, buff_h;
    float* depth_buff;
    int* tag_buff;
    vector_t* color;

    // Texture Data
    texture_t texture;

} pixel_arg_t;

void kernel_pixel(void*);