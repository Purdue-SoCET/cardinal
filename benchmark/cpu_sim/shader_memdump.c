#include "include/shader_memdump.h"

void print_line(FILE* f, uintptr_t addr, uint32_t data) {
    fprintf(f, "0x%08X \t 0x%08X\n", (unsigned int)addr, data);
}

void print_vertex_args(char* fname, vertexShader_arg_t* vertex_args, int num_verts) {
    FILE *f = fopen(fname, "w");
    if (!f) return;

    // 1. Struct Header (8 pointers)
    uint32_t* s_raw = (uint32_t*)vertex_args;
    for (int i = 0; i < 8; i++) print_line(f, (uintptr_t)&s_raw[i], s_raw[i]);

    // 2. Pointed Constant Data
    if (vertex_args->Oa)      for(int i=0; i<3; i++) print_line(f, (uintptr_t)&((uint32_t*)vertex_args->Oa)[i], ((uint32_t*)vertex_args->Oa)[i]);
    if (vertex_args->a_dist)  for(int i=0; i<3; i++) print_line(f, (uintptr_t)&((uint32_t*)vertex_args->a_dist)[i], ((uint32_t*)vertex_args->a_dist)[i]);
    if (vertex_args->alpha_r) print_line(f, (uintptr_t)vertex_args->alpha_r, *(uint32_t*)vertex_args->alpha_r);
    if (vertex_args->camera)   for(int i=0; i<3; i++) print_line(f, (uintptr_t)&((uint32_t*)vertex_args->camera)[i], ((uint32_t*)vertex_args->camera)[i]);
    if (vertex_args->invTrans) for(int i=0; i<9; i++) print_line(f, (uintptr_t)&((uint32_t*)vertex_args->invTrans)[i], ((uint32_t*)vertex_args->invTrans)[i]);

    // 3. Vertex Arrays (Input and Outputs)
    for(int i = 0; i < num_verts; i++) {
        uint32_t* v1 = (uint32_t*)&vertex_args->threeDVert[i];
        uint32_t* v2 = (uint32_t*)&vertex_args->threeDVertTrans[i];
        uint32_t* v3 = (uint32_t*)&vertex_args->twoDVert[i];
        // Each vertex_t is 5 words (x, y, z, s, t)
        for(int j=0; j<5; j++) print_line(f, (uintptr_t)&v1[j], v1[j]);
        for(int j=0; j<5; j++) print_line(f, (uintptr_t)&v2[j], v2[j]);
        for(int j=0; j<5; j++) print_line(f, (uintptr_t)&v3[j], v3[j]);
    }
    fclose(f);
}

void print_triangle_args(char* fname, triangle_arg_t* tri_args) {
    FILE *f = fopen(fname, "w");
    if (!f) return;

    // 1. Struct Header (27 words)
    uint32_t* s_raw = (uint32_t*)tri_args;
    for (int i = 0; i < 27; i++) print_line(f, (uintptr_t)&s_raw[i], s_raw[i]);

    // 2. External Pixel Buffers
    uint32_t* z_ptr = (uint32_t*)tri_args->depth_buff;
    uint32_t* t_ptr = (uint32_t*)tri_args->tag_buff;
    int pix_count = tri_args->buff_w * tri_args->buff_h;

    for (int i = 0; i < pix_count; i++) {
        if (z_ptr) print_line(f, (uintptr_t)&z_ptr[i], z_ptr[i]);
        if (t_ptr) print_line(f, (uintptr_t)&t_ptr[i], t_ptr[i]);
    }
    fclose(f);
}

void print_pixel_args(char* fname, pixel_arg_t* pix_args) {
    FILE *f = fopen(fname, "w");
    if (!f) return;

    // 1. Struct Header (12 words)
    uint32_t* s_raw = (uint32_t*)pix_args;
    for (int i = 0; i < 12; i++) print_line(f, (uintptr_t)&s_raw[i], s_raw[i]);

    // 2. Global Buffers (Color, Depth, Tag)
    int pix_count = pix_args->buff_w * pix_args->buff_h;
    uint32_t* c_ptr = (uint32_t*)pix_args->color;
    uint32_t* z_ptr = (uint32_t*)pix_args->depth_buff;
    uint32_t* t_ptr = (uint32_t*)pix_args->tag_buff;

    for (int i = 0; i < pix_count; i++) {
        if (c_ptr) {
            print_line(f, (uintptr_t)&c_ptr[i*3], c_ptr[i*3]);     // x
            print_line(f, (uintptr_t)&c_ptr[i*3+1], c_ptr[i*3+1]); // y
            print_line(f, (uintptr_t)&c_ptr[i*3+2], c_ptr[i*3+2]); // z
        }
        if (z_ptr) print_line(f, (uintptr_t)&z_ptr[i], z_ptr[i]);
        if (t_ptr) print_line(f, (uintptr_t)&t_ptr[i], t_ptr[i]);
    }

    // 3. Texture Data
    int tex_count = pix_args->texture.w * pix_args->texture.h;
    uint32_t* tx_ptr = (uint32_t*)pix_args->texture.color_arr;
    if (tx_ptr) {
        for (int i = 0; i < tex_count; i++) {
            print_line(f, (uintptr_t)&tx_ptr[i*3], tx_ptr[i*3]);
            print_line(f, (uintptr_t)&tx_ptr[i*3+1], tx_ptr[i*3+1]);
            print_line(f, (uintptr_t)&tx_ptr[i*3+2], tx_ptr[i*3+2]);
        }
    }
    fclose(f);
}