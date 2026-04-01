#include "include/kernel.h"
#include "include/vertexShader.h"
#include "../cpu_sim/include/graphics_lib.h"

void kernel_vertexShader(void* arg)
{
    vertexShader_arg_t* args = (vertexShader_arg_t*) arg;

    int i = blockIdx * blockDim + threadIdx;
    if (i >= args->num_verts) return;

    /****** ThreeD Rotation ******/
    // Per-frame common matrices and lighting values are precomputed on the CPU
    // and passed through vertexShader_arg_t.
    const float* lcs = args->lcs;
    const float* lcsInv = args->lcsInv;
    const float* rotMat = args->rotMat;

    // vertex normalized to rotation origin
    float p_tempAxis[3] = {
        args->vertex_input_buffer[i].coords.x - args->Oa->x,
        args->vertex_input_buffer[i].coords.y - args->Oa->y,
        args->vertex_input_buffer[i].coords.z - args->Oa->z
    };

    /*world -> local*/
    float p1[3] = {0, 0, 0};
    for(int j = 0; j < 3; j++)
    {
        for(int k = 0; k < 3; k++)
        {
            p1[j] += lcsInv[k*3 + j] * p_tempAxis[k];
        }
    }

    /* rotate in local space */
    float p2[3] = {0, 0, 0};
    for(int j = 0; j < 3; j++)
    {
        for(int k = 0; k < 3; k++)
        {
            p2[j] += rotMat[k*3 + j] * p1[k]; 
        }
    }

    /* local -> world */
    float p_world[3] = {0, 0, 0};
    for(int j = 0; j < 3; j++)
    {
        for(int k = 0; k < 3; k++)
        {
            p_world[j] += lcs[k*3 + j] * p2[k]; 
        }

        if(j == 0)
            args->threeDVertTrans[i].coords.x = p_world[j] + args->Oa->x;
        else if(j == 1)
            args->threeDVertTrans[i].coords.y = p_world[j] + args->Oa->y;
        if(j == 2)
            args->threeDVertTrans[i].coords.z = p_world[j] + args->Oa->z;
    }
    args->threeDVertTrans[i].u = args->vertex_input_buffer[i].u;
    args->threeDVertTrans[i].v = args->vertex_input_buffer[i].v;

    // 1. take the normal vector of vertex
    float n_tempAxis[3] = {
        args->vertex_input_buffer[i].normal.x,
        args->vertex_input_buffer[i].normal.y,
        args->vertex_input_buffer[i].normal.z
    };

    // normal to world -> local
    float n1[3] = {0, 0, 0};
    for(int j = 0; j < 3; j++) {
        for(int k = 0; k < 3; k++) {
            n1[j] += lcsInv[k*3 + j] * n_tempAxis[k];
        }
    }

    // rotate normal in local space
    float n2[3] = {0, 0, 0};
    for(int j = 0; j < 3; j++) {
        for(int k = 0; k < 3; k++) {
            n2[j] += rotMat[k*3 + j] * n1[k];
        }
    }

    // rotate normal back to world space
    float n_world[3] = {0, 0, 0};
    for(int j = 0; j < 3; j++) {
        for(int k = 0; k < 3; k++) {
            n_world[j] += lcs[k*3 + j] * n2[k];
        }
    }

    vector_t n_world_vec = {n_world[0], n_world[1], n_world[2]};
    normalize_vector(&n_world_vec);

    // lighting calculation (Lambertian diffuse + ambient)
    float normal_dot_light = dot_product(n_world_vec, args->light_dir);
    float intensity = args->ambient;
    
    if (normal_dot_light > 0.0f) {
        intensity += normal_dot_light * args->diffuse;
    }
    if (intensity > 1.0f) intensity = 1.0f; 

    args->vertex_output_buffer[i].intensity = intensity;
    
    /****** Projection ******/
    //PPC::Project

    /*Normalize 3D matrix w.r.t the camera*/
    float threeD_norm[3] = { 
        args->threeDVertTrans[i].coords.x - args->camera->x,
        args->threeDVertTrans[i].coords.y - args->camera->y,
        args->threeDVertTrans[i].coords.z - args->camera->z
    };

    float q[3] = {0.0, 0.0, 0.0};

    // q = 3Dnorm @ trans^-1
    for(int j = 0; j < 3; j++)
    {
        for(int k = 0; k < 3; k++)
        {
            q[j] += threeD_norm[k] * args->invTrans[j*3 + k];
        }
    }

    // if (q[2] < 0.0) return;
    // if (q[2] == 0.0) return;
    if (q[2] < 0.00001f) {
        args->vertex_output_buffer[i].coords.x = -10000.0f; 
        args->vertex_output_buffer[i].coords.y = -10000.0f;
        args->vertex_output_buffer[i].coords.z = 0.0f;
        return;
    }

    args->vertex_output_buffer[i].coords.x = q[0] / q[2];
    args->vertex_output_buffer[i].coords.y = q[1] / q[2];
    args->vertex_output_buffer[i].coords.z = 1.0 / q[2];

    args->vertex_output_buffer[i].u = args->vertex_input_buffer[i].u;
    args->vertex_output_buffer[i].v = args->vertex_input_buffer[i].v;

    return;
}