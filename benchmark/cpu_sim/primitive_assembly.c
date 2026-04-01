#include "include/graphics_lib.h"

// Screen dimensions for trivial reject stage
#define SCREEN_W 800
#define SCREEN_H 800

// Primitive Assembly Unit
// 1. Assembly
// 2. Back-face Culling
// 3. Trivial Reject

int primitive_assembly(vertex_t* vertex_output_buffer, triangle_t* triangle_index_buffer, int num_tris, triangle_t* surviving_triangle_index_buffer) {
    
    // number of triangles that passed all stages and ready for rasterization
    int valid_tri_count = 0;

    for (int i = 0; i < num_tris; i++) {
        
        // 1. assembly
        vertex_t p1 = vertex_output_buffer[triangle_index_buffer[i].v1];
        vertex_t p2 = vertex_output_buffer[triangle_index_buffer[i].v2];
        vertex_t p3 = vertex_output_buffer[triangle_index_buffer[i].v3];

        // 2. back-face culling
        float vecA_x = p2.coords.x - p1.coords.x;
        float vecA_y = p2.coords.y - p1.coords.y;
        float vecB_x = p3.coords.x - p1.coords.x;
        float vecB_y = p3.coords.y - p1.coords.y;

        // cross product of z: (Ax * By) - (Ay * Bx)
        float cross_z = (vecA_x * vecB_y) - (vecA_y * vecB_x);

        // discard back-facing triangles (assuming counter-clockwise winding is front-facing)
        if (cross_z > 0.0f) continue;

        // 3. trivial reject
        // discard triangles that are completely outside the screen bounds (simple bounding box check)
        // x-axis check
        if (p1.coords.x < 0 && p2.coords.x < 0 && p3.coords.x < 0) continue;
        if (p1.coords.x > SCREEN_W && p2.coords.x > SCREEN_W && p3.coords.x > SCREEN_W) continue;
        
        // y-axis check
        if (p1.coords.y < 0 && p2.coords.y < 0 && p3.coords.y < 0) continue;
        if (p1.coords.y > SCREEN_H && p2.coords.y > SCREEN_H && p3.coords.y > SCREEN_H) continue;

        // 4. output write
        // copy triangle indices
        surviving_triangle_index_buffer[valid_tri_count] = triangle_index_buffer[i];
        
        // valid triangle count update
        valid_tri_count++;
    }

    // final count of valid triangles
    return valid_tri_count;
}