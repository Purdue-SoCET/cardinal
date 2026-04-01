#ifndef VERTEX_SHADER_H
#define VERTEX_SHADER_H

#include "../../cpu_sim/include/graphics_lib.h"

//Note: All Vectors and Matrix are flat and expected to be 0 for all initaial values
typedef struct {
    /*3D -> 3D Transformation*/

    /*inputs*/
    vector_t* Oa;              //rotation origin
    vector_t* a_dist;          //distane of one origin axes 
    float* alpha_r;            //theta - angle for rotation matrix
    vertex_t* vertex_input_buffer;      //input 3D vectors

    /*output*/
    vertex_t* threeDVertTrans; //output 3D vertors after transformation

    /*3D Transformation -> 2D*/

    /*inputs*/
    vector_t* camera;          //camera location
    float* invTrans;        //inverse transformation matrix
    // threeDVertTrans is also an input 

    /*output*/
    vertex_t* vertex_output_buffer;        //output 2D  vertors

    // calculated values for transformation and lighting, can be reused across vertices
    float lcs[9];
    float lcsInv[9];
    float rotMat[9];
    vector_t light_dir;
    float ambient;
    float diffuse;

    int viewport_w;
    int viewport_h;

    int num_verts;
} vertexShader_arg_t;

void kernel_vertexShader(void*);

#endif