#include "include/kernel.h"
#include "include/pixel.h"
#include "include/graphics_lib.h"

#ifdef GPU_SIM
void main(void* arg)
#else
void kernel_pixel(void* arg)
#endif
{
    int u, v;
    #ifdef GPU_SIM
    pixel_arg_t* args = (pixel_arg_t*) argPtr();

    u = (((threadIdx())) - (args->buff_w)*(((threadIdx()))/(args->buff_w)));
    // u = mod(threadIdx, args->buff_w);
    v = (((threadIdx()) / args->buff_w) - (args->buff_h)*(((threadIdx()) / args->buff_w)/(args->buff_h)));
    // v = mod(threadIdx / args->buff_w, args->buff_h);

    int pixel_idx = threadIdx();
    
    int tag = args->tag_buff[threadIdx()];
    #else
    pixel_arg_t* args = (pixel_arg_t*) arg;

    u = (((threadIdx)) - (args->buff_w)*(((threadIdx))/(args->buff_w)));
    // u = mod(threadIdx, args->buff_w);
    v = (((threadIdx) / args->buff_w) - (args->buff_h)*(((threadIdx) / args->buff_w)/(args->buff_h)));
    // v = mod(threadIdx / args->buff_w, args->buff_h);

    int pixel_idx = threadIdx;
    
    int tag = args->tag_buff[threadIdx];
    #endif
    

    if(tag < 0) return;

    triangle_t tri = args->tris[tag];

    // Make the pixel a point in screen-space
    vector_t point;
    float value_half = 0.5;
    point.x = itof(u) + value_half;
    point.y = itof(v) + value_half;
    point.z = 1.0;

    // Get the coords for the known triangle verticies
    vertex_t pVs[3];
    pVs[0] = args->verts[tri.v1];
    pVs[1] = args->verts[tri.v2];
    pVs[2] = args->verts[tri.v3];

    vector_t coords[3];
    coords[0] = pVs[0].coords;
    coords[1] = pVs[1].coords;
    coords[2] = pVs[2].coords;

    // Get Barycentric coordinates
    // vector_t l;
    // barycentric_coordinates(&point, coords, &l);

    // INSERT THIS (Manually Inlined):
    float m00 = 1.0; float m01 = 1.0; float m02 = 1.0;
    float m10 = coords[0].x; float m11 = coords[1].x; float m12 = coords[2].x;
    float m20 = coords[0].y; float m21 = coords[1].y; float m22 = coords[2].y;

    // Calculate Determinant
    float det = m00 * (m11 * m22 - m21 * m12) -
                m01 * (m10 * m22 - m12 * m20) +
                m02 * (m10 * m21 - m11 * m20);

    if (det > -0.00001 && det < 0.00001) { // added to render teapot
        return; 
    }
    
    float invDet = 1.0 / det;

    // Calculate Inverse Row 0 (only needed for Barycentric x/y/z)
    float bc00 = (m11 * m22 - m21 * m12) * invDet;
    float bc01 = (m02 * m21 - m01 * m22) * invDet;
    float bc02 = (m01 * m12 - m02 * m11) * invDet;
    float bc10 = (m12 * m20 - m10 * m22) * invDet;
    float bc11 = (m00 * m22 - m02 * m20) * invDet;
    float bc12 = (m02 * m10 - m00 * m12) * invDet;
    float bc20 = (m10 * m21 - m20 * m11) * invDet;
    float bc21 = (m20 * m01 - m00 * m21) * invDet;
    float bc22 = (m00 * m11 - m10 * m01) * invDet;

    // Calculate 'l' (Barycentric Coords)
    vector_t l;
    l.x = bc00 + bc01 * point.x + bc02 * point.y;
    l.y = bc10 + bc11 * point.x + bc12 * point.y;
    l.z = bc20 + bc21 * point.x + bc22 * point.y;

    // base color for material
    vector_t albedo = args->albedo;

    // map texture if provided
    if(args->texture.color_arr != 0) {
        // Get new texture interpolation
        float correction_factor = l.x * (pVs[0].coords.z) + l.y * (pVs[1].coords.z) + l.z * (pVs[2].coords.z);

        float s = l.x * (pVs[0].s * pVs[0].coords.z) + l.y * (pVs[1].s * pVs[1].coords.z) + l.z * (pVs[2].s * pVs[2].coords.z);
        s = s / (correction_factor);

        float t = l.x * (pVs[0].t * pVs[0].coords.z) + l.y * (pVs[1].t * pVs[1].coords.z) + l.z * (pVs[2].t * pVs[2].coords.z);
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
        albedo = args->texture.color_arr[idx];
    }

    // if we cant calculate the lighting just exit
    if(args->threeDVertTrans == 0) {
        args->color[threadIdx] = albedo;
        return;
    }

    // phong lighting

    // interpolate between triangel for specific pixel location
    vector_t w0 = args->threeDVertTrans[tri.v1].coords;
    vector_t w1 = args->threeDVertTrans[tri.v2].coords;
    vector_t w2 = args->threeDVertTrans[tri.v3].coords;
    float wx = l.x*w0.x + l.y*w1.x + l.z*w2.x;
    float wy = l.x*w0.y + l.y*w1.y + l.z*w2.y;
    float wz = l.x*w0.z + l.y*w1.z + l.z*w2.z;

    // normal vector
    float nx = wx - args->sphere_center.x, ny = wy - args->sphere_center.y, nz = wz - args->sphere_center.z;
    float ni = isqrt(nx*nx + ny*ny + nz*nz);
    nx = nx*ni; ny = ny*ni; nz = nz*ni;

    // light vector
    float lx = args->light_pos.x - wx, ly = args->light_pos.y - wy, lz = args->light_pos.z - wz;
    float li = isqrt(lx*lx + ly*ly + lz*lz);
    lx = lx*li; ly = ly*li; lz = lz*li;

    // view vector
    float vx = args->camera.x - wx, vy = args->camera.y - wy, vz = args->camera.z - wz;
    float vi = isqrt(vx*vx + vy*vy + vz*vz);
    vx = vx*vi; vy = vy*vi; vz = vz*vi;

    // diffuse
    float diff = nx*lx + ny*ly + nz*lz;
    if(diff < 0.0) diff = 0.0;

    // specular approximation
    float hx = lx+vx, hy = ly+vy, hz = lz+vz;
    float hi = isqrt(hx*hx + hy*hy + hz*hz);
    float ndoth = nx*hx*hi + ny*hy*hi + nz*hz*hi;
    if(ndoth < 0.0) ndoth = 0.0;
    // no hardware exp
    float spec = ndoth*ndoth; spec = spec*spec; spec = spec*spec; spec = spec*spec; spec = spec*spec;

    // combine color
    args->color[threadIdx].x = args->ambient.x + args->kd * diff * albedo.x + args->ks * spec;
    args->color[threadIdx].y = args->ambient.y + args->kd * diff * albedo.y + args->ks * spec;
    args->color[threadIdx].z = args->ambient.z + args->kd * diff * albedo.z + args->ks * spec;
}