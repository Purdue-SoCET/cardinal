#ifndef CPU_SIM_GRAPHICS_LIB_H
#define CPU_SIM_GRAPHICS_LIB_H

#include <math.h>

// --- New Types ---
typedef struct {
    float x, y, z;
} vector_t;

typedef struct {
    float x, y, z, w;
} vector4_t;

typedef struct {
    vector_t coords; // 3D mapping
    float w; // for clipping
    float u, v; // Mapping into textures
    vector_t normal; // surface normal for lighting calculations
    float intensity; // lighting intensity

    float inv_w; // for perspective-correct interpolation, store 1/w from pre-divide stage
    float u_over_w; // for perspective-correct interpolation, store u/w from pre-divide stage
    float v_over_w; // for perspective-correct interpolation, store v/w from pre-dive stage
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
int primitive_assembly(const vertex_t* vertex_output_buffer, const triangle_t* triangle_index_buffer, int num_tris, vertex_t* assembled_vertex_buffer, int* assembled_vertex_count, int max_assembled_verts, triangle_t* surviving_triangle_index_buffer);

// math helper functions
vector_t cross_product(vector_t v1, vector_t v2);
void normalize_vector(vector_t* v);
float dot_product(vector_t a, vector_t b);
vector_t mat3_mul_vec3(const float m[9], vector_t v);
vector4_t mat4_mul_vec4(const float m[16], vector4_t v);

#endif