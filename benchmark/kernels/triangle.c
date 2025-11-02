#include "include/kernel.h"
#include "include/triangle.h"

void kernel_triangle(void* arg) {
    triangle_arg_t* args = (triangle_arg_t*) arg;
    int ix = blockIdx.x * blockDim.x + threadIdx.x;
    int iy = blockIdx.y * blockDim.y + threadIdx.y;

    int u = ix + args->bb_start[0];
    int v = iy + args->bb_start[1];

    // === Barycentric Interpolation ===

    float bc_col_vector[3];
    bc_col_vector[0] = 1.0f;
    bc_col_vector[1] = ((float)u) + .5;
    bc_col_vector[2] = (float)v + .5;
    float l[3] = { // Barycentric Coordinates
        bc_col_vector[0] * args->bc_im[0][0] + bc_col_vector[1] * args->bc_im[0][1] + bc_col_vector[2] * args->bc_im[0][2],
        bc_col_vector[0] * args->bc_im[1][0] + bc_col_vector[1] * args->bc_im[1][1] + bc_col_vector[2] * args->bc_im[1][2],
        bc_col_vector[0] * args->bc_im[2][0] + bc_col_vector[1] * args->bc_im[2][1] + bc_col_vector[2] * args->bc_im[2][2]
    };

    if (l[0] < -.00001f || l[1] < -.00001f || l[2] < -.00001f || (l[0] + l[1] + l[2]) > 1.01) {
        // Outside of triangle bounding box
		return;
	}

    float pix_z = l[0]*args->pVs[0][2] + l[1]*args->pVs[1][2] + l[2]*args->pVs[2][2];
    if(pix_z < args->depth_buff[GET_1D_INDEX(u, v, args->buff_w)]) { // Check if current pixel is closer then known pixel
        // current pixel is hidden
        return;
    }

    // Current pixel is closest - set as so
    args->depth_buff[GET_1D_INDEX(u, v, args->buff_w)] = pix_z;
    args->tag_buff[GET_1D_INDEX(u, v, args->buff_w)] = args->tag;
}