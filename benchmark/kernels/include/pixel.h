#ifndef PIXEL_H
#define PIXEL_H
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
    vec4_t* color;

    // Texture Data
    texture_t texture;

    
    // Lighting Data
    vec4_t albedo;
    /*
    vertex_t* threeDVertTrans;
    vector_t camera;
    //because we dont store normals just pass in
    vector_t sphere_center;
    vector_t light_pos;
    //overridden by texture
    vector_t ambient;
    //diffuse / specular
    float kd, ks;
    */

} pixel_arg_t;

#ifdef GPU_SIM
void kernel_pixel();
#else
void kernel_pixel(void*);
#endif

#endif