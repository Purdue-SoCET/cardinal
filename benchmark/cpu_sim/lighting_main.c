
// Standard Includes
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>
#include "include/kernel_run.h"
#include "include/graphics_lib.h"

// Include all needed kernels
#include "../kernels/include/vertexShader.h"
#include "../kernels/include/triangle.h"
#include "../kernels/include/pixel.h"

// Globals
uint8_t* memory_ptr;

// Defines
#define OUTPUT_W 800
#define OUTPUT_H 800

#define PI_F 3.14159265f

// Sphere resolution (keep NUM_VERTS <= 1024)
#define SPHERE_LAT 16
#define SPHERE_LON 32
#define NUM_VERTS ((SPHERE_LAT + 1) * SPHERE_LON)
#define NUM_TRIS  (SPHERE_LAT * SPHERE_LON * 2)

#define VERTEX_DEBUG 0
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
    // UV sphere phong lighting test

    const int num_verts = NUM_VERTS;
    const int num_tris = NUM_TRIS;
    const float sphere_radius = 10.0f;
    vector_t sphere_center;
    MAKE_VECTOR(sphere_center, 0.0f, 0.0f, -30.0f);

    // Vertexs
        // Allocation
        ALLOCATE_MEM(verts, vertex_t, num_verts);

        // Generate UV sphere
        for(int lat = 0; lat <= SPHERE_LAT; lat++) {
            float theta = PI_F * (float)lat / (float)SPHERE_LAT;
            float st = sinf(theta), ct = cosf(theta);
            for(int lon = 0; lon < SPHERE_LON; lon++) {
                float phi = 2.0f * PI_F * (float)lon / (float)SPHERE_LON;
                int idx = lat * SPHERE_LON + lon;
                verts[idx].coords.x = sphere_center.x + sphere_radius * st * cosf(phi);
                verts[idx].coords.y = sphere_center.y + sphere_radius * ct;
                verts[idx].coords.z = sphere_center.z + sphere_radius * st * sinf(phi);
                verts[idx].s = 0.0f;
                verts[idx].t = 0.0f;
            }
        }

    // Triangles
        // Allocation
        ALLOCATE_MEM(tris, triangle_t, num_tris);

        // Definition
        int tri_count = 0;
        for(int lat = 0; lat < SPHERE_LAT; lat++) {
            for(int lon = 0; lon < SPHERE_LON; lon++) {
                int ln = (lon + 1) % SPHERE_LON;
                int v00 = lat * SPHERE_LON + lon;
                int v01 = lat * SPHERE_LON + ln;
                int v10 = (lat + 1) * SPHERE_LON + lon;
                int v11 = (lat + 1) * SPHERE_LON + ln;
                MAKE_TRI(tris[tri_count], v00, v10, v01); tri_count++;
                MAKE_TRI(tris[tri_count], v01, v10, v11); tri_count++;
            }
        }

    // Camera
        float focal_range = 1.0f;
        const vector_t abc[3] = {
            {1.0f, 0.0f, 0.0f}, 
            {0.0f, 1.0f * ((float)OUTPUT_H / (float)OUTPUT_W), 0.0f}, 
            {0.0f, 0.0f, -focal_range * ((float)OUTPUT_H / (float)OUTPUT_W)},
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
    
    // Setup Transformation (no rotation for static frame)
        ALLOCATE_MEM(Oa, vector_t, 1);
        vertex_args->Oa = Oa;
        MAKE_VECTOR((*Oa), 0, 0, -30);

        ALLOCATE_MEM(a_dist, vector_t, 1);
        vertex_args->a_dist = a_dist;
        MAKE_VECTOR((*a_dist), 0, 1, 0);

        ALLOCATE_MEM(alpha_r, float, 1);
        vertex_args->alpha_r = alpha_r;
        *alpha_r = 0.0f;

    // Give geometry inputs
        vertex_args->threeDVert = verts;
        vertex_args->num_verts = num_verts;
        vertex_args->camera = camera_C;
        vertex_args->invTrans = cameraProjMatrix;
   
    //viewport 
    ALLOCATE_MEM(viewport_w, float, 1);
    ALLOCATE_MEM(viewport_h, float, 1);
    *viewport_w = OUTPUT_W;
    *viewport_h = OUTPUT_H;
    vertex_args->viewport_w = *viewport_w;
    vertex_args->viewport_h = *viewport_h;

    // Allocate Output Space
        ALLOCATE_MEM(tVerts, vertex_t, num_verts);
        vertex_args->threeDVertTrans = tVerts;
        ALLOCATE_MEM(pVerts, vertex_t, num_verts);
        vertex_args->twoDVert = pVerts;
    
    // Running the Kernel
    {
        int grid_dim = 1; int block_dim = num_verts;
        run_kernel(kernel_vertexShader, grid_dim, block_dim, (void*)vertex_args);
    }

    // Checking Vertex Output
    if(VERTEX_DEBUG) 
    {
        for(int i = 0; i < num_verts; i++) {
            printf(" --- Vertex %d --- \n", i);
            printf("3D:");
            printf("\t%+06.2f %+06.2f %+06.2f\n", vertex_args->threeDVert[i].coords.x, vertex_args->threeDVert[i].coords.y, vertex_args->threeDVert[i].coords.z);
            printf("3Dt:");
            printf("\t%+06.2f %+06.2f %+06.2f\n", vertex_args->threeDVertTrans[i].coords.x, vertex_args->threeDVertTrans[i].coords.y, vertex_args->threeDVertTrans[i].coords.z);
            printf("2D:");
            printf("\t%+06.2f %+06.2f %+06.2f\n", vertex_args->twoDVert[i].coords.x, vertex_args->twoDVert[i].coords.y, vertex_args->twoDVert[i].coords.z);
        }
        printf(" --- Vertex end --- \n");
    }

    // --- Triangle Kernel ---
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
        triangle_args->bb_size[0] = u_max-u_min;
        triangle_args->bb_size[1] = v_max-v_min;

        // Find barycentric Matrix
        float m[3][3] = {
            {1, 1, 1},
            {triangle_args->pVs[0].x, triangle_args->pVs[1].x, triangle_args->pVs[2].x},
            {triangle_args->pVs[0].y, triangle_args->pVs[1].y, triangle_args->pVs[2].y}
        };
        matrix_inversion((float*)m, (float*) triangle_args->bc_im);

        // Running the Kernel
        int grid_dim = 1; int block_dim = (u_max-u_min)*(v_max-v_min);
        if(block_dim <= 0) continue;
        run_kernel(kernel_triangle, grid_dim, block_dim, (void*)triangle_args);
    }

    // --- Pixel Kernel ---
    ALLOCATE_MEM(pixel_args, pixel_arg_t, 1);

    // Setup Output
        ALLOCATE_MEM(color_output, vector_t, frame_w*frame_h);
        vector_t color_default = {0.18f, 0.25f, 0.35f};
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

    // no texture
        pixel_args->texture.w = 0;
        pixel_args->texture.h = 0;
        pixel_args->texture.color_arr = 0;
    // phong lighting vars
        pixel_args->threeDVertTrans = tVerts;
        pixel_args->camera = *camera_C;
        pixel_args->sphere_center = sphere_center;

        // light source
        pixel_args->light_pos = (vector_t){15.0f, 15.0f, 0.0f};

        // material defs
        pixel_args->albedo  = (vector_t){1.0f, 0.1f, 0.1f};
        pixel_args->ambient = (vector_t){0.05f, 0.05f, 0.05f};
        pixel_args->kd = 0.7f;
        pixel_args->ks = 0.3f;

    // Running the kernel
    {
        int grid_dim = 1; int block_dim = frame_w * frame_h;
        run_kernel(kernel_pixel, grid_dim, block_dim, (void*)pixel_args);
    }

    // --- Create Image from Data ---
    
    // Convert vector colors into rgb values
    int* int_color_output = malloc(sizeof(int) * frame_w * frame_h * 3);
    for(int i = 0; i < frame_w*frame_h; i++) {
        int_color_output[i*3 + 0] = color_output[i].x * 255 + .5;
        int_color_output[i*3 + 1] = color_output[i].y * 255 + .5;
        int_color_output[i*3 + 2] = color_output[i].z * 255 + .5;
    }

    createPPMFile("build/output/lighting_frame.ppm", int_color_output, OUTPUT_W, OUTPUT_H);
    free(int_color_output);

    // --- Clean Up ---
    free(memory_base);
    
}
