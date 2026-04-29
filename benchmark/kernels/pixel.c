#include "include/kernel.h"
#include "include/pixel.h"
#include "include/graphics_lib.h"

#ifdef CPU_SIM
void kernel_pixel(void* arg)
#else
void kernel_pixel()
#endif
{
    #ifdef CPU_SIM
    pixel_arg_t* args = (pixel_arg_t*) arg;
    #else
    pixel_arg_t* args = (pixel_arg_t*) argPtr();
    #endif

    int global_id = (blockIdx * blockDim) + threadIdx;

    // 1. Boundary check
    if(global_id < (args->buff_w * args->buff_h)) {

        int u = (((global_id)) - (args->buff_w) * (((global_id))/(args->buff_w)));
        int v = (((global_id) / args->buff_w) - (args->buff_h)*(((global_id) / args->buff_w)/(args->buff_h)));
        int tag = args->tag_buff[global_id];

        // 2. Only process pixels that belong to a triangle
        if(tag >= 0) {
            
            // fetch triangle indices 
            int v1_idx = args->tri_v1[tag];
            int v2_idx = args->tri_v2[tag];
            int v3_idx = args->tri_v3[tag];

            // We only fetch x and y for the determinant, and z later if needed.
            float x0 = args->v_x[v1_idx], y0 = args->v_y[v1_idx];
            float x1 = args->v_x[v2_idx], y1 = args->v_y[v2_idx];
            float x2 = args->v_x[v3_idx], y2 = args->v_y[v3_idx];

            float value_half = 0.5;
            float px = itof(u) + value_half;
            float py = itof(v) + value_half;

            // Barycentric Matrix 
            float m00 = 1.0; float m01 = 1.0; float m02 = 1.0;
            float m10 = x0;   float m11 = x1;   float m12 = x2;
            float m20 = y0;   float m21 = y1;   float m22 = y2;

            float det = m00 * (m11 * m22 - m21 * m12) -
                        m01 * (m10 * m22 - m12 * m20) +
                        m02 * (m10 * m21 - m11 * m20);

            if (det <= -0.00001 || det >= 0.00001) {
                float invDet = 1.0 / det;

                // Barycentric weights 
                float l_x = ((m11 * m22 - m21 * m12) + (m02 * m21 - m01 * m22) * px + (m01 * m12 - m02 * m11) * py) * invDet;
                float l_y = ((m12 * m20 - m10 * m22) + (m00 * m22 - m02 * m20) * px + (m02 * m10 - m00 * m12) * py) * invDet;
                float l_z = ((m10 * m21 - m20 * m11) + (m20 * m01 - m00 * m21) * px + (m00 * m11 - m10 * m01) * py) * invDet;

                vec4_t albedo = args->albedo;

                // TEXTURE MAPPING
                if(args->texture.color_arr != 0) {
                    // Fetch Z for perspective correction 
                    float z0 = args->v_z[v1_idx];
                    float z1 = args->v_z[v2_idx];
                    float z2 = args->v_z[v3_idx];

                    // Fetch S and T 
                    float s0 = args->v_s[v1_idx], t0 = args->v_t[v1_idx];
                    float s1 = args->v_s[v2_idx], t1 = args->v_t[v2_idx];
                    float s2 = args->v_s[v3_idx], t2 = args->v_t[v3_idx];

                    float correction = l_x * z0 + l_y * z1 + l_z * z2;
                    float s = (l_x * s0 * z0 + l_y * s1 * z1 + l_z * s2 * z2) / correction;
                    float t = (l_x * t0 * z0 + l_y * t1 * z1 + l_z * t2 * z2) / correction;

                    // Manual Frac/Texel conversion
                    float s_abs = 0.0 - s;
                    float t_abs = 0.0 - t;

                    if(s>0.0){
                        s_abs = s;
                    }
                    if(t>0.0){
                        t_abs = t;
                    }

                    float w_minus_1 = itof(args->texture.w - 1);
                    float h_minus_1 = itof(args->texture.h - 1);

                    float s_fract = s_abs - itof(ftoi(s_abs));
                    float t_fract = t_abs - itof(ftoi(t_abs));

                    int texel_x = ftoi(s_fract * w_minus_1 + 0.5);
                    int texel_y = ftoi(t_fract * h_minus_1 + 0.5);

                    albedo = args->texture.color_arr[texel_y * args->texture.w + texel_x];
                }

                // LIGHTING (PHONG)
                if(args->trans_x == 0) {
                    args->color_r[global_id] = albedo.x;
                    args->color_g[global_id] = albedo.y;
                    args->color_b[global_id] = albedo.z;
                    args->color_a[global_id] = albedo.w;
                } else {
                    // Interpolate world coordinates from SoA arrays
                    float wx = l_x * args->trans_x[v1_idx] + l_y * args->trans_x[v2_idx] + l_z * args->trans_x[v3_idx];
                    float wy = l_x * args->trans_y[v1_idx] + l_y * args->trans_y[v2_idx] + l_z * args->trans_y[v3_idx];
                    float wz = l_x * args->trans_z[v1_idx] + l_y * args->trans_z[v2_idx] + l_z * args->trans_z[v3_idx];

                    // Surface Normal (assuming sphere-like normals for the demo)
                    float nx = wx - args->sphere_center.x, ny = wy - args->sphere_center.y, nz = wz - args->sphere_center.z;
                    float ni = isqrt(nx*nx + ny*ny + nz*nz);
                    nx *= ni; ny *= ni; nz *= ni;

                    // Light Direction
                    float lx = args->light_pos.x - wx, ly = args->light_pos.y - wy, lz = args->light_pos.z - wz;
                    float li = isqrt(lx*lx + ly*ly + lz*lz);
                    lx *= li; ly *= li; lz *= li;

                    // View Direction
                    float vx = args->camera.x - wx, vy = args->camera.y - wy, vz = args->camera.z - wz;
                    float vi = isqrt(vx*vx + vy*vy + vz*vz);
                    vx *= vi; vy *= vi; vz *= vi;

                    float diff = nx*lx + ny*ly + nz*lz;
                    if(diff < 0.0) diff = 0.0;

                    // Specular (Rough Approximation)
                    float hx = lx+vx, hy = ly+vy, hz = lz+vz;
                    float hi = isqrt(hx*hx + hy*hy + hz*hz);
                    float ndoth = nx*hx*hi + ny*hy*hi + nz*hz*hi;
                    if(ndoth < 0.0) ndoth = 0.0;
                    float spec = ndoth*ndoth; spec *= spec; spec *= spec; spec *= spec; spec *= spec;

                    args->color_r[global_id] = args->ambient.x + args->kd * diff * albedo.x + args->ks * spec;
                    args->color_g[global_id] = args->ambient.y + args->kd * diff * albedo.y + args->ks * spec;
                    args->color_b[global_id] = args->ambient.z + args->kd * diff * albedo.z + args->ks * spec;
                }
            }
        }
    }
}

/*
#ifdef CPU_SIM
void kernel_pixel(void* arg)
#else
void kernel_pixel()
#endif
{
    int u, v;

    #ifdef CPU_SIM
    pixel_arg_t* args = (pixel_arg_t*) arg;
    #else
    pixel_arg_t* args = (pixel_arg_t*) argPtr();
    #endif

    int global_id = (blockIdx * blockDim) + threadIdx;

    // 1. Check if global_id is within valid buffer limits
    if(global_id < ((args->buff_w * args->buff_h)-1)) {

        u = (((global_id)) - (args->buff_w)*(((global_id))/(args->buff_w)));
        // u = mod(threadIdx, args->buff_w);
        v = (((global_id) / args->buff_w) - (args->buff_h)*(((global_id) / args->buff_w)/(args->buff_h)));
        // v = mod(threadIdx / args->buff_w, args->buff_h);

        int pixel_idx = global_id;
        int tag = args->tag_buff[global_id];

        // 2. Check if the tag is valid (>= 0)
        if(tag >= 0) {

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

            // INSERT THIS (Manually Inlined):
            float m00 = 1.0; float m01 = 1.0; float m02 = 1.0;
            float m10 = coords[0].x; float m11 = coords[1].x; float m12 = coords[2].x;
            float m20 = coords[0].y; float m21 = coords[1].y; float m22 = coords[2].y;

            // Calculate Determinant
            float det = m00 * (m11 * m22 - m21 * m12) -
                        m01 * (m10 * m22 - m12 * m20) +
                        m02 * (m10 * m21 - m11 * m20);

            // 3. Check if determinant is valid (outside of near-zero bounds)
            if (det <= -0.00001 || det >= 0.00001) {

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
                vec4_t albedo = args->albedo;

                // map texture if provided
                if(args->texture.color_arr != 0) {
                    float correction_factor = l.x * (pVs[0].coords.z) + l.y * (pVs[1].coords.z) + l.z * (pVs[2].coords.z);

                    float s = l.x * (pVs[0].s * pVs[0].coords.z) + l.y * (pVs[1].s * pVs[1].coords.z) + l.z * (pVs[2].s * pVs[2].coords.z);
                    s = s / (correction_factor);

                    float t = l.x * (pVs[0].t * pVs[0].coords.z) + l.y * (pVs[1].t * pVs[1].coords.z) + l.z * (pVs[2].t * pVs[2].coords.z);
                    t = t / (correction_factor);

                    // 1. Abs function for s and t
                    float s_abs = 0.0 - s;
                    float t_abs = 0.0 - t;

                    if(s>0.0){
                        s_abs = s;
                    }
                    if(t>0.0){
                        t_abs = t;
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

                // 4. Branch based on 3D translation availability (replaces the final return)
                if(args->threeDVertTrans == 0) {
                    args->color[pixel_idx] = albedo;
                } else {
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
                    args->color[pixel_idx].x = args->ambient.x + args->kd * diff * albedo.x + args->ks * spec;
                    args->color[pixel_idx].y = args->ambient.y + args->kd * diff * albedo.y + args->ks * spec;
                    args->color[pixel_idx].z = args->ambient.z + args->kd * diff * albedo.z + args->ks * spec;
                }
            }
        }
    }
}
*/