#pragma once

// --- New Types ---
typedef struct {
    float x, y, z;
} vector_t;

typedef struct {
    vector_t coords; // 3D mapping
    float s, t; // Mapping into textures
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
vector_t barycentric_coordinates(vector_t, vector_t[3]);
vector_t get_texture(texture_t, float, float);
int matrix_inversion(const float*, float*);