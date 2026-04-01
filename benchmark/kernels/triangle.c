#include "include/kernel.h"
#include "include/triangle.h"

void kernel_triangle(void* arg) {
    triangle_arg_t* args = (triangle_arg_t*) arg;
    // int ix = mod(threadIdx, args->bb_size[0]);
    int ix = (((threadIdx)) - (args->bb_size[0])*(((threadIdx))/(args->bb_size[0])));
    // int iy = mod(threadIdx / args->bb_size[0], args->bb_size[1]);
    int iy = (((threadIdx) / args->bb_size[0]) - (args->bb_size[1])*(((threadIdx) / args->bb_size[0])/(args->bb_size[1])));

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

    if (l[0] < -.00001) {
        // Outside of triangle bounding box
		return;
	} else if (l[1] < -.00001) {
        // Outside of triangle bounding box
		return;
    } else if (l[2] < -.00001) { 
        // Outside of triangle bounding box
		return;
    } else if ((l[0] + l[1] + l[2]) > 1.01) {
        // Outside of triangle bounding box
		return;
    }

    float pix_z = l[0]*args->triangle_verts[0].z + l[1]*args->triangle_verts[1].z + l[2]*args->triangle_verts[2].z;
    if(pix_z < args->depth_buffer[GET_1D_INDEX(u, v, args->buffer_w)]) { // Check if current pixel is closer then known pixel
        // current pixel is hidden
        return;
    }

    // Current pixel is closest - set as so
    args->depth_buffer[GET_1D_INDEX(u, v, args->buffer_w)] = pix_z;
    args->tag_buffer[GET_1D_INDEX(u, v, args->buffer_w)] = args->tag;
}