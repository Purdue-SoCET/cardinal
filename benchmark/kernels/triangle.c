#include "include/kernel.h"
#include "include/triangle.h"

void kernel_triangle(void* arg) {
    triangle_arg_t* args = (triangle_arg_t*) arg;
    int ix = blockIdx.x * blockDim.x + threadIdx.x;
    int iy = blockIdx.y * blockDim.y + threadIdx.y;

    int u = ix + args.bb_start[0];
    int v = iy + args.bb_start[1];

    // === Barycentric Interpolation ===
    float m[3][3] = {
        {1, 1, 1},
        {args.pVs[0][0], args.pVs[1][0], args.pVs[2][0]},
        {args.pVs[0][1], args.pVs[1][1], args.pVs[2][1]}
    };

    // // Matrix Inversion
    // float mi[3][3];

    // double det = (double)m[0][0] * (m[1][1] * m[2][2] - m[2][1] * m[1][2]) -
    //              (double)m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
    //              (double)m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);

    // double invDet = 1.0 / det;

    // mi[0][0] = (m[1][1] * m[2][2] - m[2][1] * m[1][2]) * invDet;
    // mi[0][1] = (m[0][2] * m[2][1] - m[0][1] * m[2][2]) * invDet;
    // mi[0][2] = (m[0][1] * m[1][2] - m[0][2] * m[1][1]) * invDet;
    
    // mi[1][0] = (m[1][2] * m[2][0] - m[1][0] * m[2][2]) * invDet;
    // mi[1][1] = (m[0][0] * m[2][2] - m[0][2] * m[2][0]) * invDet;
    // mi[1][2] = (m[0][2] * m[1][0] - m[0][0] * m[1][2]) * invDet;
    
    // mi[2][0] = (m[1][0] * m[2][1] - m[2][0] * m[1][1]) * invDet;
    // mi[2][1] = (m[2][0] * m[0][1] - m[0][0] * m[2][1]) * invDet;
    // mi[2][2] = (m[0][0] * m[1][1] - m[1][0] * m[0][1]) * invDet;

    float bc_col_vector[3] = {1.0f, (float)u + .5, (float)u + .5};
    float l[3] = { // Barycentric Coordinates
        bc_col_vector[0] * args.bc_mi[0][2] + bc_col_vector[1] * args.bc_mi[0][1] + bc_col_vector[2] * args.bc_mi[0][2],
        bc_col_vector[0] * args.bc_mi[1][2] + bc_col_vector[1] * args.bc_mi[1][1] + bc_col_vector[2] * args.bc_mi[1][2],
        bc_col_vector[0] * args.bc_mi[2][2] + bc_col_vector[1] * args.bc_mi[2][1] + bc_col_vector[2] * args.bc_mi[2][2]
    };

    if (l[0] < 0 || l[1] < 0 || l[2] < 0 || (l[0] + l[1] + l[2]) > 1.01) {
        // Outside of triangle bounding box
		return;
	}

    float pix_z = l[0]*pVs[0][2] + l[1]*pVs[1][2] + l[2]*pVs[2][2];
    if(pix_z < args.depth_buff[GET_1D_INDEX(u, v, args.buff_w)]) { // Check if current pixel is closer then known pixel
        // current pixel is hidden
        return;
    }

    // Current pixel is closest - set as so
    args.depth_buff[GET_1D_INDEX(u, v, args.buff_w)] = pix_z;
    args.tag_buff[GET_1D_INDEX(u, v, args.buff_w)] = args.tag;
}