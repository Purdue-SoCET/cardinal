#include "include/graphics_lib.h"

// Returns the barycentric interpolation of the given three
void barycentric_coordinates(vector_t* l, vector_t point, vector_t pVs[3]) {
    float m[3][3] = {
        {1.0, 1.0, 1.0},
        {pVs[0].x, pVs[1].x, pVs[2].x},
        {pVs[0].y, pVs[1].y, pVs[2].y}
    };
    float bc_im[3][3];

    float det = m[0][0] * (m[1][1] * m[2][2] - m[2][1] * m[1][2]) -
                m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
                m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);

    float invDet = 1.0f / det;

    bc_im[0][0] = (m[1][1] * m[2][2] - m[2][1] * m[1][2]) * invDet;
    bc_im[0][1] = (m[0][2] * m[2][1] - m[0][1] * m[2][2]) * invDet;
    bc_im[0][2] = (m[0][1] * m[1][2] - m[0][2] * m[1][1]) * invDet;
    
    bc_im[1][0] = (m[1][2] * m[2][0] - m[1][0] * m[2][2]) * invDet;
    bc_im[1][1] = (m[0][0] * m[2][2] - m[0][2] * m[2][0]) * invDet;
    bc_im[1][2] = (m[0][2] * m[1][0] - m[0][0] * m[1][2]) * invDet;
    
    bc_im[2][0] = (m[1][0] * m[2][1] - m[2][0] * m[1][1]) * invDet;
    bc_im[2][1] = (m[2][0] * m[0][1] - m[0][0] * m[2][1]) * invDet;
    bc_im[2][2] = (m[0][0] * m[1][1] - m[1][0] * m[0][1]) * invDet;

    l->x = bc_im[0][0] * 1.0 + bc_im[0][1] * point.x + bc_im[0][2] * point.y;
    l->y = bc_im[1][0] * 1.0 + bc_im[1][1] * point.x + bc_im[1][2] * point.y;
    l->z = bc_im[2][0] * 1.0 + bc_im[2][1] * point.x + bc_im[2][2] * point.y;
}

void get_texture(vector_t* col, texture_t texture, float u, float v) {
    u = u > 0 ? u : -u;
    v = v > 0 ? v : -v;
    int texel_x = ((u - (int)u) * (texture.w-1)) + 0.5;
    int texel_y = ((v - (int)v) * (texture.h-1)) + 0.5;

    *col =  texture.color_arr[GET_1D_INDEX(texel_x, texel_y, texture.w)];
}

int matrix_inversion(const float *m, float *inv) {
    
    // ---- Calculate Determinent ---- 
    float det_part1 = m[0] * (m[4] * m[8] - m[5] * m[7]);
    float det_part2 = m[1] * (m[3] * m[8] - m[5] * m[6]);
    float det_part3 = m[2] * (m[3] * m[7] - m[4] * m[6]);
    float determinant = det_part1 - det_part2 + det_part3;

    // Check if the determinant is zero
    if (determinant < .00001f && determinant > -.00001f) {
        // No inverse exists
        return 1; 
    }

    // --- Calculate Inverse Matrix ---
    float inv_det = 1.0 / determinant;

    // Row 1
    inv[0] = (m[4] * m[8] - m[5] * m[7]) * inv_det;
    inv[1] = (m[2] * m[7] - m[1] * m[8]) * inv_det;
    inv[2] = (m[1] * m[5] - m[2] * m[4]) * inv_det;

    // Row 2
    inv[3] = (m[5] * m[6] - m[3] * m[8]) * inv_det;
    inv[4] = (m[0] * m[8] - m[2] * m[6]) * inv_det;
    inv[5] = (m[2] * m[3] - m[0] * m[5]) * inv_det;

    // Row 3
    inv[6] = (m[3] * m[7] - m[4] * m[6]) * inv_det;
    inv[7] = (m[1] * m[6] - m[0] * m[7]) * inv_det;
    inv[8] = (m[0] * m[4] - m[1] * m[3]) * inv_det;

    return 0; // Success
}

// cross product
vector_t cross_product(vector_t v1, vector_t v2) {
    vector_t result;
    result.x = v1.y * v2.z - v1.z * v2.y;
    result.y = v1.z * v2.x - v1.x * v2.z;
    result.z = v1.x * v2.y - v1.y * v2.x;
    return result;
}

// normalize vector
void normalize_vector(vector_t* v) {
    float length = sqrt(v->x * v->x + v->y * v->y + v->z * v->z);
    if (length > 0.0001f) {
        v->x /= length;
        v->y /= length;
        v->z /= length;
    }
}

// dot product
float dot_product(vector_t a, vector_t b) {
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

// mat3 x vec3 multiplication
vector_t mat3_mul_vec3(const float m[9], vector_t v) {
    vector_t out;
    out.x = m[0] * v.x + m[1] * v.y + m[2] * v.z;
    out.y = m[3] * v.x + m[4] * v.y + m[5] * v.z;
    out.z = m[6] * v.x + m[7] * v.y + m[8] * v.z;
    return out;
}