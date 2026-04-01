#ifndef CPU_SIM_GRAPHICS_LIB_H
#define CPU_SIM_GRAPHICS_LIB_H

#include <math.h>

// --- New Types ---
typedef struct {
    float x, y, z;
} vector_t;

typedef struct {
    vector_t coords; // 3D mapping
    float u, v; // Mapping into textures

    vector_t normal; // surface normal for lighting calculations
    float intensity; // lighting intensity
} vertex_t;

typedef struct {
    unsigned int v1, v2, v3;
} triangle_t;

typedef struct {
    int w, h;
    vector_t* color_arr;
} texture_t;

// --- Macros ---
#define GET_1D_INDEX(idx_w, idx_h, arr_w) (idx_h*arr_w + idx_w)

// --- Functions ---
void barycentric_coordinates(vector_t*, vector_t, vector_t[3]);
void get_texture(vector_t*, texture_t, float, float);
int matrix_inversion(const float*, float*);

// obj parser: .obj file -> vertex data + triangle data
int obj_parser(const char* filename, vertex_t** vertex_input_buffer, int* out_num_verts, triangle_t** triangle_index_buffer, int* out_num_tris);
// primitive assembly: vertex data + triangle data -> assembled triangle data
int primitive_assembly(vertex_t* vertex_output_buffer, triangle_t* triangle_index_buffer, int num_tris, triangle_t* surviving_triangle_index_buffer);

// math helper functions
vector_t cross_product(vector_t v1, vector_t v2);
void normalize_vector(vector_t* v);
float dot_product(vector_t a, vector_t b);

#endif