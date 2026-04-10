#include "include/kernel.h"
#include "include/triangle.h"

#ifdef GPU_SIM
void kernel_triangle()
#else
void kernel_triangle(void* arg)
#endif
{

    #ifdef GPU_SIM
    triangle_arg_t* args = (triangle_arg_t*) argPtr();
    #else
    triangle_arg_t* args = (triangle_arg_t*) arg;
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