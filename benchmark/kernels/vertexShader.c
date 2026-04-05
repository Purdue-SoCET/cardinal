#include "include/kernel.h"
#include "include/vertexShader.h"
#include "../cpu_sim/include/graphics_lib.h"

void kernel_vertexShader(void* arg)
{
    vertexShader_arg_t* args = (vertexShader_arg_t*) arg;

    int i = blockIdx * blockDim + threadIdx;
    if (i >= args->num_verts) return;

    /****** Stage 1: ThreeD Rotation ******/
    // Per-frame common matrices and lighting values are precomputed on the CPU
    // and passed through vertexShader_arg_t.
    // lcsInv = world -> local matrix
    // rotMat = rotation matrix in local space
    // lcs = local -> world matrix
    const float* lcs = args->lcs;
    const float* lcsInv = args->lcsInv;
    const float* rotMat = args->rotMat;

    // move vertex to origin based on rotation axis
    vector_t vertex_origin = {
        args->vertex_input_buffer[i].coords.x - args->Oa->x,
        args->vertex_input_buffer[i].coords.y - args->Oa->y,
        args->vertex_input_buffer[i].coords.z - args->Oa->z
    };

    /*world -> local*/
    vector_t vertex_local = mat3_mul_vec3(lcsInv, vertex_origin);

    /* rotate in local space */
    vector_t vertex_rotated = mat3_mul_vec3(rotMat, vertex_local);

    /* local -> world */
    vector_t vertex_world = mat3_mul_vec3(lcs, vertex_rotated);

    // move vertex back based on rotation axis
    args->threeDVertTrans[i].coords.x = vertex_world.x + args->Oa->x;
    args->threeDVertTrans[i].coords.y = vertex_world.y + args->Oa->y;
    args->threeDVertTrans[i].coords.z = vertex_world.z + args->Oa->z;
    // u, v coordinates are unaffected by rotation
    args->threeDVertTrans[i].u = args->vertex_input_buffer[i].u;
    args->threeDVertTrans[i].v = args->vertex_input_buffer[i].v;

    /****** Stage 2: Normal Transformation & Lighting ******/
    vector_t normal_origin = {
        args->vertex_input_buffer[i].normal.x,
        args->vertex_input_buffer[i].normal.y,
        args->vertex_input_buffer[i].normal.z
    };

    // normal to world -> local
    vector_t normal_local = mat3_mul_vec3(lcsInv, normal_origin);

    // rotate normal in local space
    vector_t normal_rotated = mat3_mul_vec3(rotMat, normal_local);

    // rotate normal back to world space
    vector_t normal_world = mat3_mul_vec3(lcs, normal_rotated);
    normalize_vector(&normal_world);

    // lighting calculation (Lambertian diffuse + ambient)
    float normal_dot_light = dot_product(normal_world, args->light_dir);
    float intensity = args->ambient;
    
    if (normal_dot_light > 0.0f) {
        intensity += normal_dot_light * args->diffuse;
    }
    if (intensity > 1.0f) intensity = 1.0f; 

    args->vertex_output_buffer[i].intensity = intensity;
    
    /****** Stage 3: 4D Camera Clip-space Projection ******/
    // x/y/z are stored without perspective divide.
    // w is reserved for the later 4D clip-space path.
    vector4_t vertex_camera = { 
        args->threeDVertTrans[i].coords.x - args->camera->x,
        args->threeDVertTrans[i].coords.y - args->camera->y,
        args->threeDVertTrans[i].coords.z - args->camera->z,
        1.0f
    };

    vector4_t vertex_clip = mat4_mul_vec4(args->project4x4, vertex_camera);

    // store clip-space output without perspective divide.
    args->vertex_output_buffer[i].coords.x = vertex_clip.x;
    args->vertex_output_buffer[i].coords.y = vertex_clip.y;
    args->vertex_output_buffer[i].coords.z = vertex_clip.z;
    args->vertex_output_buffer[i].w = vertex_clip.w;

    // u, v coordinates are unaffected by projection
    args->vertex_output_buffer[i].u = args->vertex_input_buffer[i].u;
    args->vertex_output_buffer[i].v = args->vertex_input_buffer[i].v;
    args->vertex_output_buffer[i].normal = normal_world;
    args->vertex_output_buffer[i].intensity = intensity;

    // prepare reciprocal-w varyings for later perspective-correct interpolation
    if (vertex_clip.w != 0.0f) {
        float inv_w = 1.0f / vertex_clip.w;
        args->vertex_output_buffer[i].inv_w = inv_w;
        args->vertex_output_buffer[i].u_over_w = args->vertex_input_buffer[i].u * inv_w;
        args->vertex_output_buffer[i].v_over_w = args->vertex_input_buffer[i].v * inv_w;
    } else {
        args->vertex_output_buffer[i].inv_w = 0.0f;
        args->vertex_output_buffer[i].u_over_w = 0.0f;
        args->vertex_output_buffer[i].v_over_w = 0.0f;
    }

    return;
}