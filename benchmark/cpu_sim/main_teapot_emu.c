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

// Kernels
#include "../kernels/include/vertex.h"
#include "../kernels/include/triangle.h"
#include "../kernels/include/pixel.h"

// Defines
#define OUTPUT_W 32
#define OUTPUT_H 32
#define ARGS_BASE_ADDR 0x00100000
#define HEAP_BASE_ADDR 0x10000000

// Memory Macros
uint8_t* args_ptr;
uint8_t* heap_ptr;

#define ALLOCATE_ARGS(dest, type, num) \
    type* dest = (type*) args_ptr; \
    args_ptr += (num) * sizeof(type);

#define ALLOCATE_HEAP(dest, type, num) \
    heap_ptr = (uint8_t*)(((uintptr_t)heap_ptr + 63) & ~63); \
    type* dest = (type*) heap_ptr; \
    heap_ptr += (num) * sizeof(type);

#define MIN3(a, b, c) (fminf(a, fminf(b, c)))
#define MAX3(a, b, c) (fmaxf(a, fmaxf(b, c)))

#define DEFAULT_ARR(arr, len, def) { \
    for(int i = 0; i < (len); i++) { arr[i] = def; } \
}

int main(int argc, char** argv) {
    int frame_h = OUTPUT_H;
    int frame_w = OUTPUT_W;

    model_t teapot = {0};
    loadbin("cpu_sim/data/geometry/teapot1K.bin", &teapot);

    // 1. Memory Mapping
    size_t args_size = 15 * 1024 * 1024;
    args_ptr = mmap((void*)ARGS_BASE_ADDR, args_size, PROT_READ | PROT_WRITE,
                    MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);

    size_t heap_size = 512 * 1024 * 1024;
    heap_ptr = mmap((void*)HEAP_BASE_ADDR, heap_size, PROT_READ | PROT_WRITE,
                    MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);

    if (args_ptr == MAP_FAILED || heap_ptr == MAP_FAILED) {
        fprintf(stderr, "mmap failed: %s\n", strerror(errno));
        return -1;
    }

    uint8_t* args_start_ptr = args_ptr;
    uint8_t* heap_start_ptr = heap_ptr;

    // ---- Setup SoA Geometry ----
    const int num_verts = teapot.vertsN;
    const int num_tris  = teapot.trisN;

    ALLOCATE_HEAP(v_x, float, num_verts);
    ALLOCATE_HEAP(v_y, float, num_verts);
    ALLOCATE_HEAP(v_z, float, num_verts);
    ALLOCATE_HEAP(v_s, float, num_verts);
    ALLOCATE_HEAP(v_t, float, num_verts);

    ALLOCATE_HEAP(tri_v1, int, num_tris);
    ALLOCATE_HEAP(tri_v2, int, num_tris);
    ALLOCATE_HEAP(tri_v3, int, num_tris);

    vector_t center = findCenter(teapot);

    for (int i = 0; i < num_verts; i++) {
        v_x[i] = teapot.vertices[i].coords.x - center.x;
        v_y[i] = teapot.vertices[i].coords.y - center.y;
        v_z[i] = teapot.vertices[i].coords.z - center.z;
        v_s[i] = teapot.vertices[i].s;
        v_t[i] = teapot.vertices[i].t;
    }

    for (int i = 0; i < num_tris; i++) {
        tri_v1[i] = teapot.triangles[i].v1;
        tri_v2[i] = teapot.triangles[i].v2;
        tri_v3[i] = teapot.triangles[i].v3;
    }

    // Camera setup
    float maxDistSq = 0;
    for (int i = 0; i < num_verts; i++) {
        float dSq = v_x[i]*v_x[i] + v_y[i]*v_y[i] + v_z[i]*v_z[i];
        if (dSq > maxDistSq) maxDistSq = dSq;
    }

    float radius = sqrtf(maxDistSq);
    float fov_rad = 90.0f * (3.1415f / 180.0f);
    float distance = radius / sinf(fov_rad / 2.0f);

    // Output buffers
    ALLOCATE_HEAP(zbuff, float, OUTPUT_W * OUTPUT_H);
    ALLOCATE_HEAP(tbuff, int, OUTPUT_W * OUTPUT_H);
    ALLOCATE_HEAP(color_r, float, OUTPUT_W * OUTPUT_H);
    ALLOCATE_HEAP(color_g, float, OUTPUT_W * OUTPUT_H);
    ALLOCATE_HEAP(color_b, float, OUTPUT_W * OUTPUT_H);
    ALLOCATE_HEAP(color_a, float, OUTPUT_W * OUTPUT_H);

    // Projection matrix
    ALLOCATE_HEAP(cameraProjMatrix, float, 9);

    float aspect = (float)OUTPUT_W / OUTPUT_H;
    float f = 1.0f / tanf(fov_rad / 2.0f);

    cameraProjMatrix[0] = f / aspect; cameraProjMatrix[1] = 0; cameraProjMatrix[2] = 0;
    cameraProjMatrix[3] = 0;          cameraProjMatrix[4] = f; cameraProjMatrix[5] = 0;
    cameraProjMatrix[6] = 0;          cameraProjMatrix[7] = 0; cameraProjMatrix[8] = 1.0f;

    // Frame loop
    int frame = 0;
    //for (int frame = 0; frame < 300; frame++) 
    {

        DEFAULT_ARR(zbuff, OUTPUT_W * OUTPUT_H, 0.0f);
        DEFAULT_ARR(tbuff, OUTPUT_W * OUTPUT_H, -1);
        DEFAULT_ARR(color_r, OUTPUT_W * OUTPUT_H, 0.6f);
        DEFAULT_ARR(color_g, OUTPUT_W * OUTPUT_H, 0.6f);
        DEFAULT_ARR(color_b, OUTPUT_W * OUTPUT_H, 0.6f);

        // ---- Vertex Kernel ----
        ALLOCATE_ARGS(vertex_args, vertex_arg_t, 1);
        ALLOCATE_HEAP(combined_matrix, float, 9);

        build_rotation_matrix_from_euler(
            0,
            2 * 3.1415f * frame / 300.0f,
            0,
            combined_matrix
        );

        vertex_args->num_verts = num_verts;
        vertex_args->combined_matrix = combined_matrix;

        vertex_args->v_x = v_x;
        vertex_args->v_y = v_y;
        vertex_args->v_z = v_z;
        vertex_args->v_s = v_s;
        vertex_args->v_t = v_t;

        vertex_args->ox = 0;
        vertex_args->oy = 0;
        vertex_args->oz = 0;

        vertex_args->cx = 0;
        vertex_args->cy = 0;
        vertex_args->cz = -distance * 1.5f;

        vertex_args->invTrans = cameraProjMatrix;
        vertex_args->viewport_w = OUTPUT_W;
        vertex_args->viewport_h = OUTPUT_H;

        ALLOCATE_HEAP(tx, float, num_verts);
        ALLOCATE_HEAP(ty, float, num_verts);
        ALLOCATE_HEAP(tz, float, num_verts);
        ALLOCATE_HEAP(px, float, num_verts);
        ALLOCATE_HEAP(py, float, num_verts);
        ALLOCATE_HEAP(pz, float, num_verts);

        vertex_args->tx = tx;
        vertex_args->ty = ty;
        vertex_args->tz = tz;
        vertex_args->px = px;
        vertex_args->py = py;
        vertex_args->pz = pz;

            size_t current_args_bytes = (uintptr_t)args_ptr - (uintptr_t)args_start_ptr;
            size_t current_heap_bytes = (uintptr_t)heap_ptr - (uintptr_t)heap_start_ptr;
            dump_memory("build/mem_dump/vertexInput_args_dump.txt", args_start_ptr, ARGS_BASE_ADDR, current_args_bytes);
            dump_memory("build/mem_dump/vertexInput_heap_dump.txt", heap_start_ptr, HEAP_BASE_ADDR, current_heap_bytes);


        int grid_dim = 1; int block_dim = num_verts;
        run_kernel(kernel_vertex, grid_dim, block_dim, (void*)vertex_args);
        FILE* file_thread = fopen("build/threads/vertexThreads.txt", "w");
        fprintf(file_thread, "Grid Dim: %d, Block Dim: %d\n", grid_dim, block_dim);
        fclose(file_thread);

         current_args_bytes = (uintptr_t)args_ptr - (uintptr_t)args_start_ptr;
         current_heap_bytes = (uintptr_t)heap_ptr - (uintptr_t)heap_start_ptr;
        dump_memory("build/mem_dump/vertexOutput_args_dump.txt", args_start_ptr, ARGS_BASE_ADDR, current_args_bytes);
        dump_memory("build/mem_dump/vertexOutput_heap_dump.txt", heap_start_ptr, HEAP_BASE_ADDR, current_heap_bytes);



        // ---- Triangle Kernel ----
        ALLOCATE_ARGS(triangle_args, triangle_arg_t, 1);

        triangle_args->buff_w = OUTPUT_W;
        triangle_args->buff_h = OUTPUT_H;
        triangle_args->depth_buff = zbuff;
        triangle_args->tag_buff = tbuff;
        file_thread = fopen("build/threads/triangleThreads.txt", "w");

        for (int tri = 0; tri < num_tris; tri++) {

            triangle_args->tag = tri;

            int v1 = tri_v1[tri];
            int v2 = tri_v2[tri];
            int v3 = tri_v3[tri];

            triangle_args->v0z = pz[v1];
            triangle_args->v1z = pz[v2];
            triangle_args->v2z = pz[v3];

            int u_min = (int)floorf(MIN3(px[v1], px[v2], px[v3]));
            int u_max = (int)ceilf (MAX3(px[v1], px[v2], px[v3]));
            int v_min = (int)floorf(MIN3(py[v1], py[v2], py[v3]));
            int v_max = (int)ceilf (MAX3(py[v1], py[v2], py[v3]));

            u_min = (u_min < 0) ? 0 : u_min;
            v_min = (v_min < 0) ? 0 : v_min;
            u_max = (u_max > frame_w - 1) ? frame_w - 1 : u_max;
            v_max = (v_max > frame_h - 1) ? frame_h - 1 : v_max;

            triangle_args->bb_start_x = u_min;
            triangle_args->bb_start_y = v_min;
            triangle_args->bb_size_x  = (u_max > u_min) ? (u_max - u_min) : 0;
            triangle_args->bb_size_y  = (v_max > v_min) ? (v_max - v_min) : 0;

            float m[3][3] = {
                {1.0f, 1.0f, 1.0f},
                {px[v1], px[v2], px[v3]},
                {py[v1], py[v2], py[v3]}
            };

            float m_inv[3][3];
            matrix_inversion((float*)m, (float*)m_inv);

            triangle_args->bc_00 = m_inv[0][0]; triangle_args->bc_01 = m_inv[0][1]; triangle_args->bc_02 = m_inv[0][2];
            triangle_args->bc_10 = m_inv[1][0]; triangle_args->bc_11 = m_inv[1][1]; triangle_args->bc_12 = m_inv[1][2];
            triangle_args->bc_20 = m_inv[2][0]; triangle_args->bc_21 = m_inv[2][1]; triangle_args->bc_22 = m_inv[2][2];


             current_args_bytes = (uintptr_t)args_ptr - (uintptr_t)args_start_ptr;
             current_heap_bytes = (uintptr_t)heap_ptr - (uintptr_t)heap_start_ptr;
            char filename_args[100];
            char filename_heap[100];
            sprintf(filename_args, "build/mem_dump/triangleInput%d_args_dump.txt", tri); 
            sprintf(filename_heap, "build/mem_dump/triangleInput%d_heap_dump.txt", tri); 
            //print_triangle_args(filename, triangle_args);
            dump_memory(filename_args, args_start_ptr, ARGS_BASE_ADDR, current_args_bytes);
            dump_memory(filename_heap, heap_start_ptr, HEAP_BASE_ADDR, current_heap_bytes);
           
           
            size_t threads = (size_t)triangle_args->bb_size_x *
                             (size_t)triangle_args->bb_size_y;

            int total_threads = (u_max - u_min) * (v_max - v_min);
            block_dim = total_threads > 1024 ? 1024 : total_threads;
            grid_dim = (total_threads + block_dim - 1) / block_dim;
            run_kernel(kernel_triangle, grid_dim, block_dim, (void*)triangle_args);
            fprintf(file_thread, "Grid Dim: %d, Block Dim: %d\n", grid_dim, block_dim);

             current_args_bytes = (uintptr_t)args_ptr - (uintptr_t)args_start_ptr;
             current_heap_bytes = (uintptr_t)heap_ptr - (uintptr_t)heap_start_ptr;
             filename_args[50];
             filename_heap[50];
            sprintf(filename_args, "build/mem_dump/triangleOutput%d_args_dump.txt", tri); 
            sprintf(filename_heap, "build/mem_dump/triangleOutput%d_heap_dump.txt", tri); 
            //print_triangle_args(filename, triangle_args);
            dump_memory(filename_args, args_start_ptr, ARGS_BASE_ADDR, current_args_bytes);
            dump_memory(filename_heap, heap_start_ptr, HEAP_BASE_ADDR, current_heap_bytes);
        }

        // ---- Pixel Kernel ----
        ALLOCATE_ARGS(pixel_args, pixel_arg_t, 1);

        pixel_args->color_r = color_r;
        pixel_args->color_g = color_g;
        pixel_args->color_b = color_b;
        pixel_args->color_a = color_a;

        pixel_args->v_x = px;
        pixel_args->v_y = py;
        pixel_args->v_z = pz;

        pixel_args->v_s = v_s;
        pixel_args->v_t = v_t;

        pixel_args->tri_v1 = tri_v1;
        pixel_args->tri_v2 = tri_v2;
        pixel_args->tri_v3 = tri_v3;

        pixel_args->num_tris = num_tris;
        pixel_args->buff_w = OUTPUT_W;
        pixel_args->buff_h = OUTPUT_H;
        pixel_args->depth_buff = zbuff;
        pixel_args->tag_buff = tbuff;

        ALLOCATE_HEAP(texture, texture_t, 1);

        *texture = load_png("cpu_sim/data/textures/red_0.25_alpha.png",0);

        pixel_args->texture = *texture;

         current_args_bytes = (uintptr_t)args_ptr - (uintptr_t)args_start_ptr;
         current_heap_bytes = (uintptr_t)heap_ptr - (uintptr_t)heap_start_ptr;
        dump_memory("build/mem_dump/pixelInput_args_dump.txt", args_start_ptr, ARGS_BASE_ADDR, current_args_bytes);
        dump_memory("build/mem_dump/pixelInput_heap_dump.txt", heap_start_ptr, HEAP_BASE_ADDR, current_heap_bytes);

        float total_threads = frame_w * frame_h;
        grid_dim = (int)ceil(total_threads / 1024.0); 
        block_dim = total_threads > 1024 ? 1024 : (int)total_threads;
        run_kernel(kernel_pixel, grid_dim, block_dim, (void*)pixel_args);
        file_thread = fopen("build/threads/pixelThreads.txt", "w");
        fprintf(file_thread, "Grid Dim: %d, Block Dim: %d\n", grid_dim, block_dim);
        fclose(file_thread);

         current_args_bytes = (uintptr_t)args_ptr - (uintptr_t)args_start_ptr;
         current_heap_bytes = (uintptr_t)heap_ptr - (uintptr_t)heap_start_ptr;
        dump_memory("build/mem_dump/pixelOutput_args_dump.txt", args_start_ptr, ARGS_BASE_ADDR, current_args_bytes);
        dump_memory("build/mem_dump/pixelOutput_heap_dump.txt", heap_start_ptr, HEAP_BASE_ADDR, current_heap_bytes);

        // ---- Output ----
        int* img = malloc(sizeof(int) * OUTPUT_W * OUTPUT_H * 3);

        for (int i = 0; i < OUTPUT_W * OUTPUT_H; i++) {
            img[i*3+0] = (int)(color_r[i] * 255.0f + 0.5f);
            img[i*3+1] = (int)(color_g[i] * 255.0f + 0.5f);
            img[i*3+2] = (int)(color_b[i] * 255.0f + 0.5f);
        }

        char name[64];
        snprintf(name, sizeof(name),
                 "build/output/frame_%03d.ppm", frame);

        createPPMFile(name, img, OUTPUT_W, OUTPUT_H);
        free(img);

        // Reset per-frame allocator state
        args_ptr = args_start_ptr;
        heap_ptr = heap_start_ptr;
    }

    munmap(args_start_ptr, args_size);
    munmap(heap_start_ptr, heap_size);

    return 0;
}