
// Standard Includes
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include "include/kernel_run.h"

// Include all needed kernels
#include "../kernels/include/graphics_lib.h"
#include "../kernels/include/vertexShader.h"
#include "../kernels/include/triangle.h"
#include "../kernels/include/pixel.h"

// Globals
uint8_t* memory_ptr;

// Defines
#define OUTPUT_W 800 // 680
#define OUTPUT_H 800 // 480

#define VERTEX_DEBUG 1
#define TRIANGLE_DEBUG 0
#define PIXEL_DEBUG 0

// Macros
#define ALLOCATE_MEM(dest, type, num) \
    type* dest = (type*) memory_ptr; \
    memory_ptr += num * sizeof(type);

#define MAKE_VECTOR(vector, ix, iy, iz) { \
    vector.x = ix; \
    vector.y = iy; \
    vector.z = iz; \
}

#define MAKE_VERTEX(vertex, ix, iy, iz, is, it) { \
    MAKE_VECTOR(vertex.coords, ix, iy, iz); \
    vertex.s = is; vertex.t = it; \
}

#define MAKE_TRI(tri, iv1, iv2, iv3) { \
    tri.v1 = iv1; \
    tri.v2 = iv2; \
    tri.v3 = iv3; \
}

#define MAX2(a, b) (a > b ? a : b)
#define MIN2(a, b) (a < b ? a : b)
#define MAX3(a, b, c) MAX2(a, MAX2(b, c))
#define MIN3(a, b, c) MIN2(a, MIN2(b, c))

#define DEFAULT_ARR(arr, len, def) { \
    for(int DFAx = 0; DFAx < len; DFAx++) { \
        arr[DFAx] = def; \
    } \
}



int main(int argc, char** argv) {
    uint8_t* memory_base = (uint8_t*) malloc(MEMORY_SIZE - STACK_SIZE - TEXT_SIZE);
    uint8_t* memory_ptr = memory_base;

    // ---- Setup Geometry ----
    // Single Triangle, all in a single plane

    // Vertexs
        const int num_verts = 8;

        // Allocation
        ALLOCATE_MEM(verts, vertex_t, num_verts);

        // Definition
        // Front Face
        MAKE_VERTEX(verts[0], -10, -10, -20, 0, 0); // BL
        MAKE_VERTEX(verts[1], -10,  10, -20, 0, 1); // TL
        MAKE_VERTEX(verts[2],  10, -10, -20, 1, 0); // BR
        MAKE_VERTEX(verts[3],  10,  10, -20, 1, 1); // TR

        // Back Face
        MAKE_VERTEX(verts[4], -10, -10, -40, 0, 1); // BL
        MAKE_VERTEX(verts[5], -10,  10, -40, 1, 1); // TL
        MAKE_VERTEX(verts[6],  10, -10, -40, 0, 0); // BR
        MAKE_VERTEX(verts[7],  10,  10, -40, 1, 0); // TR

    // Triangles
        const int num_tris = 12;

        // Allocation
        ALLOCATE_MEM(tris, triangle_t, num_tris);

        // Definition
        // Front of Cube
        MAKE_TRI(tris[0], 0, 1, 2);
        MAKE_TRI(tris[1], 3, 1, 2);
        
        // Back of Cube
        MAKE_TRI(tris[6], 4, 5, 6);
        MAKE_TRI(tris[7], 7, 5, 6);

        // Top of Cube
        MAKE_TRI(tris[2], 1, 3, 5);
        MAKE_TRI(tris[3], 7, 3, 5);

        // Bottom of Cube
        MAKE_TRI(tris[4], 0, 2, 4);
        MAKE_TRI(tris[5], 6, 2, 4);

        // Left of Cube
        MAKE_TRI(tris[8], 0, 1, 4);
        MAKE_TRI(tris[9], 5, 1, 4);

        // Right of Cube
        MAKE_TRI(tris[10], 2, 3, 6);
        MAKE_TRI(tris[11], 7, 3, 6);



    // Texture
        const int text_w = 10, text_h = 10;

        // Allocation
        ALLOCATE_MEM(texture, texture_t, 1);
        ALLOCATE_MEM(color_map, vector_t, (text_w * text_h));

        // Definition
        texture->w = text_w; texture->h = text_h;
        texture->color_arr = color_map;
        for(int u = 0; u < text_w; u++) {
            for(int v = 0; v < text_h; v++) {
                // Make red/blue checkerboard texture
                const vector_t red = {1.0f, 1.0f, 1.0f}; const vector_t blue = {0.0f, 0.0f, 0.0f};
                texture->color_arr[GET_1D_INDEX(u, v, text_w)] = (u+v+1) % 2 ? red : blue;
            }
        }

    // Camera
        const vector_t abc[3] = {
            {1.0f, 0.0f, 0.0f}, 
            {0.0f, -1.0f, 0.0f}, 
            {-OUTPUT_W/2, OUTPUT_H/2, -150.0f},
        };

        const vector_t abcTranspose[3] = {
            {abc[0].x, abc[1].x, abc[2].x},
            {abc[0].y, abc[1].y, abc[2].y},
            {abc[0].z, abc[1].z, abc[2].z}
        };

        // Allocation
        ALLOCATE_MEM(camera_C, vector_t, 1);
        ALLOCATE_MEM(cameraProjMatrix, float, 9);

        // Definition
        camera_C->x = 0.0f; camera_C->y = 0.0f; camera_C->z = 0.0f;
        matrix_inversion((float*)abcTranspose, cameraProjMatrix);


    // --- Vertex Kernel ---
    ALLOCATE_MEM(vertex_args, vertexShader_arg_t, 1);
    
    // Setup Transformation
        ALLOCATE_MEM(Oa, vector_t, 1);
        vertex_args->Oa = Oa;
        MAKE_VECTOR((*Oa), 0, 0, -30);

        ALLOCATE_MEM(a_dist, vector_t, 1);
        vertex_args->a_dist = a_dist;
        MAKE_VECTOR((*a_dist), 0, 1, 0); // Rotate around z

        ALLOCATE_MEM(alpha_r, float, 1);
        vertex_args->alpha_r = alpha_r;
        *alpha_r = 3.14f * 0.2f; // Assume no rotation for now

    // Give geometry inputs
        vertex_args->threeDVert = verts;
        vertex_args->camera = camera_C;
        vertex_args->invTrans = cameraProjMatrix;
    
    // Allocate Output Space
        ALLOCATE_MEM(tVerts, vertex_t, num_verts);
        vertex_args->threeDVertTrans = tVerts;
        ALLOCATE_MEM(pVerts, vertex_t, num_verts);
        vertex_args->twoDVert = pVerts;
    
    // Running the Kernel
    {
        dim_t grid_dim = {1, 1, 1}; dim_t block_dim = {num_verts, 1, 1};
        run_kernel(kernel_vertexShader, grid_dim, block_dim, (void*)vertex_args);
    }

    // Checking Vertex Output
    if(VERTEX_DEBUG) 
    {
        for(int i = 0; i < num_verts; i++) {
            printf(" --- Vertex %d --- \n", i);
            printf("3D:");
            printf("\t%+06.2f %+06.2f %+06.2f - %.2f %.2f\n", vertex_args->threeDVert[i].coords.x, vertex_args->threeDVert[i].coords.y, vertex_args->threeDVert[i].coords.z, vertex_args->threeDVert[i].s, vertex_args->threeDVert[i].t);
            printf("3Dt:");
            printf("\t%+06.2f %+06.2f %+06.2f - %.2f %.2f\n", vertex_args->threeDVertTrans[i].coords.x, vertex_args->threeDVertTrans[i].coords.y, vertex_args->threeDVertTrans[i].coords.z, vertex_args->threeDVertTrans[i].s, vertex_args->threeDVertTrans[i].t);
            printf("2D:");
            printf("\t%+06.2f %+06.2f %+06.2f - %.2f %.2f\n", vertex_args->twoDVert[i].coords.x, vertex_args->twoDVert[i].coords.y, vertex_args->twoDVert[i].coords.z, vertex_args->twoDVert[i].s, vertex_args->twoDVert[i].t);
        }
        printf(" --- Vertex end --- \n");
    }

    // --- Triangle Kernel ---
    // Only one call - still implement multi triangle framework
    ALLOCATE_MEM(triangle_args, triangle_arg_t, 1);

    // Setup Pixel Buffers
        const int frame_w = OUTPUT_W; const int frame_h = OUTPUT_H;
        ALLOCATE_MEM(zbuff, float, frame_w*frame_h);
        DEFAULT_ARR(zbuff, frame_w*frame_h, 0);
        ALLOCATE_MEM(tbuff, int, frame_w*frame_h);
        DEFAULT_ARR(tbuff, frame_w*frame_h, -1);

        triangle_args->buff_w = frame_w;
        triangle_args->buff_h = frame_h;
        triangle_args->depth_buff = zbuff;
        triangle_args->tag_buff = tbuff;

    // Setup and launch each triangle kernel
    for(int tri = 0; tri < num_tris; tri++) {
        // Set Tag
        triangle_args->tag = tri;

        // Collect Verticies
        triangle_args->pVs[0] = pVerts[tris[tri].v1].coords;
        triangle_args->pVs[1] = pVerts[tris[tri].v2].coords;
        triangle_args->pVs[2] = pVerts[tris[tri].v3].coords;
        
        // Find Bounding Box
        int u_min, u_max;
        u_min = MIN3(triangle_args->pVs[0].x, triangle_args->pVs[1].x, triangle_args->pVs[2].x) - .5;
        u_min = u_min < 0 ? 0 : u_min;
        u_max = MAX3(triangle_args->pVs[0].x, triangle_args->pVs[1].x, triangle_args->pVs[2].x) + .5;
        u_max = u_max > (frame_w-1) ? (frame_w-1) : u_max;
        int v_min, v_max;
        v_min = MIN3(triangle_args->pVs[0].y, triangle_args->pVs[1].y, triangle_args->pVs[2].y) - .5;
        v_min = v_min < 0 ? 0 : v_min;
        v_max = MAX3(triangle_args->pVs[0].y, triangle_args->pVs[1].y, triangle_args->pVs[2].y) + .5;
        v_max = v_max > (frame_h-1) ? (frame_h-1) : v_max;

        triangle_args->bb_start[0] = u_min;
        triangle_args->bb_start[1] = v_min;

        // Find barycentric Matrix
        float m[3][3] = {
            {1, 1, 1},
            {triangle_args->pVs[0].x, triangle_args->pVs[1].x, triangle_args->pVs[2].x},
            {triangle_args->pVs[0].y, triangle_args->pVs[1].y, triangle_args->pVs[2].y}
        };
        matrix_inversion((float*)m, (float*) triangle_args->bc_im);

        // Running the Kernel
        dim_t grid_dim = {1, 1, 1}; dim_t block_dim = {u_max, v_max, 1};
        run_kernel(kernel_triangle, grid_dim, block_dim, (void*)triangle_args);
    }

    // Checking TRIANGLE Output
    if(TRIANGLE_DEBUG) 
    {
        printf(" --- Post Triangle Depths --- \n");
        printf("\t[");
        for(int i = 0; i < frame_w * frame_h; i++) {
            printf("%+06.2f", zbuff[i]);
            if(((i+1) % frame_w)) {
                printf(", ");
            } else if (i+1 != frame_w*frame_h) {
                printf("]\n\t[");
            } else {
                printf("]\n");
            }
        }
        printf(" --- Post Triangle Tags --- \n");
        printf("\t[");
        for(int i = 0; i < frame_w * frame_h; i++) {
            printf("%d", tbuff[i]+1);
            if(((i+1) % frame_w)) {
                printf("");
            } else if (i+1 != frame_w*frame_h) {
                printf("]\n\t[");
            } else {
                printf("]\n");
            }
        }
        printf(" --- Triangle Printing DONE ---\n");
    }

    // --- Pixel Kernel ---
    ALLOCATE_MEM(pixel_args, pixel_arg_t, 1);

    // Setup Output
        ALLOCATE_MEM(color_output, vector_t, frame_w*frame_h);
        vector_t color_default = {0.6f, 0.6f, 0.6f};
        DEFAULT_ARR(color_output, frame_w*frame_h, color_default);
        pixel_args->color = color_output;

    // Setup Arguments
        pixel_args->verts = pVerts;
        pixel_args->num_verts = num_verts;
        
        pixel_args->tris = tris;
        pixel_args->num_tris = num_tris;

        pixel_args->buff_w = frame_w;
        pixel_args->buff_h = frame_h;
        pixel_args->depth_buff = zbuff;
        pixel_args->tag_buff = tbuff;

        pixel_args->texture = *texture;

    // Running the kernel
    {
        dim_t grid_dim = {1, 1, 1}; dim_t block_dim = {frame_w, frame_h, 1};
        printf("Running kernel_pixel\n");
        run_kernel(kernel_pixel, grid_dim, block_dim, (void*)pixel_args);
    }

    // --- Create Image from Data ---
    
    // Convert vector colors into rgb values
    int* int_color_output = malloc(sizeof(int) * frame_w * frame_h * 3);
    for(int i = 0; i < frame_w*frame_h; i++) {
        int_color_output[i*3 + 0] = color_output[i].x * 255 + .5;
        int_color_output[i*3 + 1] = color_output[i].y * 255 + .5;
        int_color_output[i*3 + 2] = color_output[i].z * 255 + .5;
        // if(tbuff[i] != -1) {
        //     int_color_output[i*3 + 0] = 255;
        //     int_color_output[i*3 + 1] = 255;
        //     int_color_output[i*3 + 2] = 255;
        // } else {
        //     int_color_output[i*3 + 0] = 0;
        //     int_color_output[i*3 + 1] = 0;
        //     int_color_output[i*3 + 2] = 0;
        // }
    }

    createPPMFile("frame0.ppm", int_color_output);
    free(int_color_output);

    // --- Clean Up ---
    free(memory_base);
    
}