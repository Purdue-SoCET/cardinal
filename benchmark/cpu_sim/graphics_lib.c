#include <stdio.h>
#include <stdlib.h>
#include "include/graphics_lib.h"

// Returns the barycentric interpolation of the given three
void barycentric_coordinates(vector_t* l, vector_t point, vector_t pVs[3]) {
    float m[3][3] = {
        {1.0, 1.0, 1.0},
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

    l->x = bc_im[0][0] * 1.0 + bc_im[0][1] * point.x + bc_im[0][2] * point.y;
    l->y = bc_im[1][0] * 1.0 + bc_im[1][1] * point.x + bc_im[1][2] * point.y;
    l->z = bc_im[2][0] * 1.0 + bc_im[2][1] * point.x + bc_im[2][2] * point.y;
}

void get_texture(vector_t* col, texture_t texture, float s, float t) {
    s = s > 0 ? s : -s;
    t = t > 0 ? t : -t;
    int texel_x = ((s - (int)s) * (texture.w-1)) + 0.5;
    int texel_y = ((t - (int)t) * (texture.h-1)) + 0.5;

    *col =  texture.color_arr[GET_1D_INDEX(texel_x, texel_y, texture.w)];
}

int matrix_inversion(const float *m, float *inv) {
    
    // ---- Calculate Determinent ---- 
    float det_part1 = m[0] * (m[4] * m[8] - m[5] * m[7]);
    float det_part2 = m[1] * (m[3] * m[8] - m[5] * m[6]);
    float det_part3 = m[2] * (m[3] * m[7] - m[4] * m[6]);
    float determinant = det_part1 - det_part2 + det_part3;

    // Check if the determinant is zero
    if (determinant < .00001 && determinant > .00001) {
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

void loadbin(char *fname, model_t *model) {
    FILE *fptr = fopen(fname, "rb");

    if (!fptr) {
        fprintf(stderr, "Error: Could not open %s\n", fname);
        return;
    }

    // Read vertex count
    fread(&model->vertsN, sizeof(int), 1, fptr);

    // Read flags 
    char hasCoords, hasColors, hasNormals, hasTexCoords;
    fread(&hasCoords, 1, 1, fptr);    // xyz
    fread(&hasColors, 1, 1, fptr);    // rgb
    fread(&hasNormals, 1, 1, fptr);   // nxnynz
    fread(&hasTexCoords, 1, 1, fptr); // st

    // Allocate your vertex_t array
    model->vertices = (vertex_t*)malloc(model->vertsN * sizeof(vertex_t));

    // Load Coordinates into vertex_t.coords
    for (int i = 0; i < model->vertsN; i++) {
        fread(&model->vertices[i].coords, sizeof(vector_t), 1, fptr);
    }

    // Optional data 
    if (hasColors == 'y') fseek(fptr, model->vertsN * sizeof(float) * 3, SEEK_CUR);
    if (hasNormals == 'y') fseek(fptr, model->vertsN * sizeof(float) * 3, SEEK_CUR);

    // Load Texture Coordinates into vertex_t.s and .t
    if (hasTexCoords == 'y') {
        for (int i = 0; i < model->vertsN; i++) {
            fread(&model->vertices[i].s, sizeof(float), 1, fptr);
            fread(&model->vertices[i].t, sizeof(float), 1, fptr);
        }
    } else {
        // Initialize to zero if not in file
        for (int i = 0; i < model->vertsN; i++) {
            model->vertices[i].s = 0.0f;
            model->vertices[i].t = 0.0f;
        }
    }

    // Load Triangles
    fread(&model->trisN, sizeof(int), 1, fptr);
    model->triangles = (triangle_t*)malloc(model->trisN * sizeof(triangle_t));
    fread(model->triangles, sizeof(triangle_t), model->trisN, fptr);

    fclose(fptr);
    printf("Model Loaded: %d vertices, %d triangles\n", model->vertsN, model->trisN);
}

vector_t findCenter(model_t model){
    float min_x = 100000.0f, max_x = -100000.0f;
    float min_y = 100000.0f, max_y = -100000.0f;
    float min_z = 100000.0f, max_z = -100000.0f;

    for (int i = 0; i < model.vertsN; i++) {
        vector_t v = model.vertices[i].coords;
        if (v.x < min_x) min_x = v.x;
        if (v.x > max_x) max_x = v.x;
        if (v.y < min_y) min_y = v.y;
        if (v.y > max_y) max_y = v.y;
        if (v.z < min_z) min_z = v.z;
        if (v.z > max_z) max_z = v.z;
    }

    // --- STEP 2: Calculate the Geometric Center ---
    vector_t center;
    center.x = (min_x + max_x) / 2.0f;
    center.y = (min_y + max_y) / 2.0f;
    center.z = (min_z + max_z) / 2.0f;

    return center;
}