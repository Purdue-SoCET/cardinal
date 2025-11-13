#include "include/kernel.h"
#include "include/pixel.h"
#include "include/graphics_lib.h"

void kernel_pixel(void* arg) {
    // Need to use strides to fit all operation 
    pixel_arg_t* args = (pixel_arg_t*) arg;
    
    int u, v;
    u = threadIdx.x; v = threadIdx.y;
    
    int tag = args.tag_buff[GET_1D_INDEX(u, v, args.buff_w)];
    triangle_t tri = args.tris[tag];


    // Make the pixel a point in screen-space
    vector_t point;
    point.x = u + 0.5f;
    point.y = y + 0.5f;
    point.z = 1.0f;

    // Get the coords for the known triangle verticies
    vertex_t pVs[3];
    pVs[0] = args.verts[tri.v1];
    pVs[1] = args.verts[tri.v2];
    pVs[2] = args.verts[tri.v3];

    vector_t coords;
    coords[0] = pVs[0].coords;
    coords[1] = pVs[1].coords;
    coords[2] = pVs[2].coords;

    // Get Barycentric coordinates
    vector_t l = barycentric_coordinates(point, coords);

    // Get new texture interpolation
    float s = l[0] * (pVs[0].s / pVs[0].coords.z) + l[1] * (pVs[1].s / pVs[1].coords.z) + l[2] * (pVs[2].s / pVs[2].coords.z);
    s = s / args.depth_buff[GET_1D_INDEX(u, v, args.buff_w)];

    float t = l[0] * (pVs[0].t / pVs[0].coords.z) + l[1] * (pVs[1].t / pVs[1].coords.z) + l[2] * (pVs[2].t / pVs[2].coords.z);
    t = t / args.depth_buff[GET_1D_INDEX(u, v, args.buff_w)];

    args.color[GET_1D_INDEX(u, v, args.buff_w)] = get_texture(args.texture, s, t);
    
}