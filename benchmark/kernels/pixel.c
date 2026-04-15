#include "include/kernel.h"
#include "include/pixel.h"
#include "../cpu_sim/include/graphics_lib.h"
#define ENABLE_LIGHTING 1

void barycentric_coordinates(vector_t* l, vector_t point, vector_t triangle_verts[3]);
void get_texture(vector_t* col, texture_t texture, float u, float v);

void kernel_pixel(void* arg) {
    pixel_arg_t* args = (pixel_arg_t*) arg;
    int i = blockIdx * blockDim + threadIdx;
    int pixel_count = args->buffer_w * args->buffer_h;
    if (i >= pixel_count) return;
    
    int screen_x, screen_y;
    screen_x = i % args->buffer_w;
    screen_y = i / args->buffer_w;

    int tag = args->tag_buffer[i];
    if(tag < 0) return;

    triangle_t tri = args->surviving_triangle_index_buffer[tag];

    // Make the pixel a point in screen-space
    vector_t point;
    float value_half = 0.5f;
    point.x = itof(screen_x) + value_half;
    point.y = itof(screen_y) + value_half;
    point.z = 1.0f;

    // Get the coords for the known triangle verticies
    vertex_t triangle_verts[3];
    triangle_verts[0] = args->assembled_vertex_buffer[tri.v1];
    triangle_verts[1] = args->assembled_vertex_buffer[tri.v2];
    triangle_verts[2] = args->assembled_vertex_buffer[tri.v3];

    vector_t coords[3];
    coords[0] = triangle_verts[0].coords;
    coords[1] = triangle_verts[1].coords;
    coords[2] = triangle_verts[2].coords;

    // Get Barycentric coordinates
    vector_t l;
    barycentric_coordinates(&l, point, coords);

    // Interpolate texture coordinates across the final assembled screen-space triangle.
    // True perspective-correct interpolation would require carrying reciprocal-w from the
    // pre-divide stage into the assembled vertex buffer. At this stage, coords.z is screen-space
    // depth, so do not use it as a perspective correction term.
    float interp_inv_w = l.x * triangle_verts[0].inv_w + l.y * triangle_verts[1].inv_w + l.z * triangle_verts[2].inv_w;
    float interp_u_over_w = l.x * triangle_verts[0].u_over_w + l.y * triangle_verts[1].u_over_w + l.z * triangle_verts[2].u_over_w;
    float interp_v_over_w = l.x * triangle_verts[0].v_over_w + l.y * triangle_verts[1].v_over_w + l.z * triangle_verts[2].v_over_w;

    float tex_u = 0.0f;
    float tex_v = 0.0f;

    if (interp_inv_w != 0.0f) {
        tex_u = interp_u_over_w / interp_inv_w;
        tex_v = interp_v_over_w / interp_inv_w;
    }

    // call Texture Mapping
    vector_t texture_color;
    get_texture(&texture_color, args->texture_buffer, tex_u, tex_v);
    
    // simple lighting calculation using interpolated intensity
#if ENABLE_LIGHTING
    float interp_intensity = (l.x * triangle_verts[0].intensity) + (l.y * triangle_verts[1].intensity) + (l.z * triangle_verts[2].intensity);
#else
    float interp_intensity = 0.7f;
#endif
    if (interp_intensity < 0.0f) interp_intensity = 0.0f;
    if (interp_intensity > 1.0f) interp_intensity = 1.0f;

    // calculate final color with lighting applied
    vector_t final_color;
    final_color.x = texture_color.x * interp_intensity;
    final_color.y = texture_color.y * interp_intensity;
    final_color.z = texture_color.z * interp_intensity;

    // clamp final color to [0, 1] because frame_buffer stores normalized float RGB values.
    if (final_color.x < 0.0f) final_color.x = 0.0f;
    if (final_color.y < 0.0f) final_color.y = 0.0f;
    if (final_color.z < 0.0f) final_color.z = 0.0f;
    if (final_color.x > 1.0f) final_color.x = 1.0f;
    if (final_color.y > 1.0f) final_color.y = 1.0f;
    if (final_color.z > 1.0f) final_color.z = 1.0f;

    // save final color to frame buffer
    args->frame_buffer[i] = final_color;
}