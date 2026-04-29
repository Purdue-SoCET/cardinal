
// Standard Includes
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>
#include "include/kernel_run.h"
#include "include/graphics_lib.h"

// Include all needed kernels
#include "../kernels/include/vertex.h"
#include "../kernels/include/triangle.h"
#include "../kernels/include/pixel.h"
#include "../kernels/include/post.h"
#include "../kernels/include/blend.h"

// Globals
uint8_t* memory_ptr;

// Defines
#define OUTPUT_W 800 // 680
#define OUTPUT_H 800 // 480

#define VERTEX_DEBUG 0
#define TRIANGLE_DEBUG 0
#define PIXEL_DEBUG 0

#define X_ANGLE 0
#define Y_ANGLE 0
#define Z_ANGLE 0

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

//Teapot from:
//https://github.com/sexton34/Graphics-Pipeline/tree/master/geometry

// Make video from Frames:
//ffmpeg -framerate 30 -pattern_type glob -i "build/output/*.ppm" -c:v libx264 -pix_fmt yuv420p output.mp4

int main(int argc, char** argv) {
    int frame = 0;
    model_t teapot = {0};
    loadbin("cpu_sim/data/geometry/teapot1K.bin", &teapot);

    if (teapot.vertsN == 0) {
        fprintf(stderr, "Failed to load teapot model!\n");
        return -1;
    }
    for (int frame = 0; frame < 300; frame++)
    {
    uint8_t* memory_base = (uint8_t*) malloc(MEMORY_SIZE - STACK_SIZE - TEXT_SIZE);
    uint8_t* memory_ptr = memory_base;

    // ---- Setup Geometry ----

    const int num_verts = teapot.vertsN;
    const int num_tris = teapot.trisN;

    ALLOCATE_MEM(verts, vertex_t, num_verts);
    ALLOCATE_MEM(tris, triangle_t, num_tris);

    for (int i = 0; i < num_verts; i++) {
        verts[i] = teapot.vertices[i]; 
    }

    for (int i = 0; i < num_tris; i++) {
        tris[i] = teapot.triangles[i]; 
    }

    vector_t center = findCenter(teapot);

    for (int i = 0; i < num_verts; i++) {
        verts[i].coords.x -= center.x;
        verts[i].coords.y -= center.y;
        verts[i].coords.z -= center.z;
    }

        float maxDistSq = 0;
        for (int i = 0; i < num_verts; i++) {
            float dx = verts[i].coords.x - center.x;
            float dy = verts[i].coords.y - center.y;
            float dz = verts[i].coords.z - center.z;
            float distSq = dx*dx + dy*dy + dz*dz;
            if (distSq > maxDistSq) maxDistSq = distSq;
        }
        float radius = sqrtf(maxDistSq);

        float fov_radians = 90.0f * (3.14159 / 180.0f); 
        float distance = radius / sinf(fov_radians / 2.0f);

    // Texture
        const int text_w = 2500, text_h = 2500;

        // Allocation
        ALLOCATE_MEM(texture, texture_t, 1);
        ALLOCATE_MEM(color_map, vec4_t, (text_w * text_h));

        // FIX LOAD PNG TO PUT MEM IN SHARED MEM

        *texture = load_png("cpu_sim/data/textures/red_0.25_alpha.png",0);

    // Camera
        const vector_t abc[3] = {
            {1.0f, 0.0f, 0.0f}, 
            {0.0f, 1.0f, 0.0f},
            {-0.2f, 0.5f, 1.0f},
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
    ALLOCATE_MEM(vertex_args, vertex_arg_t, 1);

    vertex_args->num_verts = num_verts;
    
    // Setup Transformation
        ALLOCATE_MEM(Oa, vector_t, 1);
        vertex_args->Oa = Oa;
        MAKE_VECTOR((*Oa), 0, 0, 0);

        // Pre-compute 3x3 rotation matrix on CPU
        ALLOCATE_MEM(combined_matrix, float, 9);
        vertex_args->combined_matrix = combined_matrix;

        float ax = 3.14f * 2 * X_ANGLE / 300.0f; 
        float ay = 3.14f * 2 * (Y_ANGLE + frame )/ 300.0f;
        float az = 3.14f * 2 * Z_ANGLE / 300.0f;

        build_rotation_matrix_from_euler(ax, ay, az, combined_matrix);

        // Viewport Settings
        vertex_args->viewport_w = (float)OUTPUT_W;
        vertex_args->viewport_h = (float)OUTPUT_H;

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
        int grid_dim = 1; int block_dim = num_verts;
        run_kernel(kernel_vertex, grid_dim, block_dim, (void*)vertex_args);
    }

    // Checking Vertex Output
    if(VERTEX_DEBUG) 
    {
        FILE *f = fopen("build/vertexdebug.txt", "w");
        if (f == NULL) {
            printf("Error opening file!\n");
        }

        fprintf(f, " --- Vertex Debug Dump (Count: %d) --- \n", num_verts);
        
        for(int i = 0; i < num_verts; i++) {
            fprintf(f, " --- Vertex %d --- \n", i);
            
            fprintf(f, "3D (Model):\n");
            fprintf(f, "\tX:%+06.2f Y:%+06.2f Z:%+06.2f | U:%.2f V:%.2f\n", 
                vertex_args->threeDVert[i].coords.x, 
                vertex_args->threeDVert[i].coords.y, 
                vertex_args->threeDVert[i].coords.z, 
                vertex_args->threeDVert[i].s, 
                vertex_args->threeDVert[i].t);

            fprintf(f, "3D (Trans):\n");
            fprintf(f, "\tX:%+06.2f Y:%+06.2f Z:%+06.2f | U:%.2f V:%.2f\n", 
                vertex_args->threeDVertTrans[i].coords.x, 
                vertex_args->threeDVertTrans[i].coords.y, 
                vertex_args->threeDVertTrans[i].coords.z, 
                vertex_args->threeDVertTrans[i].s, 
                vertex_args->threeDVertTrans[i].t);

            fprintf(f, "2D (Screen):\n");
            fprintf(f, "\tX:%+06.2f Y:%+06.2f Z:%+06.2f | U:%.2f V:%.2f\n", 
                vertex_args->twoDVert[i].coords.x, 
                vertex_args->twoDVert[i].coords.y, 
                vertex_args->twoDVert[i].coords.z, 
                vertex_args->twoDVert[i].s, 
                vertex_args->twoDVert[i].t);
            
            fprintf(f, "\n");
        }

        fprintf(f, " --- End of Dump --- \n");
        fclose(f);
        /*
        for(int i = 0; i < num_verts; i++) {
            printf(" --- Vertex %d --- \n", i);
            printf("3D:");
            printf("\t%+06.2f %+06.2f %+06.2f - %.2f %.2f\n", vertex_args->threeDVert[i].coords.x, vertex_args->threeDVert[i].coords.y, vertex_args->threeDVert[i].coords.z, vertex_args->threeDVert[i].s, vertex_args->threeDVert[i].t);
            printf("3Dt:");
            printf("\t%+06.2f %+06.2f %+06.2f - %.2f %.2f\n", vertex_args->threeDVertTrans[i].coords.x, vertex_args->threeDVertTrans[i].coords.y, vertex_args->threeDVertTrans[i].coords.z, vertex_args->threeDVertTrans[i].s, vertex_args->threeDVertTrans[i].t);
            printf("2D:");
            printf("\t%+06.2f %+06.2f %+06.2f - %.2f %.2f\n", vertex_args->twoDVert[i].coords.x, vertex_args->twoDVert[i].coords.y, vertex_args->twoDVert[i].coords.z, vertex_args->twoDVert[i].s, vertex_args->twoDVert[i].t);
        }
        */
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
        //run_kernel(kernel_triangle, grid_dim, block_dim, (void*)triangle_args);
    }

    // Checking TRIANGLE Output
    if(TRIANGLE_DEBUG) 
    {

        FILE *f1 = fopen("build/depth_triangledebug.txt", "w");
        if (f1 == NULL) {
            printf("Error opening file!\n");
        }
        fprintf(f1, " --- Post Triangle Depths --- \n");
        fprintf(f1, "\t[");
        for(int i = 0; i < frame_w * frame_h; i++) {
            fprintf(f1, "%+06.2f", zbuff[i]);
            if(((i+1) % frame_w)) {
                fprintf(f1, ", ");
            } else if (i+1 != frame_w*frame_h) {
                fprintf(f1, "]\n\t[");
            } else {
                fprintf(f1, "]\n");
            }
        }
        fclose(f1);

        FILE *f = fopen("build/tag_triangledebug.txt", "w");
        if (f == NULL) {
            printf("Error opening file!\n");
        }
        fprintf(f, " --- Post Triangle Tags --- \n");
        fprintf(f, "\t[");
        for(int i = 0; i < frame_w * frame_h; i++) {
            if(tbuff[i]+1 > 0)
            fprintf(f, "%d", tbuff[i]+1);
            if(((i+1) % frame_w)) {
                fprintf(f, ", ");
            } else if (i+1 != frame_w*frame_h) {
                fprintf(f, "]\n\t[");
            } else {
                fprintf(f, "]\n");
            }
        }
        fprintf(f, " --- Triangle Printing DONE ---\n");
        fclose(f);
    }

    // --- Pixel Kernel ---
    ALLOCATE_MEM(pixel_args, pixel_arg_t, 1);

    // Setup Output
        ALLOCATE_MEM(color_output, vec4_t, frame_w*frame_h);
        vec4_t color_default = {0.6f, 0.6f, 0.6f, 1.0f};
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

        //pixel_args->uv_buffer = (texel_t*) memory_ptr;
        //memory_ptr += sizeof(texel_t) * frame_w*frame_h;

    // Running the kernel
    {
        int grid_dim = 1; int block_dim = frame_w * frame_h;
        //run_kernel(kernel_pixel, grid_dim, block_dim, (void*)pixel_args);
    }

    if(PIXEL_DEBUG) 
    {
        FILE *f = fopen("build/pixeldebug.txt", "w");
        if (f == NULL) {
            printf("Error opening file!\n");
        }
        fprintf(f, " --- Post Pixel Colors --- \n");
        for(int i = 0; i < frame_w*frame_h; i++) {
            fprintf(f, "Pixel %d: R:%+06.2f G:%+06.2f B:%+06.2f\n", i, color_output[i].x, color_output[i].y, color_output[i].z);
        }
        fprintf(f, " --- Pixel Printing DONE ---\n");
        fclose(f);

        FILE *f1 = fopen("build/pixeldebug_UV.txt", "w");
        if (f1 == NULL) {
            printf("Error opening file!\n");
        }

        fprintf(f1, " --- Post Pixel UVs --- \n");
        //for(int i = 0; i < frame_w*frame_h; i++) {
        //    fprintf(f1, "Pixel %d: S:%+06.2f T:%+06.2f\n", i, pixel_args->uv_buffer[i].s, pixel_args->uv_buffer[i].t);
        //}
        fprintf(f1, " --- Pixel UV Printing DONE ---\n");
        fclose(f1);
    }

    // --- Blend Kernel ---
    ALLOCATE_MEM(blend_args, blend_arg_t, 1);

    blend_args->buff_w = frame_w;
    blend_args->buff_h = frame_h;
    blend_args->depth_buff = zbuff;
    blend_args->tag_buff = tbuff;
    blend_args->color = color_output;
    blend_args->texture = *texture;  

    for(int tri = 0; tri < num_tris; tri++) {
        blend_args->tag = tri;

        // Collect Vertices (Added the missing,, indices!)
        blend_args->pVs[0] = pVerts[tris[tri].v1];
        blend_args->pVs[1] = pVerts[tris[tri].v2];
        blend_args->pVs[2] = pVerts[tris[tri].v3];

        // Find Bounding Box (Added missing indices to pVs!)
        int u_min, u_max;
        u_min = MIN3(blend_args->pVs[0].coords.x, blend_args->pVs[1].coords.x, blend_args->pVs[2].coords.x) - .5;
        u_min = u_min < 0 ? 0 : u_min;
        u_max = MAX3(blend_args->pVs[0].coords.x, blend_args->pVs[1].coords.x, blend_args->pVs[2].coords.x) + .5;
        u_max = u_max > (frame_w-1) ? (frame_w-1) : u_max;
        
        int v_min, v_max;
        v_min = MIN3(blend_args->pVs[0].coords.y, blend_args->pVs[1].coords.y, blend_args->pVs[2].coords.y) - .5;
        v_min = v_min < 0 ? 0 : v_min;
        v_max = MAX3(blend_args->pVs[0].coords.y, blend_args->pVs[1].coords.y, blend_args->pVs[2].coords.y) + .5;
        v_max = v_max > (frame_h-1) ? (frame_h-1) : v_max;

        // Bounding box start (Added missing and indices)
        blend_args->bb_start[0] = u_min;
        blend_args->bb_start[1] = v_min;
        
        // Size of the bounding box (Added missing and indices)
        blend_args->bb_size[0] = u_max - u_min;
        blend_args->bb_size[1] = v_max - v_min;

        // Check to prevent launching a kernel with 0 threads
        if (blend_args->bb_size[0] <= 0 || blend_args->bb_size[1] <= 0) {
            continue;
        }

        // Find Barycentric Matrix 
        float m[3][3] = {
            {1, 1, 1},
            {blend_args->pVs[0].coords.x, blend_args->pVs[1].coords.x, blend_args->pVs[2].coords.x},
            {blend_args->pVs[0].coords.y, blend_args->pVs[1].coords.y, blend_args->pVs[2].coords.y}
        };

        float det = m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) -
                    m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
                    m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);

        if (det > -0.00001f && det < 0.00001f) {
            continue; 
        }
        
        // Invert on the host
        matrix_inversion((float*)m, (float*) blend_args->bc_im);

        int grid_dim = 1; 
        int block_dim = (u_max-u_min)*(v_max-v_min);
        
        run_kernel(kernel_blend, grid_dim, block_dim, (void*)blend_args);
    }

    // --- FXAA Kernel --- (it's called post for now but probably want it to be called fxaa and then every shader after should be called its own thing.)
    ALLOCATE_MEM(post_args, post_arg_t, 1);

    post_args->color = color_output;
    post_args->depth_buff = zbuff;
    post_args->buff_w = frame_w;
    post_args->buff_h = frame_h;
    post_args->threshold = 2;

    // Running the kernel
    {
        int grid_dim = 1; int block_dim = frame_w * frame_h;
        run_kernel(kernel_post, grid_dim, block_dim, (void*)post_args);
    }

    // --- Create Image from Data ---
    
    // Convert vector colors into rgb values
    int* int_color_output = malloc(sizeof(int) * frame_w * frame_h * 3);
    for(int i = 0; i < frame_w*frame_h; i++) {
        int_color_output[i*3 + 0] = color_output[i].x * 255 + .5;
        int_color_output[i*3 + 1] = color_output[i].y * 255 + .5;
        int_color_output[i*3 + 2] = color_output[i].z * 255 + .5;
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

    createPPMFile(fname, int_color_output, frame_w, frame_h);
    free(int_color_output);

    // --- Clean Up ---
    free(memory_base);
    }

    free(teapot.vertices);
    free(teapot.triangles);
    
}