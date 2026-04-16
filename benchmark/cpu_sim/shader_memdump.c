#include "include/shader_memdump.h"

void print_line(FILE* f, uintptr_t addr, uint32_t data) {
    fprintf(f, "0x%08X \t 0x%08X\n", (unsigned int)addr, data);
}

void print_vertex_args(char* fname, vertex_arg_t* vertex_args, int num_verts) {
    FILE *f = fopen(fname, "w");
    if (!f) return;

    // 1. Struct Header
    int words = sizeof(vertex_arg_t)/sizeof(uint32_t);
    uint32_t* s_raw = (uint32_t*)vertex_args;
    for (int i = 0; i < words; i++)
        print_line(f, (uintptr_t)&s_raw[i], s_raw[i]);

    // 2. Pointed Constant Data
    if (vertex_args->Oa)      for(int i=0; i<3; i++) print_line(f, (uintptr_t)&((uint32_t*)vertex_args->Oa)[i], ((uint32_t*)vertex_args->Oa)[i]);
    if (vertex_args->combined_matrix)  for(int i=0; i<9; i++) print_line(f, (uintptr_t)&((uint32_t*)vertex_args->combined_matrix)[i], ((uint32_t*)vertex_args->combined_matrix)[i]);
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

    // 1. Struct Header
    int words = sizeof(triangle_arg_t)/sizeof(uint32_t);
    uint32_t* s_raw = (uint32_t*)tri_args;
    for (int i = 0; i < words; i++) print_line(f, (uintptr_t)&s_raw[i], s_raw[i]);

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

    // 1. Struct Header
    uint32_t* s_raw = (uint32_t*)pix_args;
    int words = sizeof(pixel_arg_t)/sizeof(uint32_t);
    for (int i = 0; i < words; i++)
        print_line(f, (uintptr_t)&s_raw[i], s_raw[i]);


    // 2. Vertex Arrays (Input and Outputs)
    for(int i = 0; i < pix_args->num_verts; i++) {
        uint32_t* v1 = (uint32_t*)&pix_args->verts[i];
        // Each vertex_t is 5 words (x, y, z, s, t)
        for(int j=0; j<5; j++) print_line(f, (uintptr_t)&v1[j], v1[j]);
    }

    if (pix_args->threeDVertTrans) {
        int vert_count = pix_args->num_verts;
        uint32_t* vert_ptr = (uint32_t*)pix_args->threeDVertTrans;
        for (int i = 0; i < vert_count; i++) {
            // Each vertex_t is 5 words (x, y, z, s, t)
            for(int j=0; j<5; j++) print_line(f, (uintptr_t)&vert_ptr[i*5+j], vert_ptr[i*5+j]);
        }
    }

    // 3. Triangle Arrays (Input and Outputs)
    for(int i = 0; i < pix_args->num_tris; i++) {
        uint32_t* t1 = (uint32_t*)&pix_args->tris[i];
        // Each triangle_t is 3 words (v1, v2, v3)
        for(int j=0; j<3; j++) print_line(f, (uintptr_t)&t1[j], t1[j]);
    }

    // 4. Global Buffers (Color, Depth, Tag)
    int pix_count = pix_args->buff_w * pix_args->buff_h;
    uint32_t* c_ptr = (uint32_t*)pix_args->color;
    uint32_t* z_ptr = (uint32_t*)pix_args->depth_buff;
    uint32_t* t_ptr = (uint32_t*)pix_args->tag_buff;
    for(int i = 0; i < pix_count; i++) {
        if (c_ptr) {
            // Each vec4_t is 4 words (x, y, z, w)
            print_line(f, (uintptr_t)&c_ptr[i*4], c_ptr[i*4]);     // x
            print_line(f, (uintptr_t)&c_ptr[i*4+1], c_ptr[i*4+1]); // y
            print_line(f, (uintptr_t)&c_ptr[i*4+2], c_ptr[i*4+2]); // z
            print_line(f, (uintptr_t)&c_ptr[i*4+3], c_ptr[i*4+3]); // w
        }
        if (z_ptr) print_line(f, (uintptr_t)&z_ptr[i], z_ptr[i]);
        if (t_ptr) print_line(f, (uintptr_t)&t_ptr[i], t_ptr[i]);
    }

    // 5. Texture Data
    // 5. Texture data
    if (pix_args->texture.color_arr) {
        int tex_count = pix_args->texture.w * pix_args->texture.h;
        uint32_t* tex_ptr = (uint32_t*)pix_args->texture.color_arr;
        for (int i = 0; i < tex_count; i++) {
            // Each vec4_t is 4 words (w, x, y, z)
            for (int j = 0; j < 4; j++)
                print_line(f, (uintptr_t)&tex_ptr[i*4+j], tex_ptr[i*4+j]);
        }
    }

    fclose(f);
}

void dump_memory(const char* filename, uint8_t* host_memory_ptr, uint32_t simulated_base_address, size_t num_bytes) {
    FILE* file = fopen(filename, "w");
    if (file == NULL) {
        fprintf(stderr, "Error: Could not open %s for writing.\n", filename);
        return;
    }

    uint32_t* memory_words = (uint32_t*) host_memory_ptr;
    // Round up to ensure we don't drop the last 1-3 bytes
    size_t num_words = (num_bytes + sizeof(uint32_t) - 1) / sizeof(uint32_t);

    for (size_t i = 0; i < num_words; i++) {
        uint32_t value = memory_words[i];
        uint32_t current_address = simulated_base_address + (i * sizeof(uint32_t));
        
        // Cast to unsigned int for standard %08X safety
        fprintf(file, "0x%08X %08X\n", current_address, (unsigned int)value);
    }

    fclose(file);
}