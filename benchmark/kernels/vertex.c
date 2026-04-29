#include "include/kernel.h"
#include "include/vertex.h"
#include "include/graphics_lib.h"

#ifdef GPU_SIM
void kernel_vertex()
#else
void kernel_vertex(void* arg)
#endif
{
    #ifdef GPU_SIM
    vertex_arg_t* args = (vertex_arg_t*) argPtr();
    #else
    vertex_arg_t* args = (vertex_arg_t*) arg;
    #endif

    int i = (blockIdx * blockDim) + threadIdx;

    // 1. Boundary check
    if(i < args->num_verts) 
    {
        // === Rotation Stage (Object to World) ===
        
        // Fetch input coordinates from SoA arrays
        // Subtract flattened pivot (Oa)
        float px = args->v_x[i] - args->ox;
        float py = args->v_y[i] - args->oy;
        float pz = args->v_z[i] - args->oz;

        // Apply rotation matrix
        float rx = args->combined_matrix[0]*px + args->combined_matrix[1]*py + args->combined_matrix[2]*pz;
        float ry = args->combined_matrix[3]*px + args->combined_matrix[4]*py + args->combined_matrix[5]*pz;
        float rz = args->combined_matrix[6]*px + args->combined_matrix[7]*py + args->combined_matrix[8]*pz;

        // Store transformed coordinates back to SoA arrays
        args->tx[i] = rx + args->ox;
        args->ty[i] = ry + args->oy;
        args->tz[i] = rz + args->oz;

        // === Projection Stage (World to Screen) ===

        // Use flattened camera scalars (cx, cy, cz)
        float nx = args->tx[i] - args->cx;
        float ny = args->ty[i] - args->cy;
        float nz = args->tz[i] - args->cz;

        // Apply inverse camera projection matrix
        float qx = nx*args->invTrans[0] + ny*args->invTrans[1] + nz*args->invTrans[2];
        float qy = nx*args->invTrans[3] + ny*args->invTrans[4] + nz*args->invTrans[5];
        float qz = nx*args->invTrans[6] + ny*args->invTrans[7] + nz*args->invTrans[8];

        if (qz > 0.0) // Clipping: Only process if in front of camera
        {
            float inv_qz = 1.0 / qz;
            
            // Normalized Device Coordinates
            float ndc_x = qx * inv_qz;
            float ndc_y = qy * inv_qz;

            // Viewport mapping & store to projected
            args->px[i] = (ndc_x + 1.0) * args->viewport_w * 0.5;
            args->py[i] = (1.0 - ndc_y) * args->viewport_h * 0.5;
            args->pz[i] = inv_qz; // Store W-buffer (1/z) for the rasterizer
        }
    }
}

/*

#ifdef GPU_SIM
void kernel_vertex()
#else
void kernel_vertex(void* arg)
#endif
{

    #ifdef GPU_SIM
    vertex_arg_t* args = (vertex_arg_t*) argPtr();
    #else
    vertex_arg_t* args = (vertex_arg_t*) arg;
    #endif
    int i = (blockIdx * blockDim) + threadIdx;


    if(i < args->num_verts) 
    {

        // camera space to world space
        float px = args->threeDVert[i].coords.x - args->Oa->x;
        float py = args->threeDVert[i].coords.y - args->Oa->y;
        float pz = args->threeDVert[i].coords.z - args->Oa->z;

        // apply rotation matrix
        float rx = args->combined_matrix[0]*px + args->combined_matrix[1]*py + args->combined_matrix[2]*pz;
        float ry = args->combined_matrix[3]*px + args->combined_matrix[4]*py + args->combined_matrix[5]*pz;
        float rz = args->combined_matrix[6]*px + args->combined_matrix[7]*py + args->combined_matrix[8]*pz;

        // world space back to camera space
        args->threeDVertTrans[i].coords.x = rx + args->Oa->x;
        args->threeDVertTrans[i].coords.y = ry + args->Oa->y;
        args->threeDVertTrans[i].coords.z = rz + args->Oa->z;

        // pass through texture coordinates
        args->threeDVertTrans[i].s = args->threeDVert[i].s;
        args->threeDVertTrans[i].t = args->threeDVert[i].t;

        // Perspective Projection
        float nx = args->threeDVertTrans[i].coords.x - args->camera->x;
        float ny = args->threeDVertTrans[i].coords.y - args->camera->y;
        float nz = args->threeDVertTrans[i].coords.z - args->camera->z;

        // apply inverse camera projection matrix
        float qx = nx*args->invTrans[0] + ny*args->invTrans[1] + nz*args->invTrans[2];
        float qy = nx*args->invTrans[3] + ny*args->invTrans[4] + nz*args->invTrans[5];
        float qz = nx*args->invTrans[6] + ny*args->invTrans[7] + nz*args->invTrans[8];

        if (qz > 0.0) // Is the vertex in front of the camera?
        {
            args->twoDVert[i].coords.x = qx / qz;
            args->twoDVert[i].coords.y = qy / qz;
            args->twoDVert[i].coords.z = 1.0 / qz;

            args->twoDVert[i].s = args->threeDVert[i].s;
            args->twoDVert[i].t = args->threeDVert[i].t;
            
            args->twoDVert[i].coords.x = (args->twoDVert[i].coords.x + 1.0) * args->viewport_w / 2.0;
            args->twoDVert[i].coords.y = (1.0 - args->twoDVert[i].coords.y) * args->viewport_h / 2.0;
        }
    }
}

*/
