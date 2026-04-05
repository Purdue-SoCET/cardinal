#ifndef PIXEL_H
#define PIXEL_H
#include "../../cpu_sim/include/graphics_lib.h"

typedef struct {
    // Transformed Verticies
    vertex_t* assembled_vertex_buffer;
    int num_verts;

    // Triangle Data
    triangle_t* surviving_triangle_index_buffer;
    int num_tris;

    // Pixel buffers
    int buffer_w, buffer_h;
    float* depth_buffer;
    int* tag_buffer;
    vector_t* frame_buffer;

    // Texture Data
    texture_t texture_buffer;

} pixel_arg_t;

void kernel_pixel(void*);

#endif