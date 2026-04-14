#ifndef BLEND_LIGHT_H
#define BLEND_LIGHT_H
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

    // Lighting Data (same with pixel_arg_t in pixel.h)
    vertex_t* threeDVertTrans;
    vector_t camera;
    vector_t sphere_center;
    vector_t light_pos;
    vec4_t albedo;
    vector_t ambient;
    float kd, ks;
} blend_arg_t;

#ifdef GPU_SIM
void main(void* arg);
#else
void kernel_blend_light(void* arg);
#endif    

#endif