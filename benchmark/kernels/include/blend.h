#ifndef BLEND_H
#define BLEND_H
#include "graphics_lib.h"

typedef struct {
   // Per Triangle Information
    int bb_start[2];
    int bb_size[2];
    float bc_im[3][3];
    int tag;
    vertex_t pVs[3];

    // Buffer Information
    int buff_w, buff_h;
    float* depth_buff;
    int*    tag_buff;

    // Transformed Verticies
    vertex_t* verts;
    int num_verts;

    // Triangle Data
    triangle_t* tris;
    int num_tris;

    // Pixel buffers
    vec4_t* color;

    // Texture Data
    texture_t texture;
} blend_arg_t;

#ifdef GPU_SIM
void main(void* arg);
#else
void kernel_blend(void* arg);
#endif    

#endif