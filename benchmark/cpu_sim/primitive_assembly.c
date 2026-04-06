#include "include/graphics_lib.h"

#define SCREEN_W 800
#define SCREEN_H 800
#define CLIP_EPS 1e-6f
#define ENABLE_CLIPPING 1

// Primitive Assembly Unit
// 1. Read one input triangle in clip space
// 2. Reject triangles fully outside the clip-space frustum
// 3. Clip the surviving polygon against all 6 frustum planes
// 4. Triangulate the clipped polygon with triangle fan
// 5. Perspective divide
// 6. Viewport transform
// 7. Back-face culling in screen space
// 8. Output surviving triangle list for rasterization

// Clip-space convention:
// - x, y, z are clipped against [-w, +w] (OpenGL-style homogeneous clipping)
// - perspective divide produces screen-space depth where smaller z is closer
// - after viewport y-flip, screen-space back-face culling uses cross_z > 0 as back-facing

static float absf_local(float x) {
    return (x < 0.0f) ? -x : x;
}

static vertex_t interpolate_vertex(vertex_t a, vertex_t b, float t) {
    vertex_t out = {0};

    out.coords.x = a.coords.x + t * (b.coords.x - a.coords.x);
    out.coords.y = a.coords.y + t * (b.coords.y - a.coords.y);
    out.coords.z = a.coords.z + t * (b.coords.z - a.coords.z);
    out.w = a.w + t * (b.w - a.w);

    out.u = a.u + t * (b.u - a.u);
    out.v = a.v + t * (b.v - a.v);

    out.normal.x = a.normal.x + t * (b.normal.x - a.normal.x);
    out.normal.y = a.normal.y + t * (b.normal.y - a.normal.y);
    out.normal.z = a.normal.z + t * (b.normal.z - a.normal.z);

    out.intensity = a.intensity + t * (b.intensity - a.intensity);
    
    out.inv_w = a.inv_w + t * (b.inv_w - a.inv_w);
    out.u_over_w = a.u_over_w + t * (b.u_over_w - a.u_over_w);
    out.v_over_w = a.v_over_w + t * (b.v_over_w - a.v_over_w);
    return out;
}

static int reject_outside_frustum(vertex_t v0, vertex_t v1, vertex_t v2) {
    // Entire triangle is outside one clip plane, so it can be rejected immediately.
    if (v0.coords.x < -v0.w && v1.coords.x < -v1.w && v2.coords.x < -v2.w) return 1; // left
    if (v0.coords.x >  v0.w && v1.coords.x >  v1.w && v2.coords.x >  v2.w) return 1; // right
    if (v0.coords.y < -v0.w && v1.coords.y < -v1.w && v2.coords.y < -v2.w) return 1; // bottom
    if (v0.coords.y >  v0.w && v1.coords.y >  v1.w && v2.coords.y >  v2.w) return 1; // top
    if (v0.coords.z < -v0.w && v1.coords.z < -v1.w && v2.coords.z < -v2.w) return 1; // near
    // if (v0.coords.z < 0.0f && v1.coords.z < 0.0f && v2.coords.z < 0.0f) return 1; // near
    if (v0.coords.z >  v0.w && v1.coords.z >  v1.w && v2.coords.z >  v2.w) return 1; // far
    return 0;
}

static int clip_left_plane(const vertex_t* in_poly, int in_count, vertex_t* out_poly) {
    int out_vertex_count = 0;

    for (int i = 0; i < in_count; i++) {
        vertex_t curr_vertex = in_poly[i];
        vertex_t prev_vertex = in_poly[(i - 1 + in_count) % in_count];

        float curr_dist = curr_vertex.coords.x + curr_vertex.w;
        float prev_dist = prev_vertex.coords.x + prev_vertex.w;
        int curr_inside = (curr_dist >= 0.0f);
        int prev_inside = (prev_dist >= 0.0f);

        if (curr_inside != prev_inside) {
            float denom = prev_dist - curr_dist;
            float t = (absf_local(denom) > CLIP_EPS) ? (prev_dist / denom) : 0.0f;
            out_poly[out_vertex_count++] = interpolate_vertex(prev_vertex, curr_vertex, t);
        }

        if (curr_inside) {
            out_poly[out_vertex_count++] = curr_vertex;
        }
    }

    return out_vertex_count;
}

static int clip_right_plane(const vertex_t* in_poly, int in_count, vertex_t* out_poly) {
    int out_vertex_count = 0;

    for (int i = 0; i < in_count; i++) {
        vertex_t curr_vertex = in_poly[i];
        vertex_t prev_vertex = in_poly[(i - 1 + in_count) % in_count];

        float curr_dist = curr_vertex.w - curr_vertex.coords.x;
        float prev_dist = prev_vertex.w - prev_vertex.coords.x;
        int curr_inside = (curr_dist >= 0.0f);
        int prev_inside = (prev_dist >= 0.0f);

        if (curr_inside != prev_inside) {
            float denom = prev_dist - curr_dist;
            float t = (absf_local(denom) > CLIP_EPS) ? (prev_dist / denom) : 0.0f;
            out_poly[out_vertex_count++] = interpolate_vertex(prev_vertex, curr_vertex, t);
        }

        if (curr_inside) {
            out_poly[out_vertex_count++] = curr_vertex;
        }
    }

    return out_vertex_count;
}

static int clip_bottom_plane(const vertex_t* in_poly, int in_count, vertex_t* out_poly) {
    int out_vertex_count = 0;

    for (int i = 0; i < in_count; i++) {
        vertex_t curr_vertex = in_poly[i];
        vertex_t prev_vertex = in_poly[(i - 1 + in_count) % in_count];

        float curr_dist = curr_vertex.coords.y + curr_vertex.w;
        float prev_dist = prev_vertex.coords.y + prev_vertex.w;
        int curr_inside = (curr_dist >= 0.0f);
        int prev_inside = (prev_dist >= 0.0f);

        if (curr_inside != prev_inside) {
            float denom = prev_dist - curr_dist;
            float t = (absf_local(denom) > CLIP_EPS) ? (prev_dist / denom) : 0.0f;
            out_poly[out_vertex_count++] = interpolate_vertex(prev_vertex, curr_vertex, t);
        }

        if (curr_inside) {
            out_poly[out_vertex_count++] = curr_vertex;
        }
    }

    return out_vertex_count;
}

static int clip_top_plane(const vertex_t* in_poly, int in_count, vertex_t* out_poly) {
    int out_vertex_count = 0;

    for (int i = 0; i < in_count; i++) {
        vertex_t curr_vertex = in_poly[i];
        vertex_t prev_vertex = in_poly[(i - 1 + in_count) % in_count];

        float curr_dist = curr_vertex.w - curr_vertex.coords.y;
        float prev_dist = prev_vertex.w - prev_vertex.coords.y;
        int curr_inside = (curr_dist >= 0.0f);
        int prev_inside = (prev_dist >= 0.0f);

        if (curr_inside != prev_inside) {
            float denom = prev_dist - curr_dist;
            float t = (absf_local(denom) > CLIP_EPS) ? (prev_dist / denom) : 0.0f;
            out_poly[out_vertex_count++] = interpolate_vertex(prev_vertex, curr_vertex, t);
        }

        if (curr_inside) {
            out_poly[out_vertex_count++] = curr_vertex;
        }
    }

    return out_vertex_count;
}

static int clip_near_plane(const vertex_t* in_poly, int in_count, vertex_t* out_poly) {
    int out_vertex_count = 0;

    for (int i = 0; i < in_count; i++) {
        vertex_t curr_vertex = in_poly[i];
        vertex_t prev_vertex = in_poly[(i - 1 + in_count) % in_count];

        float curr_dist = curr_vertex.coords.z + curr_vertex.w;
        float prev_dist = prev_vertex.coords.z + prev_vertex.w;
        // float curr_dist = curr_vertex.coords.z;
        // float prev_dist = prev_vertex.coords.z;
        int curr_inside = (curr_dist >= 0.0f);
        int prev_inside = (prev_dist >= 0.0f);

        if (curr_inside != prev_inside) {
            float denom = prev_dist - curr_dist;
            float t = (absf_local(denom) > CLIP_EPS) ? (prev_dist / denom) : 0.0f;
            out_poly[out_vertex_count++] = interpolate_vertex(prev_vertex, curr_vertex, t);
        }

        if (curr_inside) {
            out_poly[out_vertex_count++] = curr_vertex;
        }
    }

    return out_vertex_count;
}

static int clip_far_plane(const vertex_t* in_poly, int in_count, vertex_t* out_poly) {
    int out_vertex_count = 0;

    for (int i = 0; i < in_count; i++) {
        vertex_t curr_vertex = in_poly[i];
        vertex_t prev_vertex = in_poly[(i - 1 + in_count) % in_count];

        float curr_dist = curr_vertex.w - curr_vertex.coords.z;
        float prev_dist = prev_vertex.w - prev_vertex.coords.z;
        int curr_inside = (curr_dist >= 0.0f);
        int prev_inside = (prev_dist >= 0.0f);

        if (curr_inside != prev_inside) {
            float denom = prev_dist - curr_dist;
            float t = (absf_local(denom) > CLIP_EPS) ? (prev_dist / denom) : 0.0f;
            out_poly[out_vertex_count++] = interpolate_vertex(prev_vertex, curr_vertex, t);
        }

        if (curr_inside) {
            out_poly[out_vertex_count++] = curr_vertex;
        }
    }

    return out_vertex_count;
}

static int perspective_divide_vertex(vertex_t* v) {
    if (absf_local(v->w) < CLIP_EPS) {
        return 0;
    }

    v->coords.x /= v->w;
    v->coords.y /= v->w;
    v->coords.z /= v->w;
    return 1;
}

static void viewport_transform_vertex(vertex_t* v) {
    v->coords.x = (v->coords.x + 1.0f) * 0.5f * SCREEN_W;
    v->coords.y = (1.0f - v->coords.y) * 0.5f * SCREEN_H;
}

int primitive_assembly(const vertex_t* vertex_output_buffer, const triangle_t* triangle_index_buffer, int num_tris, vertex_t* assembled_vertex_buffer, int* assembled_vertex_count, int max_assembled_verts, triangle_t* surviving_triangle_index_buffer) {
    // number of triangles that passed all stages and ready for rasterization
    int surviving_tri_count = 0;
    int out_vertex_count = 0;

    for (int i = 0; i < num_tris; i++) {
        // 1. Read one input triangle in clip space
        vertex_t clip_v0 = vertex_output_buffer[triangle_index_buffer[i].v1];
        vertex_t clip_v1 = vertex_output_buffer[triangle_index_buffer[i].v2];
        vertex_t clip_v2 = vertex_output_buffer[triangle_index_buffer[i].v3];

        // 2. Reject triangles fully outside the clip-space frustum
        vertex_t clip_poly_a[10];
        vertex_t clip_poly_b[10];
        int clip_vertex_count = 3;

        clip_poly_a[0] = clip_v0;
        clip_poly_a[1] = clip_v1;
        clip_poly_a[2] = clip_v2;

#if ENABLE_CLIPPING
        if (reject_outside_frustum(clip_v0, clip_v1, clip_v2)) continue;

        // 3. Clip the surviving polygon against all 6 frustum planes
        clip_vertex_count = clip_left_plane(clip_poly_a, clip_vertex_count, clip_poly_b);
        if (clip_vertex_count < 3) continue;
        clip_vertex_count = clip_right_plane(clip_poly_b, clip_vertex_count, clip_poly_a);
        if (clip_vertex_count < 3) continue;
        clip_vertex_count = clip_bottom_plane(clip_poly_a, clip_vertex_count, clip_poly_b);
        if (clip_vertex_count < 3) continue;
        clip_vertex_count = clip_top_plane(clip_poly_b, clip_vertex_count, clip_poly_a);
        if (clip_vertex_count < 3) continue;
        clip_vertex_count = clip_near_plane(clip_poly_a, clip_vertex_count, clip_poly_b);
        if (clip_vertex_count < 3) continue;
        clip_vertex_count = clip_far_plane(clip_poly_b, clip_vertex_count, clip_poly_a);
        if (clip_vertex_count < 3) continue;
#endif

        // 4. Triangulate the clipped polygon with triangle fan
        for (int j = 1; j < clip_vertex_count - 1; j++) {
            vertex_t tri_v0 = clip_poly_a[0];
            vertex_t tri_v1 = clip_poly_a[j];
            vertex_t tri_v2 = clip_poly_a[j + 1];

            // 5. Perspective divide after clipping
            if (!perspective_divide_vertex(&tri_v0)) continue;
            if (!perspective_divide_vertex(&tri_v1)) continue;
            if (!perspective_divide_vertex(&tri_v2)) continue;

            // 6. Viewport transform into screen space
            viewport_transform_vertex(&tri_v0);
            viewport_transform_vertex(&tri_v1);
            viewport_transform_vertex(&tri_v2);

            // 7. Back-face culling in screen space
            float edge_a_x = tri_v1.coords.x - tri_v0.coords.x;
            float edge_a_y = tri_v1.coords.y - tri_v0.coords.y;
            float edge_b_x = tri_v2.coords.x - tri_v0.coords.x;
            float edge_b_y = tri_v2.coords.y - tri_v0.coords.y;
            float cross_z = (edge_a_x * edge_b_y) - (edge_a_y * edge_b_x);
            if (cross_z > 0.0f) continue;

            // 8. Write final screen-space vertices into the assembled vertex buffer
            if (out_vertex_count + 3 > max_assembled_verts) {
                *assembled_vertex_count = out_vertex_count;
                return surviving_tri_count;
            }

            int out0 = out_vertex_count++;
            int out1 = out_vertex_count++;
            int out2 = out_vertex_count++;

            assembled_vertex_buffer[out0] = tri_v0;
            assembled_vertex_buffer[out1] = tri_v1;
            assembled_vertex_buffer[out2] = tri_v2;

            surviving_triangle_index_buffer[surviving_tri_count].v1 = out0;
            surviving_triangle_index_buffer[surviving_tri_count].v2 = out1;
            surviving_triangle_index_buffer[surviving_tri_count].v3 = out2;
            surviving_tri_count++;
        }
    }

    *assembled_vertex_count = out_vertex_count;
    return surviving_tri_count;
}