#include "include/graphics_lib.h"

// Returns the barycentric interpolation of the given three
vector_t barycentric_coordinates(vector_t point, vector_t pVs[3]) {
    float m[3][3] = {
        {1, 1, 1},
        {pVs[0].x, pVs[1].x, pVs[2].x},
        {pVs[0].y, pVs[1].y, pVs[2].y}
    };
    float bc_im[3][3];

    double det = (double)m[0][0] * (m[1][1] * m[2][2] - m[2][1] * m[1][2]) -
                (double)m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
                (double)m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);

    double invDet = 1.0 / det;

    bc_im[0][0] = (m[1][1] * m[2][2] - m[2][1] * m[1][2]) * invDet;
    bc_im[0][1] = (m[0][2] * m[2][1] - m[0][1] * m[2][2]) * invDet;
    bc_im[0][2] = (m[0][1] * m[1][2] - m[0][2] * m[1][1]) * invDet;
    
    bc_im[1][0] = (m[1][2] * m[2][0] - m[1][0] * m[2][2]) * invDet;
    bc_im[1][1] = (m[0][0] * m[2][2] - m[0][2] * m[2][0]) * invDet;
    bc_im[1][2] = (m[0][2] * m[1][0] - m[0][0] * m[1][2]) * invDet;
    
    bc_im[2][0] = (m[1][0] * m[2][1] - m[2][0] * m[1][1]) * invDet;
    bc_im[2][1] = (m[2][0] * m[0][1] - m[0][0] * m[2][1]) * invDet;
    bc_im[2][2] = (m[0][0] * m[1][1] - m[1][0] * m[0][1]) * invDet;

    vector_t l; // Barycentric Coordinates
    l.x = point.x * bc_im[0][0] + point.y * bc_im[0][1] + point.z * bc_im[0][2];
    l.y = point.x * bc_im[1][0] + point.y * bc_im[1][1] + point.z * bc_im[1][2];
    l.z = point.x * bc_im[2][0] + point.y * bc_im[2][1] + point.z * bc_im[2][2];

    return l;
}

vector_t get_texture(texture_t texture, float s, float t) {
    
    int texel_x = (s * texture.w) + 0.5f;
    int texel_y = (t * texture.h) + 0.5f;

    return texture.color_arr[GET_1D_INDEX(texel_x, texel_y, texture.w)];
}