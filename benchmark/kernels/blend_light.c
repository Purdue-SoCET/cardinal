#include "include/kernel.h"
#include "include/blend_light.h"
#include "include/graphics_lib.h"

#ifdef GPU_SIM
void main(void* arg)
#else
void kernel_blend_light(void* arg)
#endif    
{

    #ifdef GPU_SIM
    blend_arg_t* args = (blend_arg_t*) argPtr();
    int ix = (((threadIdx())) - (args->bb_size[0])*(((threadIdx()))/(args->bb_size[0])));
    int iy = (((threadIdx()) / args->bb_size[0]) - (args->bb_size[1])*(((threadIdx()) / args->bb_size[0])/(args->bb_size[1])));

    #else
    blend_arg_t* args = (blend_arg_t*) arg;
    int ix = (((threadIdx)) - (args->bb_size[0])*(((threadIdx))/(args->bb_size[0])));
    int iy = (((threadIdx) / args->bb_size[0]) - (args->bb_size[1])*(((threadIdx) / args->bb_size[0])/(args->bb_size[1])));

    #endif

    int u = ix + args->bb_start[0];
    int v = iy + args->bb_start[1];

    if (u < 0 || v < 0 || u >= args->buff_w || v >= args->buff_h) {
        return;
    }

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

    float pix_z = l[0]*args->pVs[0].coords.z + l[1]*args->pVs[1].coords.z + l[2]*args->pVs[2].coords.z;

    if(pix_z < args->depth_buff[GET_1D_INDEX(u, v, args->buff_w)]) {
        return;
    }

    // base color for material
    vec4_t albedo = args->albedo;

    if(args->texture.color_arr != 0) {
        // Get new texture interpolation
        float correction_factor = l[0] * (args->pVs[0].coords.z) + l[1] * (args->pVs[1].coords.z) + l[2] * (args->pVs[2].coords.z);

        float s = l[0] * (args->pVs[0].s * args->pVs[0].coords.z) + l[1] * (args->pVs[1].s * args->pVs[1].coords.z) + l[2] * (args->pVs[2].s * args->pVs[2].coords.z);
        s = s / (correction_factor);

        float t = l[0] * (args->pVs[0].t * args->pVs[0].coords.z) + l[1] * (args->pVs[1].t * args->pVs[1].coords.z) + l[2] * (args->pVs[2].t * args->pVs[2].coords.z);
        t = t / (correction_factor);

        // 1. Abs function for s and t
        float s_abs;
        float t_abs;

        if(s>0.0){
            s_abs = s;
        } else{
            s_abs = 0.0-s;
        }
        if(t>0.0){
            t_abs = t;
        }
        else{
            t_abs = 0.0-t;
        }

        // 2. Calculate Texel Coordinates
        float w_minus_1 = itof(args->texture.w - 1);
        float h_minus_1 = itof(args->texture.h - 1);

        float s_fract = s_abs - itof(ftoi(s_abs));
        float t_fract = t_abs - itof(ftoi(t_abs));

        int texel_x = ftoi(s_fract * w_minus_1 + 0.5);
        int texel_y = ftoi(t_fract * h_minus_1 + 0.5);

        int idx = texel_y * args->texture.w + texel_x;
        albedo = args->texture.color_arr[idx];
    }

    vec4_t src_color = albedo;

    // check for valid condition to enble phong lighting    
    int phong_enable =
        args->threeDVertTrans != 0 &&
        args->tris != 0 &&
        args->num_tris > 0 &&
        args->num_verts > 0 &&
        args->tag >= 0 && args->tag < args->num_tris;
    
    if(phong_enable) {
        triangle_t tri = args->tris[args->tag];

        vector_t w0 = args->threeDVertTrans[tri.v1].coords;
        vector_t w1 = args->threeDVertTrans[tri.v2].coords;
        vector_t w2 = args->threeDVertTrans[tri.v3].coords;
        float wx = l[0]*w0.x + l[1]*w1.x + l[2]*w2.x;
        float wy = l[0]*w0.y + l[1]*w1.y + l[2]*w2.y;
        float wz = l[0]*w0.z + l[1]*w1.z + l[2]*w2.z;

        float nx = wx - args->sphere_center.x, ny = wy - args->sphere_center.y, nz = wz - args->sphere_center.z;
        float ni = isqrt(nx*nx + ny*ny + nz*nz);
        nx = nx*ni; ny = ny*ni; nz = nz*ni;

        float lx = args->light_pos.x - wx, ly = args->light_pos.y - wy, lz = args->light_pos.z - wz;
        float li = isqrt(lx*lx + ly*ly + lz*lz);
        lx = lx*li; ly = ly*li; lz = lz*li;

        float vx = args->camera.x - wx, vy = args->camera.y - wy, vz = args->camera.z - wz;
        float vi = isqrt(vx*vx + vy*vy + vz*vz);
        vx = vx*vi; vy = vy*vi; vz = vz*vi;

        float diff = nx*lx + ny*ly + nz*lz;
        if(diff < 0.0) diff = 0.0;

        float hx = lx+vx, hy = ly+vy, hz = lz+vz;
        float hi = isqrt(hx*hx + hy*hy + hz*hz);
        float ndoth = nx*hx*hi + ny*hy*hi + nz*hz*hi;
        if(ndoth < 0.0) ndoth = 0.0;
        float spec = ndoth*ndoth; spec = spec*spec; spec = spec*spec; spec = spec*spec; spec = spec*spec;

        src_color.x = args->ambient.x + args->kd * diff * albedo.x + args->ks * spec;
        src_color.y = args->ambient.y + args->kd * diff * albedo.y + args->ks * spec;
        src_color.z = args->ambient.z + args->kd * diff * albedo.z + args->ks * spec;
        src_color.w = albedo.w;
    }

    if (src_color.w <= 0.0) {
        return;
    }

    int pixel_idx = GET_1D_INDEX(u, v, args->buff_w);
    vec4_t dest_color = args->color[pixel_idx];

    vec4_t final_color;
    final_color.x = (src_color.x * src_color.w) + (dest_color.x * (1.0 - src_color.w));
    final_color.y = (src_color.y * src_color.w) + (dest_color.y * (1.0 - src_color.w));
    final_color.z = (src_color.z * src_color.w) + (dest_color.z * (1.0 - src_color.w));
    final_color.w = src_color.w + dest_color.w * (1.0 - src_color.w);

    args->color[pixel_idx] = final_color;
}