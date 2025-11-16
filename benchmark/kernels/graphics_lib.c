#include "include/graphics_lib.h"
#include <stdio.h>

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

    if(det == 0) printf("Barcyentric Coordinates for det = 0. Created colinear triangle\n");
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
    l.x = bc_im[0][0] * 1.0f + bc_im[0][1] * point.x + bc_im[0][2] * point.y;
    l.y = bc_im[1][0] * 1.0f + bc_im[1][1] * point.x + bc_im[1][2] * point.y;
    l.z = bc_im[2][0] * 1.0f + bc_im[2][1] * point.x + bc_im[2][2] * point.y;

    return l;
}

vector_t get_texture(texture_t texture, float s, float t) {
    s = s > 0 ? s : -s;
    t = t > 0 ? t : -t;
    int texel_x = ((s - (int)s) * (texture.w-1)) + 0.5f;
    int texel_y = ((t - (int)t) * (texture.h-1)) + 0.5f;

    if(texel_x >= texture.w || texel_y >= texture.h || texel_x < 0 || texel_y < 0) {
        printf("get_texture: Out of bounds error. <tx, ty> = <%d, %d>\n", texel_x, texel_y);
        printf("\t<s, t> = <%f, %f>\n", s, t);
    }
    return texture.color_arr[GET_1D_INDEX(texel_x, texel_y, texture.w)];
}

int matrix_inversion(const float *m, float *inv) {
    
    // ---- Calculate Determinent ---- 
    float det_part1 = m[0] * (m[4] * m[8] - m[5] * m[7]);
    float det_part2 = m[1] * (m[3] * m[8] - m[5] * m[6]);
    float det_part3 = m[2] * (m[3] * m[7] - m[4] * m[6]);
    float determinant = det_part1 - det_part2 + det_part3;

    // Check if the determinant is zero
    if (determinant < 1e-6 && determinant > 1e-6) {
        // No inverse exists
        return 1; 
    }

    // --- Calculate Inverse Matrix ---
    float inv_det = 1.0f / determinant;

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