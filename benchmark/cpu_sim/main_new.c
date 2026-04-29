
// Standard Includes
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <errno.h>
#include <string.h>
#include <math.h>
#include "include/kernel_run.h"
#include "include/graphics_lib.h"
#include "include/shader_memdump.h"

// Include all needed kernels
#include "../kernels/include/vertex.h"
#include "../kernels/include/triangle.h"
#include "../kernels/include/pixel.h"

// Globals
uint8_t* memory_ptr;

// Defines
#define OUTPUT_W 32
#define OUTPUT_H 32

#define VERTEX_DEBUG 0
#define TRIANGLE_DEBUG 0
#define PIXEL_DEBUG 0

#define INPUT_ARGS_DEBUG 1
#define OUTPUT_ARGS_DEBUG 1

#define ARGS_BASE_ADDR 0x00100000
#define HEAP_BASE_ADDR 0x10000000

// Macros
uint8_t* memory_base;
uint8_t* memory_ptr;
#define ALLOCATE_MEM(dest, type, num) \
    type* dest = (type*) memory_ptr; \
    memory_ptr += num * sizeof(type);

#define ALLOCATE_ARGS(dest, type, num) \
    type* dest = (type*) args_ptr; \
    args_ptr += (num) * sizeof(type);
/*
#define ALLOCATE_HEAP(dest, type, num) \
    type* dest = (type*) heap_ptr; \
    heap_ptr += (num) * sizeof(type);
*/
// make heap addresses cache block aligned 
#define ALLOCATE_HEAP(dest, type, num) \
    heap_ptr = (uint8_t*)(((uintptr_t)heap_ptr + 63) & ~63); \
    type* dest = (type*) heap_ptr; \
    heap_ptr += (num) * sizeof(type);

#define MAKE_VECTOR(vector, ix, iy, iz) { \
    vector.x = ix; \
    vector.y = iy; \
    vector.z = iz; \
}

#define MAKE_VERTEX(vertex, ix, iy, iz, is, it) { \
    MAKE_VECTOR(vertex.coords, ix, iy, iz); \
    vertex.s = is; vertex.t = it; \
}

#define MAKE_VERTEX_C(i, ix, iy, iz, is, it) { \
    v_x[i] = ix; \
    v_y[i] = iy; \
    v_z[i] = iz; \
    v_s[i] = is; \
    v_t[i] = it; \
}

#define MAKE_TRI(tri, iv1, iv2, iv3) { \
    tri.v1 = iv1; \
    tri.v2 = iv2; \
    tri.v3 = iv3; \
}

#define MAKE_TRI_C(i, iv1, iv2, iv3) { \
    tri_v1[i] = iv1; \
    tri_v2[i] = iv2; \
    tri_v3[i] = iv3; \
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
    int frame = 0;
    // for (int frame = 0; frame < 300; frame++)
    {
    memory_base = (uint8_t*) malloc(MEMORY_SIZE - STACK_SIZE - TEXT_SIZE);
    memory_ptr = memory_base;

    uint8_t* args_ptr;
    uint8_t* heap_ptr;
    /*

    args_ptr = memory_base + ARGS_BASE_ADDR;
    heap_ptr = memory_base + HEAP_BASE_ADDR;
    */

    // 1. Map the Arguments Space (Starts at 0x00100000, size ~15MB)
    size_t args_size = 15 * 1024 * 1024;
    args_ptr = mmap((void*)0x00100000, args_size, 
                             PROT_READ | PROT_WRITE, 
                             MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, 
                             -1, 0);

    // 2. Map the Heap Space (Starts at 0x10000000, size ~256MB)
    size_t heap_size = 256 * 1024 * 1024;
    heap_ptr = mmap((void*)0x10000000, heap_size, 
                             PROT_READ | PROT_WRITE, 
                             MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, 
                             -1, 0);

    if (args_ptr == MAP_FAILED || heap_ptr == MAP_FAILED) {
        fprintf(stderr, "mmap failed! OS refused to give us those exact addresses. Error: %s\n", strerror(errno));
        return -1;
    }

    printf("Successfully forced Arguments to %p and Heap to %p\n", args_ptr, heap_ptr);

    uint8_t* args_start_ptr = args_ptr;
    uint8_t* heap_start_ptr = heap_ptr;

    // ---- Setup Geometry ----
    // Single Triangle, all in a single plane

    // Vertexs
        const int num_verts = 8;

        // Allocation
        //ALLOCATE_HEAP(verts, vertex_t, num_verts);
        ALLOCATE_HEAP(v_x, float, num_verts);
        ALLOCATE_HEAP(v_y, float, num_verts);
        ALLOCATE_HEAP(v_z, float, num_verts);
        ALLOCATE_HEAP(v_s, float, num_verts);
        ALLOCATE_HEAP(v_t, float, num_verts);

        // Definition
        // Front Face
        /*
        MAKE_VERTEX(verts[0], -10, -10, -20, 0, 0); // BL
        MAKE_VERTEX(verts[1], -10,  10, -20, 0, 1); // TL
        MAKE_VERTEX(verts[2],  10, -10, -20, 1, 0); // BR
        MAKE_VERTEX(verts[3],  10,  10, -20, 1, 1); // TR

        // Back Face
        MAKE_VERTEX(verts[4], -10, -10, -40, 0, 1); // BL
        MAKE_VERTEX(verts[5], -10,  10, -40, 1, 1); // TL
        MAKE_VERTEX(verts[6],  10, -10, -40, 0, 0); // BR
        MAKE_VERTEX(verts[7],  10,  10, -40, 1, 0); // TR
        */
        MAKE_VERTEX_C(0, -10, -10, -20, 0, 0); // BL
        MAKE_VERTEX_C(1, -10,  10, -20, 0, 1); // TL
        MAKE_VERTEX_C(2,  10, -10, -20, 1, 0); // BR
        MAKE_VERTEX_C(3,  10,  10, -20, 1, 1); // TR

        // Back Face
        MAKE_VERTEX_C(4, -10, -10, -40, 0, 1); // BL
        MAKE_VERTEX_C(5, -10,  10, -40, 1, 1); // TL
        MAKE_VERTEX_C(6,  10, -10, -40, 0, 0); // BR
        MAKE_VERTEX_C(7,  10,  10, -40, 1, 0); // TR
       

    // Triangles
        const int num_tris = 12;

        // Allocation
        //ALLOCATE_HEAP(tris, triangle_t, num_tris);
        ALLOCATE_HEAP(tri_v1, int, num_tris);
        ALLOCATE_HEAP(tri_v2, int, num_tris);
        ALLOCATE_HEAP(tri_v3, int, num_tris);

        // Definition
        // Front of Cube
        /*
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
        */

        MAKE_TRI_C(0, 0, 1, 2);
        MAKE_TRI_C(1, 3, 1, 2);
        
        // Back of Cube
        MAKE_TRI_C(6, 4, 5, 6);
        MAKE_TRI_C(7, 7, 5, 6);

        // Top of Cube
        MAKE_TRI_C(2, 1, 3, 5);
        MAKE_TRI_C(3, 7, 3, 5);

        // Bottom of Cube
        MAKE_TRI_C(4, 0, 2, 4);
        MAKE_TRI_C(5, 6, 2, 4);

        // Left of Cube
        MAKE_TRI_C(8, 0, 1, 4);
        MAKE_TRI_C(9, 5, 1, 4);

        // Right of Cube
        MAKE_TRI_C(10, 2, 3, 6);
        MAKE_TRI_C(11, 7, 3, 6);

    vector_t center = {0.0f, 0.0f, 0.0f};

    float maxDistSq = 0;
    for (int i = 0; i < num_verts; i++) {
        float dx = v_x[i] - center.x;
        float dy = v_y[i] - center.y;
        float dz = v_z[i] - center.z;
        float distSq = dx*dx + dy*dy + dz*dz;
        if (distSq > maxDistSq) maxDistSq = distSq;
    }
    float radius = sqrtf(maxDistSq);

    float fov_radians = 90.0f * (3.14159 / 180.0f); 
    float distance = radius / sinf(fov_radians / 2.0f);

    // Texture
        const int text_w = 10, text_h = 10;

        // Allocation
        ALLOCATE_HEAP(texture, texture_t, 1);
        ALLOCATE_HEAP(color_map, vec4_t, (text_w * text_h));

        // Definition
        texture->w = text_w; texture->h = text_h;
        texture->color_arr = color_map;
        for(int u = 0; u < text_w; u++) {
            for(int v = 0; v < text_h; v++) {
                // Make red/blue checkerboard texture
                const vec4_t red = {1.0f, 1.0f, 1.0f, 1.0f}; const vec4_t blue = {0.0f, 0.0f, 0.0f, 1.0f};
                texture->color_arr[GET_1D_INDEX(u, v, text_w)] = (u+v+1) % 2 ? red : blue;
            }
        }

    // Camera
        const vector_t abc[3] = {
            {1.0f, 0.0f, 0.0f}, 
            {0.0f, 1.0f, 0.0f},
            {0.0f, 0.0f, 1.0f},
        };

        const vector_t abcTranspose[3] = {
            {abc[0].x, abc[1].x, abc[2].x},
            {abc[0].y, abc[1].y, abc[2].y},
            {abc[0].z, abc[1].z, abc[2].z}
        };

        // Allocation
        ALLOCATE_HEAP(camera_C, vector_t, 1);
        ALLOCATE_HEAP(cameraProjMatrix, float, 9);

        // Definition
        float cam_dist = (100*1.5f + 1)/300.0f + .5f;

        camera_C->x = center.x; 
        camera_C->y = center.y; 
        camera_C->z = (center.z - distance)*cam_dist; 

        float aspect_ratio = (float)OUTPUT_W / (float)OUTPUT_H;
        float f = 1.0f / tanf(fov_radians / 2.0f);

        float x_scaled = f / aspect_ratio;
        float y_scaled = f;

        cameraProjMatrix[0] = x_scaled * abcTranspose[0].x; 
        cameraProjMatrix[1] = x_scaled * abcTranspose[0].y;
        cameraProjMatrix[2] = x_scaled * abcTranspose[0].z;

        cameraProjMatrix[3] = y_scaled * abcTranspose[1].x;
        cameraProjMatrix[4] = y_scaled * abcTranspose[1].y;
        cameraProjMatrix[5] = y_scaled * abcTranspose[1].z;

        cameraProjMatrix[6] = abcTranspose[2].x;
        cameraProjMatrix[7] = abcTranspose[2].y;
        cameraProjMatrix[8] = abcTranspose[2].z;
    // --- Vertex Kernel ---
    ALLOCATE_ARGS(vertex_args, vertex_arg_t, 1);

    vertex_args->num_verts = num_verts;
    
    // Setup Transformation
        // Pre-compute 3x3 rotation matrix on CPU
        ALLOCATE_HEAP(combined_matrix, float, 9);
        vertex_args->combined_matrix = combined_matrix;

        float ax = 3.14f * 2 * 0 / 300.0f; 
        float ay = 3.14f * 2 * 0 / 300.0f;
        float az = 3.14f * 2 * 0 / 300.0f;

        build_rotation_matrix_from_euler(ax, ay, az, combined_matrix);

    // Give geometry inputs

        //vertex_args->threeDVert = verts;
        //vertex_args->camera = camera_C;
        vertex_args->invTrans = cameraProjMatrix;

        vertex_args->v_x = v_x; 
        vertex_args->v_y = v_y; 
        vertex_args->v_z = v_z;
        vertex_args->v_s = v_s; 
        vertex_args->v_t = v_t;

        vertex_args->ox = 0.0f; 
        vertex_args->oy = 0.0f; 
        vertex_args->oz = -30.0f;

        vertex_args->cx = camera_C->x; 
        vertex_args->cy = camera_C->y; 
        vertex_args->cz = camera_C->z;

        vertex_args->invTrans = cameraProjMatrix;
        vertex_args->viewport_w = OUTPUT_W;
        vertex_args->viewport_h = OUTPUT_H;

        // Allocate SoA Output Space
        ALLOCATE_HEAP(tx, float, num_verts);
        ALLOCATE_HEAP(ty, float, num_verts);
        ALLOCATE_HEAP(tz, float, num_verts);
        vertex_args->tx = tx; vertex_args->ty = ty; vertex_args->tz = tz;

        ALLOCATE_HEAP(px, float, num_verts);
        ALLOCATE_HEAP(py, float, num_verts);
        ALLOCATE_HEAP(pz, float, num_verts);
        vertex_args->px = px; vertex_args->py = py; vertex_args->pz = pz;
    
        if(INPUT_ARGS_DEBUG){
            //print_vertex_args("build/vertexInput.txt", vertex_args, num_verts);
            size_t current_args_bytes = (uintptr_t)args_ptr - (uintptr_t)args_start_ptr;
            size_t current_heap_bytes = (uintptr_t)heap_ptr - (uintptr_t)heap_start_ptr;
            dump_memory("build/mem_dump/vertexInput_args_dump.txt", args_start_ptr, ARGS_BASE_ADDR, current_args_bytes);
            dump_memory("build/mem_dump/vertexInput_heap_dump.txt", heap_start_ptr, HEAP_BASE_ADDR, current_heap_bytes);
        }

        //printf("args size: %lu\n", sizeof(vertex_arg_t));
    
    // Running the Kernel
    {
        int grid_dim = 1; int block_dim = num_verts;
        run_kernel(kernel_vertex, grid_dim, block_dim, (void*)vertex_args);
        FILE* file_thread = fopen("build/threads/vertexThreads.txt", "w");
        fprintf(file_thread, "Grid Dim: %d, Block Dim: %d\n", grid_dim, block_dim);
        fclose(file_thread);
    }

    if(OUTPUT_ARGS_DEBUG){
        //print_vertex_args("build/vertexOutput.txt", vertex_args, num_verts);
        size_t current_args_bytes = (uintptr_t)args_ptr - (uintptr_t)args_start_ptr;
        size_t current_heap_bytes = (uintptr_t)heap_ptr - (uintptr_t)heap_start_ptr;
        dump_memory("build/mem_dump/vertexOutput_args_dump.txt", args_start_ptr, ARGS_BASE_ADDR, current_args_bytes);
        dump_memory("build/mem_dump/vertexOutput_heap_dump.txt", heap_start_ptr, HEAP_BASE_ADDR, current_heap_bytes);
    }


    // --- Triangle Kernel ---
    // Only one call - still implement multi triangle framework
    ALLOCATE_ARGS(triangle_args, triangle_arg_t, 1);

    // Setup Pixel Buffers
        const int frame_w = OUTPUT_W; const int frame_h = OUTPUT_H;
        ALLOCATE_HEAP(zbuff, float, frame_w*frame_h);
        DEFAULT_ARR(zbuff, frame_w*frame_h, 0);
        ALLOCATE_HEAP(tbuff, int, frame_w*frame_h);
        DEFAULT_ARR(tbuff, frame_w*frame_h, -1);

        triangle_args->buff_w = frame_w;
        triangle_args->buff_h = frame_h;
        triangle_args->depth_buff = zbuff;
        triangle_args->tag_buff = tbuff;

    
    FILE* file_thread = fopen("build/threads/triangleThreads.txt", "w");
    // Setup and launch each triangle kernel
    for(int tri = 0; tri < num_tris; tri++) {
        // Set Tag
        triangle_args->tag = tri;

        int v1 = tri_v1[tri];
        int v2 = tri_v2[tri];
        int v3 = tri_v3[tri];

        triangle_args->v0z = pz[v1];
        triangle_args->v1z = pz[v2];
        triangle_args->v2z = pz[v3];

        // 2. Calculate X-bounds using the projected X-coordinate array (px)
        int u_min = (int)floorf(MIN3(px[v1], px[v2], px[v3]));
        u_min = (u_min < 0) ? 0 : u_min;

        int u_max = (int)ceilf(MAX3(px[v1], px[v2], px[v3]));
        u_max = (u_max > (frame_w - 1)) ? (frame_w - 1) : u_max;

        // 3. Calculate Y-bounds using the projected Y-coordinate array (py)
        int v_min = (int)floorf(MIN3(py[v1], py[v2], py[v3]));
        v_min = (v_min < 0) ? 0 : v_min;

        int v_max = (int)ceilf(MAX3(py[v1], py[v2], py[v3]));
        v_max = (v_max > (frame_h - 1)) ? (frame_h - 1) : v_max;

        // 4. Update the flattened triangle_args
        triangle_args->bb_start_x = u_min;
        triangle_args->bb_start_y = v_min;
        triangle_args->bb_size_x  = (u_max - u_min);
        triangle_args->bb_size_y  = (v_max - v_min);


        float m[3][3] = {
            {1.0f, 1.0f, 1.0f},
            {px[v1], px[v2], px[v3]},
            {py[v1], py[v2], py[v3]}
        };

        // Flatten the 3x3 Barycentric Matrix
        float m_inv[3][3];
        matrix_inversion((float*)m, (float*)m_inv);
        
        triangle_args->bc_00 = m_inv[0][0]; triangle_args->bc_01 = m_inv[0][1]; triangle_args->bc_02 = m_inv[0][2];
        triangle_args->bc_10 = m_inv[1][0]; triangle_args->bc_11 = m_inv[1][1]; triangle_args->bc_12 = m_inv[1][2];
        triangle_args->bc_20 = m_inv[2][0]; triangle_args->bc_21 = m_inv[2][1]; triangle_args->bc_22 = m_inv[2][2];


        if(INPUT_ARGS_DEBUG){
            size_t current_args_bytes = (uintptr_t)args_ptr - (uintptr_t)args_start_ptr;
            size_t current_heap_bytes = (uintptr_t)heap_ptr - (uintptr_t)heap_start_ptr;
            char filename_args[50];
            char filename_heap[50];
            sprintf(filename_args, "build/mem_dump/triangleInput%d_args_dump.txt", tri); 
            sprintf(filename_heap, "build/mem_dump/triangleInput%d_heap_dump.txt", tri); 
            //print_triangle_args(filename, triangle_args);
            dump_memory(filename_args, args_start_ptr, ARGS_BASE_ADDR, current_args_bytes);
            dump_memory(filename_heap, heap_start_ptr, HEAP_BASE_ADDR, current_heap_bytes);
        }

        // Running the Kernel
        int total_threads = (u_max - u_min) * (v_max - v_min);
        int block_dim = total_threads > 1024 ? 1024 : total_threads;
        int grid_dim = (total_threads + block_dim - 1) / block_dim;
        run_kernel(kernel_triangle, grid_dim, block_dim, (void*)triangle_args);
        fprintf(file_thread, "Grid Dim: %d, Block Dim: %d\n", grid_dim, block_dim);

        if(OUTPUT_ARGS_DEBUG){
            printf("Tri %d, Blocks: %d, Threads: %d\n", tri, grid_dim, block_dim);
            size_t current_args_bytes = (uintptr_t)args_ptr - (uintptr_t)args_start_ptr;
            size_t current_heap_bytes = (uintptr_t)heap_ptr - (uintptr_t)heap_start_ptr;
            char filename_args[50];
            char filename_heap[50];
            sprintf(filename_args, "build/mem_dump/triangleOutput%d_args_dump.txt", tri); 
            sprintf(filename_heap, "build/mem_dump/triangleOutput%d_heap_dump.txt", tri); 
            //print_triangle_args(filename, triangle_args);
            dump_memory(filename_args, args_start_ptr, ARGS_BASE_ADDR, current_args_bytes);
            dump_memory(filename_heap, heap_start_ptr, HEAP_BASE_ADDR, current_heap_bytes);
        }
    }
    fclose(file_thread);

    // Checking TRIANGLE Output
    if(TRIANGLE_DEBUG) 
    {
        printf(" --- Post Triangle Depths --- \n");
        printf("\t[");
        for(int i = 0; i < frame_w * frame_h; i++) {
            printf("%+06.2f", (double) zbuff[i]);
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
            if(tbuff[i]+1 > 0)
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
    ALLOCATE_ARGS(pixel_args, pixel_arg_t, 1);

    // Setup Output
        ALLOCATE_HEAP(color_output, vec4_t, frame_w*frame_h);
        vec4_t color_default = {0.6f, 0.6f, 0.6f, 1.0f};
        DEFAULT_ARR(color_output, frame_w*frame_h, color_default);
        //pixel_args->color = color_output;
        ALLOCATE_HEAP(color_r, float, frame_w*frame_h);
        ALLOCATE_HEAP(color_g, float, frame_w*frame_h);
        ALLOCATE_HEAP(color_b, float, frame_w*frame_h);
        ALLOCATE_HEAP(color_a, float, frame_w*frame_h);
        DEFAULT_ARR(color_r, frame_w*frame_h, color_default.x);
        DEFAULT_ARR(color_g, frame_w*frame_h, color_default.y);
        DEFAULT_ARR(color_b, frame_w*frame_h, color_default.z);
        DEFAULT_ARR(color_a, frame_w*frame_h, color_default.w);
        pixel_args->color_r = color_r;
        pixel_args->color_g = color_g;
        pixel_args->color_b = color_b;
        pixel_args->color_a = color_a;


        // Input Vertex SoA (Screen Space)
        pixel_args->v_x = px; 
        pixel_args->v_y = py; 
        pixel_args->v_z = pz;
        pixel_args->v_s = v_s; 
        pixel_args->v_t = v_t;
        pixel_args->num_verts = num_verts;

        // Input Triangle SoA
        pixel_args->tri_v1 = tri_v1;
        pixel_args->tri_v2 = tri_v2;
        pixel_args->tri_v3 = tri_v3;
        pixel_args->num_tris = num_tris;

        // World Space SoA (for Lighting)
        pixel_args->trans_x = 0;//tx; 
        pixel_args->trans_y = ty; 
        pixel_args->trans_z = tz;

        // Uniforms
        pixel_args->buff_w = frame_w;
        pixel_args->buff_h = frame_h;
        pixel_args->depth_buff = zbuff;
        pixel_args->tag_buff = tbuff;
        pixel_args->texture = *texture;

    if(INPUT_ARGS_DEBUG){
        //print_pixel_args("build/pixelInput.txt", pixel_args); 
        size_t current_args_bytes = (uintptr_t)args_ptr - (uintptr_t)args_start_ptr;
        size_t current_heap_bytes = (uintptr_t)heap_ptr - (uintptr_t)heap_start_ptr;
        dump_memory("build/mem_dump/pixelInput_args_dump.txt", args_start_ptr, ARGS_BASE_ADDR, current_args_bytes);
        dump_memory("build/mem_dump/pixelInput_heap_dump.txt", heap_start_ptr, HEAP_BASE_ADDR, current_heap_bytes);
    }
    // Running the kernel
    {
        float total_threads = frame_w * frame_h;
        int grid_dim = (int)ceil(total_threads / 1024.0); 
        int block_dim = total_threads > 1024 ? 1024 : (int)total_threads;
        printf("Pixel Kernel: Blocks: %d, Threads: %d\n", grid_dim, block_dim);
        run_kernel(kernel_pixel, grid_dim, block_dim, (void*)pixel_args);
        FILE* file_thread = fopen("build/threads/pixelThreads.txt", "w");
        fprintf(file_thread, "Grid Dim: %d, Block Dim: %d\n", grid_dim, block_dim);
        fclose(file_thread);

    }

    if(OUTPUT_ARGS_DEBUG){
        //print_pixel_args("build/pixelOutput.txt", pixel_args); 
        size_t current_args_bytes = (uintptr_t)args_ptr - (uintptr_t)args_start_ptr;
        size_t current_heap_bytes = (uintptr_t)heap_ptr - (uintptr_t)heap_start_ptr;
        dump_memory("build/mem_dump/pixelOutput_args_dump.txt", args_start_ptr, ARGS_BASE_ADDR, current_args_bytes);
        dump_memory("build/mem_dump/pixelOutput_heap_dump.txt", heap_start_ptr, HEAP_BASE_ADDR, current_heap_bytes);
    }

    // --- Create Image from Data ---
    
    // Convert vector colors into rgb values
    int* int_color_output = malloc(sizeof(int) * frame_w * frame_h * 3);
    for(int i = 0; i < frame_w*frame_h; i++) {
        int_color_output[i*3 + 0] = pixel_args->color_r[i] * 255 + .5;
        int_color_output[i*3 + 1] = pixel_args->color_g[i] * 255 + .5;
        int_color_output[i*3 + 2] = pixel_args->color_b[i] * 255 + .5;
        // int_color_output[i*3 + 0] = zbuff[i] != 0 ? ((zbuff[i]-5.0) / 8.0f * 255 + .5) : 0;
        // int_color_output[i*3 + 1] = zbuff[i] != 0 ? ((zbuff[i]-5.0) / 8.0f * 255 + .5) : 0;
        // int_color_output[i*3 + 2] = zbuff[i] != 0 ? ((zbuff[i]-5.0) / 8.0f * 255 + .5) : 0;
        // int_color_output[i*3 + 0] = tbuff[i] != -1 ? (((tbuff[i]+1) % 3)+1.0f) / 3.0f * 255 : 0;
        // int_color_output[i*3 + 1] = tbuff[i] != -1 ? (((tbuff[i]+2) % 4)+1.0f) / 4.0f * 255 : 0;
        // int_color_output[i*3 + 2] = tbuff[i] != -1 ? (((tbuff[i]+3) % 5)+1.0f) / 5.0f * 255 : 0;
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

    char fname[30];
    snprintf(fname, sizeof(fname), "build/output/frame_%03d.ppm", frame);

    createPPMFile(fname, int_color_output, OUTPUT_W, OUTPUT_H);
    free(int_color_output);

    // --- Clean Up ---
    free(memory_base);
    }
    
}