#ifndef VERTEX_H
#define VERTEX_H

#include "graphics_lib.h"


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


#ifdef GPU_SIM
void main(void*);
#else
void kernel_vertex(void*);
#endif

#endif