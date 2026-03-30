#ifndef GRAPHICS_LIB_H
#define GRAPHICS_LIB_H

// --- New Types ---
typedef struct {
    float x, y, z;
} vector_t;

typedef struct {
    vector_t coords; // 3D mapping
    float s, t; // Mapping into textures
} vertex_t;

typedef struct {
    float s, t; 
} texel_t;

typedef struct {
    unsigned int v1, v2, v3;
} triangle_t;

typedef struct {
    float w, x, y, z;
} vec4_t;

typedef struct {
    int w, h;
    //vec4_t* color_arr;
    vector_t* color_arr;
    int id;
} texture_t;

typedef struct {
    int vertsN;
    int trisN;
    vertex_t* vertices;
    triangle_t* triangles;
} model_t;

// --- Macros ---
#define GET_1D_INDEX(idx_w, idx_h, arr_w) (idx_h*arr_w + idx_w)

// --- Functions ---

void build_rotation_matrix_from_euler(float ax, float ay, float az, float* out_matrix);

#endif