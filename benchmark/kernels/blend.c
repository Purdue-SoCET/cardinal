#include "include/kernel.h"
#include "include/blend.h"

#ifdef GPU_SIM
void main(void* arg)
#else
void kernel_blend(void* arg)
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

    if(pix_z > args->depth_buff[GET_1D_INDEX(u, v, args->buff_w)]) {
        return;
    }

    if(args->texture.color_arr != 0) {
        // Get new texture interpolation
        float correction_factor = l[0] * (args->pVs[0].coords.z) + l[1] * (args->pVs[1].coords.z) + l[2] * (args->pVs[2].coords.z);

        float s = l[0] * (args->pVs[0].s * args->pVs[0].coords.z) + l[1] * (args->pVs[1].s * args->pVs[1].coords.z) + l[2] * (args->pVs[2].s * args->pVs[2].coords.z);
        s = s / (correction_factor);

        float t = l[0] * (args->pVs[0].t * args->pVs[0].coords.z) + l[1] * (args->pVs[1].t * args->pVs[1].coords.z) + l[2] * (args->pVs[2].t * args->pVs[2].coords.z);
        t = t / (correction_factor);


        // args->color[threadIdx] = get_texture(args->texture, s, t);
        // REPLACE WITH INLINED LOGIC:

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
        // Note: Breaking down math to avoid tree coverage errors
        float w_minus_1 = itof(args->texture.w - 1);
        float h_minus_1 = itof(args->texture.h - 1);
        
        // (s - (int)s)
        float s_fract = s_abs - itof(ftoi(s_abs));
        float t_fract = t_abs - itof(ftoi(t_abs));
        
        int texel_x = ftoi(s_fract * w_minus_1 + 0.5);
        int texel_y = ftoi(t_fract * h_minus_1 + 0.5);

        int idx = texel_y * args->texture.w + texel_x;

        vec4_t texel;
        texel = args->texture.color_arr[idx];
         // === 3. Alpha Blending ===
        // Early exit to save cycles if the pixel is fully transparent
        if (texel.w <= 0.0f) {
            return; 
        }

        // Fetch the existing color in the frame buffer 
        int pixel_idx = GET_1D_INDEX(u, v, args->buff_w);
        vec4_t dest_color = args->color[pixel_idx];

        // Standard Alpha Blending Equation
        vec4_t final_color;
        final_color.x = (texel.x * texel.w) + (dest_color.x * (1.0f - texel.w));
        final_color.y = (texel.y * texel.w) + (dest_color.y * (1.0f - texel.w));
        final_color.z = (texel.z * texel.w) + (dest_color.z * (1.0f - texel.w));
        final_color.w = texel.w + dest_color.w * (1.0f - texel.w); 

        args->color[pixel_idx] = final_color;
    }
}