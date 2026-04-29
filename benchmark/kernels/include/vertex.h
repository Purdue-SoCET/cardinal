#ifndef VERTEX_H
#define VERTEX_H

#include "graphics_lib.h"

typedef struct {
    int num_verts;

    // Input 3D Model Data (SoA)
    float* v_x; float* v_y; float* v_z;
    float* v_s; float* v_t;

    // Transformation Uniforms (Flattened for broadcasting)
    float ox, oy, oz;       // Object Origin (Pivot)
    float* combined_matrix; // 3x3 Rotation
    
    // Camera & Projection Uniforms
    float cx, cy, cz;       // Camera Position
    float* invTrans;        // 3x3 Projection Matrix

    // Output: Transformed 3D Vertices (SoA)
    float* tx; float* ty; float* tz;

    // Output: Projected 2D Vertices (SoA)
    float* px; float* py; float* pz;

    float viewport_w;
    float viewport_h;
} vertex_arg_t;



/*
typedef struct {
    int num_verts;
    vertex_t* threeDVert;
    vector_t* Oa;
    float* combined_matrix;
    vertex_t* threeDVertTrans;
    vector_t* camera;
    float* invTrans;
    vertex_t* twoDVert;
    float viewport_w;
    float viewport_h;
    
} vertex_arg_t;
*/

#ifdef GPU_SIM
void kernel_vertex();
#else
void kernel_vertex(void*);
#endif

#endif