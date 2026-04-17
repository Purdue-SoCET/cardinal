#ifndef PIXEL_H
#define PIXEL_H
#include "graphics_lib.h"

typedef struct {
    float s;   /* perspective-corrected s before texel lookup */
    float t;   /* perspective-corrected t before texel lookup */
} debug_t;

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

#ifdef CPU_SIM
void kernel_pixel(void*);
#else
void kernel_pixel();
#endif

#endif
