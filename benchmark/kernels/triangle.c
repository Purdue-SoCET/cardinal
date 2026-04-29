#include "include/kernel.h"
#include "include/triangle.h"

#ifdef CPU_SIM
void kernel_triangle(void* arg)
#else
void kernel_triangle()
#endif
{
    #ifdef CPU_SIM
    triangle_arg_t* args = (triangle_arg_t*) arg;
    #else
    triangle_arg_t* args = (triangle_arg_t*) argPtr();
    #endif
    
    int global_id = (blockIdx * blockDim) + threadIdx;

    // Mapping 1D thread ID to 2D Bounding Box coordinates
    int ix = global_id % args->bb_size_x;
    int iy = global_id / args->bb_size_x;

    // Check if thread is within the triangle's bounding box
    if (iy < args->bb_size_y) {
        int u = ix + args->bb_start_x;
        int v = iy + args->bb_start_y;

        // Pixel center for sampling
        float px = (float)u + 0.5;
        float py = (float)v + 0.5;

        // === Barycentric Calculation (Using Flattened Matrix) ===
        // bc_col_vector is always 1.0, so we just use the first column directly
        float l0 = args->bc_00 + px * args->bc_01 + py * args->bc_02;
        float l1 = args->bc_10 + px * args->bc_11 + py * args->bc_12;
        float l2 = args->bc_20 + px * args->bc_21 + py * args->bc_22;

        // Edge test (including small epsilon for stability)
        if (l0 >= -0.00001 && l1 >= -0.00001 && l2 >= -0.00001 && (l0 + l1 + l2) <= 1.01) {

            // Interpolate Depth (pix_z) using SoA depths
            float pix_z = l0 * args->v0z + l1 * args->v1z + l2 * args->v2z;

            int pixel_idx = v * args->buff_w + u;

            // Coalesced Read-Modify-Write
            // Adjacent threads are writing to adjacent indices in the depth/tag buffers
            if (pix_z >= args->depth_buff[pixel_idx]) {
                args->depth_buff[pixel_idx] = pix_z;
                args->tag_buff[pixel_idx] = args->tag;
            }
        }
    }
}

/*
#ifdef CPU_SIM
void kernel_triangle(void* arg)
#else
void kernel_triangle()
#endif
{

    #ifdef CPU_SIM
    triangle_arg_t* args = (triangle_arg_t*) arg;
    #else
    triangle_arg_t* args = (triangle_arg_t*) argPtr();
    #endif
    int global_id = (blockIdx * blockDim) + threadIdx;


    int ix = (((global_id)) - (args->bb_size[0])*(((global_id))/(args->bb_size[0])));
    int iy = (((global_id) / args->bb_size[0]) - (args->bb_size[1])*(((global_id) / args->bb_size[0])/(args->bb_size[1])));

    int u = ix + args->bb_start[0];
    int v = iy + args->bb_start[1];

    // === Barycentric Interpolation ===

    float bc_col_vector[3];
    bc_col_vector[0] = 1.0;
    bc_col_vector[1] = ((float)u) + .5;
    bc_col_vector[2] = ((float)v)+ .5;
    float l[3] = { // Barycentric Coordinates
        bc_col_vector[0] * args->bc_im[0][0] + bc_col_vector[1] * args->bc_im[0][1] + bc_col_vector[2] * args->bc_im[0][2],
        bc_col_vector[0] * args->bc_im[1][0] + bc_col_vector[1] * args->bc_im[1][1] + bc_col_vector[2] * args->bc_im[1][2],
        bc_col_vector[0] * args->bc_im[2][0] + bc_col_vector[1] * args->bc_im[2][1] + bc_col_vector[2] * args->bc_im[2][2]
    };

    // Check if the pixel is inside the triangle bounding box
    if (l[0] >= -.00001 && l[1] >= -.00001 && l[2] >= -.00001 && (l[0] + l[1] + l[2]) <= 1.01) {

        float pix_z = l[0]*args->pVs[0].z + l[1]*args->pVs[1].z + l[2]*args->pVs[2].z;

        // Check if current pixel is closest (inverted from original '<' return check)
        if (pix_z >= args->depth_buff[GET_1D_INDEX(u, v, args->buff_w)]) {
            // Current pixel is closest - set as so
            args->depth_buff[GET_1D_INDEX(u, v, args->buff_w)] = pix_z;
            args->tag_buff[GET_1D_INDEX(u, v, args->buff_w)] = args->tag;
        }
    }
}
*/