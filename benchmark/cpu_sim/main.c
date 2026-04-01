// Standard Includes
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>
#include <math.h>
#include "include/kernel_run.h"
#include "include/graphics_lib.h"
#include "include/obj_parser.h"
// #include "include/scene_config.h"

// Include all needed kernels
#include "../kernels/include/vertexShader.h"
#include "../kernels/include/triangle.h"
#include "../kernels/include/pixel.h"

// Globals
uint8_t* memory_ptr;

// Defines
#define OUTPUT_W 800
#define OUTPUT_H 800

#define VERTEX_DEBUG 0
#define TRIANGLE_DEBUG 0
#define PIXEL_DEBUG 0

// Macros
#define ALLOCATE_MEM(dest, type, num) \
    type* dest = (type*) memory_ptr; \
    memory_ptr += num * sizeof(type);

#define MAKE_VECTOR(vector, ix, iy, iz) { vector.x = ix; vector.y = iy; vector.z = iz; }
#define MAX2(a, b) (a > b ? a : b)
#define MIN2(a, b) (a < b ? a : b)
#define MAX3(a, b, c) MAX2(a, MAX2(b, c))
#define MIN3(a, b, c) MIN2(a, MIN2(b, c))
#define DEFAULT_ARR(arr, len, def) { for(int DFAx = 0; DFAx < len; DFAx++) { arr[DFAx] = def; } }

int main(int argc, char** argv) {
    int frame = 0;
    
    uint8_t* memory_base = (uint8_t*) malloc(MEMORY_SIZE - STACK_SIZE - TEXT_SIZE);
    // uint8_t* memory_ptr = memory_base;

    // call obj_parser to load teapot geometry
    int num_verts = 0;
    int num_tris = 0;
    vertex_t* vertex_input_buffer = NULL;
    triangle_t* triangle_index_buffer = NULL;
    if (!obj_parser("stanford-bunny.obj", &vertex_input_buffer, &num_verts, &triangle_index_buffer, &num_tris)) {
        printf("Error: Failed to parse obj file\n");
        free(memory_base);
        return 1;
    }

    float model_scale = 300.0f; // bunny = 300.0f, teapot = 1.0f
    float offset_y    = -20.0f; // bunny = -20.0f, teapot = 0.0f

    for (int i = 0; i < num_verts; i++) {
        vertex_input_buffer[i].coords.x *= model_scale;
        vertex_input_buffer[i].coords.y = (vertex_input_buffer[i].coords.y * model_scale) + offset_y;
        vertex_input_buffer[i].coords.z *= model_scale;
    }

    calculate_normals(vertex_input_buffer, num_verts, triangle_index_buffer, num_tris);

    // number of frames to render
    int total_frames = 60;

    // frame loop
    for (frame = 0; frame < total_frames; frame++) {
        printf("Frame %d\n", frame);

        // reset memory pointer for each frame
        memory_ptr = memory_base;

        // Texture
        const int text_w = 10, text_h = 10;
        ALLOCATE_MEM(texture, texture_t, 1);
        ALLOCATE_MEM(texture_buffer, vector_t, (text_w * text_h));
        texture->w = text_w; texture->h = text_h;
        texture->color_arr = texture_buffer;

        const vector_t white = {255.0f, 255.0f, 255.0f};
        const vector_t black = {0.0f, 0.0f, 0.0f};
        for(int u = 0; u < text_w; u++) {
            for(int v = 0; v < text_h; v++) {
                texture->color_arr[GET_1D_INDEX(u, v, text_w)] = (u+v+1) % 2 ? white : black;
            }
        }

        // Camera
        const vector_t abc[3] = { {1.0f, 0.0f, 0.0f}, {0.0f, -1.0f, 0.0f}, {-OUTPUT_W/2, OUTPUT_H/2, -1500.0f} };
        const vector_t abcTranspose[3] = {
            {abc[0].x, abc[1].x, abc[2].x}, {abc[0].y, abc[1].y, abc[2].y}, {abc[0].z, abc[1].z, abc[2].z}
        };
        ALLOCATE_MEM(camera_C, vector_t, 1);
        ALLOCATE_MEM(cameraProjMatrix, float, 9);
        camera_C->x = 0.0f; camera_C->y = 0.0f; camera_C->z = 150.0f;
        matrix_inversion((float*)abcTranspose, cameraProjMatrix);

        // 2. Vertex Kernel (3D -> 2D projection)
        ALLOCATE_MEM(vertex_args, vertexShader_arg_t, 1);
        ALLOCATE_MEM(Oa, vector_t, 1);
        vertex_args->Oa = Oa; MAKE_VECTOR((*Oa), 0, 0, 0);
        ALLOCATE_MEM(a_dist, vector_t, 1);
        vertex_args->a_dist = a_dist; MAKE_VECTOR((*a_dist), 0, 1, 0); 
        ALLOCATE_MEM(alpha_r, float, 1);
        vertex_args->alpha_r = alpha_r; *alpha_r = (3.141592f * 2.0f * (float)frame) / (float)total_frames;

        // CPU precomputation for vertex shader (to be reused across vertices)
        // these values can change per frame but not per vertex, so we compute them once on the CPU and pass them to the vertex shader
        vertex_args->num_verts = num_verts;
        vertex_args->viewport_w = OUTPUT_W;
        vertex_args->viewport_h = OUTPUT_H;

        vector_t light_dir = {0.3f, 0.9f, 0.3f};
        normalize_vector(&light_dir);
        vertex_args->light_dir = light_dir;
        vertex_args->ambient = 0.3f;
        vertex_args->diffuse = 0.8f;

        vector_t axis = *a_dist;
        normalize_vector(&axis);

        vector_t helper_axis = {0.0f, 0.0f, 0.0f};
        float abs_x = axis.x > 0.0f ? axis.x : -axis.x;
        float abs_y = axis.y > 0.0f ? axis.y : -axis.y;
        float abs_z = axis.z > 0.0f ? axis.z : -axis.z;

        if (abs_x <= abs_y && abs_x <= abs_z) {
            helper_axis.x = 1.0f;
        }
        else if (abs_y <= abs_x && abs_y <= abs_z) {
            helper_axis.y = 1.0f;
        }
        else {
            helper_axis.z = 1.0f;
        }

        vector_t u_axis = cross_product(helper_axis, axis);
        normalize_vector(&u_axis);
        vector_t v_axis = cross_product(u_axis, axis);
        normalize_vector(&v_axis);

        // 3x3 local coordinate system matrix (for rotation)
        vertex_args->lcs[0] = u_axis.x;
        vertex_args->lcs[1] = u_axis.y;
        vertex_args->lcs[2] = u_axis.z;
        vertex_args->lcs[3] = axis.x;
        vertex_args->lcs[4] = axis.y;
        vertex_args->lcs[5] = axis.z;
        vertex_args->lcs[6] = v_axis.x;
        vertex_args->lcs[7] = v_axis.y;
        vertex_args->lcs[8] = v_axis.z;

        // inverse of local coordinate system matrix
        vertex_args->lcsInv[0] = vertex_args->lcs[0];
        vertex_args->lcsInv[1] = vertex_args->lcs[3];
        vertex_args->lcsInv[2] = vertex_args->lcs[6];
        vertex_args->lcsInv[3] = vertex_args->lcs[1];
        vertex_args->lcsInv[4] = vertex_args->lcs[4];
        vertex_args->lcsInv[5] = vertex_args->lcs[7];
        vertex_args->lcsInv[6] = vertex_args->lcs[2];
        vertex_args->lcsInv[7] = vertex_args->lcs[5];
        vertex_args->lcsInv[8] = vertex_args->lcs[8];

        // rotation matrix for rotating around the axis by alpha_r
        float c = cosf(*alpha_r);
        float s = sinf(*alpha_r);

        vertex_args->rotMat[0] = c;
        vertex_args->rotMat[1] = 0.0f;
        vertex_args->rotMat[2] = s;
        vertex_args->rotMat[3] = 0.0f;
        vertex_args->rotMat[4] = 1.0f;
        vertex_args->rotMat[5] = 0.0f;
        vertex_args->rotMat[6] = -s;
        vertex_args->rotMat[7] = 0.0f;
        vertex_args->rotMat[8] = c;

        vertex_args->vertex_input_buffer = vertex_input_buffer;
        vertex_args->camera = camera_C;
        vertex_args->invTrans = cameraProjMatrix;
        
        ALLOCATE_MEM(tVerts, vertex_t, num_verts);
        vertex_args->threeDVertTrans = tVerts;
        ALLOCATE_MEM(vertex_output_buffer, vertex_t, num_verts);
        vertex_args->vertex_output_buffer = vertex_output_buffer;
        
        run_kernel(kernel_vertexShader, 1, num_verts, (void*)vertex_args);

        // 3. Primitive Assembly
        // memory allocation for output of primitive assembly (culled triangles)
        ALLOCATE_MEM(surviving_triangle_index_buffer, triangle_t, num_tris);
        
        int final_tri_count = primitive_assembly(vertex_output_buffer, triangle_index_buffer, num_tris, surviving_triangle_index_buffer);
        
        printf("\n[Primitive Assembly Result]\n");
        printf("Original Triangles: %d\n", num_tris);
        printf("Surviving Triangles: %d\n\n", final_tri_count);

        // 4. Triangle Kernel (rasterization)
        ALLOCATE_MEM(triangle_args, triangle_arg_t, 1);
        const int frame_w = OUTPUT_W; const int frame_h = OUTPUT_H;
        ALLOCATE_MEM(depth_buffer, float, frame_w*frame_h); DEFAULT_ARR(depth_buffer, frame_w*frame_h, 0);
        ALLOCATE_MEM(tag_buffer, int, frame_w*frame_h);   DEFAULT_ARR(tag_buffer, frame_w*frame_h, -1);

        triangle_args->buffer_w = frame_w; triangle_args->buffer_h = frame_h;
        triangle_args->depth_buffer = depth_buffer; triangle_args->tag_buffer = tag_buffer;

        printf(" --- Triangle Test --- \n");
        // run the triangle kernel for each surviving triangle
        for(int tri = 0; tri < final_tri_count; tri++) {
            triangle_args->tag = tri;

            // take only the surviving triangles from primitive assembly
            triangle_args->triangle_verts[0] = vertex_output_buffer[surviving_triangle_index_buffer[tri].v1].coords;
            triangle_args->triangle_verts[1] = vertex_output_buffer[surviving_triangle_index_buffer[tri].v2].coords;
            triangle_args->triangle_verts[2] = vertex_output_buffer[surviving_triangle_index_buffer[tri].v3].coords;
            
            // Bounding Box
            int u_min, u_max, v_min, v_max;
            u_min = MIN3(triangle_args->triangle_verts[0].x, triangle_args->triangle_verts[1].x, triangle_args->triangle_verts[2].x) - .5; u_min = u_min < 0 ? 0 : u_min;
            u_max = MAX3(triangle_args->triangle_verts[0].x, triangle_args->triangle_verts[1].x, triangle_args->triangle_verts[2].x) + .5; u_max = u_max > (frame_w-1) ? (frame_w-1) : u_max;
            v_min = MIN3(triangle_args->triangle_verts[0].y, triangle_args->triangle_verts[1].y, triangle_args->triangle_verts[2].y) - .5; v_min = v_min < 0 ? 0 : v_min;
            v_max = MAX3(triangle_args->triangle_verts[0].y, triangle_args->triangle_verts[1].y, triangle_args->triangle_verts[2].y) + .5; v_max = v_max > (frame_h-1) ? (frame_h-1) : v_max;

            triangle_args->bb_start[0] = u_min; triangle_args->bb_start[1] = v_min;
            triangle_args->bb_size[0] = u_max-u_min; triangle_args->bb_size[1] = v_max-v_min;

            // Barycentric Matrix
            float m[3][3] = {
                {1, 1, 1},
                {triangle_args->triangle_verts[0].x, triangle_args->triangle_verts[1].x, triangle_args->triangle_verts[2].x},
                {triangle_args->triangle_verts[0].y, triangle_args->triangle_verts[1].y, triangle_args->triangle_verts[2].y}
            };
            matrix_inversion((float*)m, (float*) triangle_args->bc_im);

            run_kernel(kernel_triangle, 1, (u_max-u_min)*(v_max-v_min), (void*)triangle_args);
        }
        printf("--- Triangle Test Done ---\n");

        // 5. Pixel Kernel
        ALLOCATE_MEM(pixel_args, pixel_arg_t, 1);
        ALLOCATE_MEM(frame_buffer, vector_t, frame_w*frame_h);
        vector_t color_default = {30.0f, 30.0f, 30.0f};
        DEFAULT_ARR(frame_buffer, frame_w*frame_h, color_default);
        
        pixel_args->frame_buffer = frame_buffer;
        pixel_args->vertex_output_buffer = vertex_output_buffer;
        pixel_args->num_verts = num_verts;
        
        // pass the culled triangles
        pixel_args->surviving_triangle_index_buffer = surviving_triangle_index_buffer; 
        pixel_args->num_tris = final_tri_count;

        pixel_args->buffer_w = frame_w; pixel_args->buffer_h = frame_h;
        pixel_args->depth_buffer = depth_buffer; pixel_args->tag_buffer = tag_buffer;
        pixel_args->texture_buffer = *texture;

        run_kernel(kernel_pixel, 1, frame_w * frame_h, (void*)pixel_args);

        // 6. Output Image
        int* int_color_output = malloc(sizeof(int) * frame_w * frame_h * 3);
        for(int i = 0; i < frame_w*frame_h; i++) {
            int_color_output[i*3 + 0] = frame_buffer[i].x;
            int_color_output[i*3 + 1] = frame_buffer[i].y;
            int_color_output[i*3 + 2] = frame_buffer[i].z;
        }

        char fname[30];
        snprintf(fname, sizeof(fname), "build/output/frame_%03d.ppm", frame);
        createPPMFile(fname, int_color_output);

        free(int_color_output);
    }
    
    free(vertex_input_buffer);
    free(triangle_index_buffer);
    free(memory_base);
}