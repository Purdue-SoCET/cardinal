#include "include/kernel.h"
#include "include/pixel.h"
#include "include/graphics_lib.h"

void kernel_pixel(void* arg) {
    pixel_arg_t* args = (pixel_arg_t*) arg;
    
    int u, v;
    u = mod(threadIdx, args->buff_w);
    v = mod(threadIdx / args->buff_w, args->buff_h);
    
    int tag = args->tag_buff[threadIdx];
    if(tag > 100) {
        printf("Pixel Kernel on p = <%d, %d>\n", u, v);
        printf("\t Got tag = %d\n", tag);
    }
    if(tag < 0) return;

    triangle_t tri = args->tris[tag];
    


    // Make the pixel a point in screen-space
    vector_t point;
    point.x = u + 0.5f;
    point.y = v + 0.5f;
    point.z = 1.0f;

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
    vector_t l = barycentric_coordinates(point, coords);

    // Get new texture interpolation
    float correction_factor = l.x * (pVs[0].coords.z) + l.y * (pVs[1].coords.z) + l.z * (pVs[2].coords.z);

    float s = l.x * (pVs[0].s * pVs[0].coords.z) + l.y * (pVs[1].s * pVs[1].coords.z) + l.z * (pVs[2].s * pVs[2].coords.z);
    s = s / (correction_factor);

    float t = l.x * (pVs[0].t * pVs[0].coords.z) + l.y * (pVs[1].t * pVs[1].coords.z) + l.z * (pVs[2].t * pVs[2].coords.z);
    t = t / (correction_factor);

    args->color[threadIdx] = get_texture(args->texture, s, t);
}