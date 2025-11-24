#ifndef VERTEX_SHADER_H
#define VERTEX_SHADER_H

#include "graphics_lib.h"

//Note: All Vectors and Matrix are flat and expected to be 0 for all initaial values
typedef struct {
    /*3D -> 3D Transformation*/

    /*inputs*/
    vector_t* Oa;              //rotation origin
    vector_t* a_dist;          //distane of one origin axes 
    float* alpha_r;            //theta - angle for rotation matrix
    vertex_t* threeDVert;      //input 3D vectors

    /*output*/
    vertex_t* threeDVertTrans; //output 3D vertors after transformation

    /*3D Transformation -> 2D*/

    /*inputs*/
    vector_t* camera;          //camera location
    float* invTrans;        //inverse transformation matrix
    // threeDVertTrans is also an input 

    /*output*/
    vertex_t* twoDVert;        //output 2D  vertors
} vertexShader_arg_t;

void kernel_vertexShader(void*);

#endif