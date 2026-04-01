#include "include/kernel.h"
#include "include/pixel.h"
#include "../cpu_sim/include/graphics_lib.h"

void barycentric_coordinates(vector_t* l, vector_t point, vector_t triangle_verts[3]);
void get_texture(vector_t* col, texture_t texture, float u, float v);

void kernel_pixel(void* arg) {
    pixel_arg_t* args = (pixel_arg_t*) arg;

    int pixel_count = args->buffer_w * args->buffer_h;
    if (threadIdx >= pixel_count) return;
    
    int screen_x, screen_y;
    screen_x = threadIdx % args->buffer_w;
    screen_y = threadIdx / args->buffer_w;

    int tag = args->tag_buffer[threadIdx];
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
    triangle_verts[0] = args->vertex_output_buffer[tri.v1];
    triangle_verts[1] = args->vertex_output_buffer[tri.v2];
    triangle_verts[2] = args->vertex_output_buffer[tri.v3];

    vector_t coords[3];
    coords[0] = triangle_verts[0].coords;
    coords[1] = triangle_verts[1].coords;
    coords[2] = triangle_verts[2].coords;

    // Get Barycentric coordinates
    vector_t l;
    barycentric_coordinates(&l, point, coords);

    // Get new texture interpolation (perspective correct interpolation)
    float correction_factor = (l.x * triangle_verts[0].coords.z) + (l.y * triangle_verts[1].coords.z) + (l.z * triangle_verts[2].coords.z);
    float tex_u = l.x * (triangle_verts[0].u * triangle_verts[0].coords.z) + l.y * (triangle_verts[1].u * triangle_verts[1].coords.z) + l.z * (triangle_verts[2].u * triangle_verts[2].coords.z);
    float tex_v = l.x * (triangle_verts[0].v * triangle_verts[0].coords.z) + l.y * (triangle_verts[1].v * triangle_verts[1].coords.z) + l.z * (triangle_verts[2].v * triangle_verts[2].coords.z);

    if (correction_factor != 0.0f) {
        tex_u /= correction_factor;
        tex_v /= correction_factor;
    }
    else {
        tex_u = 0.0f;
        tex_v = 0.0f;
    }

    // call Texture Mapping
    vector_t texture_color;
    get_texture(&texture_color, args->texture_buffer, tex_u, tex_v);
    
    // simple lighting calculation using interpolated intensity
    float interp_intensity = (l.x * triangle_verts[0].intensity) + (l.y * triangle_verts[1].intensity) + (l.z * triangle_verts[2].intensity);

    // calculate final color with lighting applied
    vector_t final_color;
    final_color.x = texture_color.x * interp_intensity;
    final_color.y = texture_color.y * interp_intensity;
    final_color.z = texture_color.z * interp_intensity;

    // clamp final color to [0, 255]
    if (final_color.x < 0.0f) final_color.x = 0.0f;
    if (final_color.y < 0.0f) final_color.y = 0.0f;
    if (final_color.z < 0.0f) final_color.z = 0.0f;
    if (final_color.x > 255.0f) final_color.x = 255.0f;
    if (final_color.y > 255.0f) final_color.y = 255.0f;
    if (final_color.z > 255.0f) final_color.z = 255.0f;

    // save final color to frame buffer
    args->frame_buffer[threadIdx] = final_color;
}