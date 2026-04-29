#ifndef PIXEL_H
#define PIXEL_H
#include "graphics_lib.h"

typedef struct {
    // Vertex Data (SoA)
    float* v_x; float* v_y; float* v_z;
    float* v_s; float* v_t;
    int num_verts;

    // Triangle Data (SoA)
    int* tri_v1; int* tri_v2; int* tri_v3;
    int num_tris;

    // Transformed 3D Data for Lighting (SoA)
    float* trans_x; float* trans_y; float* trans_z;

    // Pixel buffers
    int buff_w, buff_h;
    float* depth_buff;
    int* tag_buff;
    //vec4_t* color;
    float* color_r;
    float* color_g;
    float* color_b;
    float* color_a;

    // Texture & Lighting 
    texture_t texture;
    vector_t camera;
    vector_t sphere_center;
    vector_t light_pos;
    vec4_t albedo;
    vector_t ambient;
    float kd, ks;
} pixel_arg_t;

/*

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
    vertex_t* threeDVertTrans;
    vector_t camera;
    //because we dont store normals just pass in
    vector_t sphere_center;
    vector_t light_pos;
    //overridden by texture
    vec4_t albedo;
    vector_t ambient;
    //diffuse / specular
    float kd, ks;

} pixel_arg_t;
*/

#ifdef CPU_SIM
void kernel_pixel(void* arg);
#else
void kernel_pixel();
#endif

#endif
