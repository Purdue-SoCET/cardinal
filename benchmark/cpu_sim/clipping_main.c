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

#define THREADS_PER_BLOCK 1024

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

    // Fallback UV generation for models that do not contain texture coordinates.
    // Stanford bunny loads with u=v=0, so generate planar UVs from object-space x/z.
    float min_x = 1e30f, max_x = -1e30f;
    float min_z = 1e30f, max_z = -1e30f;
    for (int i = 0; i < num_verts; i++) {
        float x = vertex_input_buffer[i].coords.x;
        float z = vertex_input_buffer[i].coords.z;
        if (x < min_x) min_x = x;
        if (x > max_x) max_x = x;
        if (z < min_z) min_z = z;
        if (z > max_z) max_z = z;
    }

    float uv_tile = 4.0f;
    float range_x = max_x - min_x;
    float range_z = max_z - min_z;
    if (range_x == 0.0f) range_x = 1.0f;
    if (range_z == 0.0f) range_z = 1.0f;

    for (int i = 0; i < num_verts; i++) {
        float x = vertex_input_buffer[i].coords.x;
        float z = vertex_input_buffer[i].coords.z;
        vertex_input_buffer[i].u = uv_tile * (x - min_x) / range_x;
        vertex_input_buffer[i].v = uv_tile * (z - min_z) / range_z;
    }

    // Scaling for bunny
    float model_scale = 300.0f; // bunny = 300.0f, teapot = 1.0f
    float offset_y    = -20.0f; // bunny = -20.0f, teapot = 0.0f

    for (int i = 0; i < num_verts; i++) {
        vertex_input_buffer[i].coords.x *= model_scale;
        vertex_input_buffer[i].coords.y = (vertex_input_buffer[i].coords.y * model_scale) + offset_y;
        vertex_input_buffer[i].coords.z *= model_scale;
    }

    calculate_normals(vertex_input_buffer, num_verts, triangle_index_buffer, num_tris);

    texture_t loaded_texture = load_jpg("0qmf_npeu_210906.jpg", 0);
    if (loaded_texture.color_arr == NULL) {
        printf("Error: Failed to load JPG texture\n");
        free(vertex_input_buffer);
        free(triangle_index_buffer);
        free(memory_base);
        return 1;
    }

    // number of frames to render
    int total_frames = 60;

    // frame loop
    for (frame = 0; frame < total_frames; frame++) {
        printf("===== Frame %d =====\n", frame);

        // testing timers for each stage of the pipeline
        clock_t frame_start, frame_end;
        clock_t vertex_start, vertex_end;
        clock_t primitive_start, primitive_end;
        clock_t triangle_start, triangle_end;
        clock_t pixel_start, pixel_end;
        double vertex_ms, primitive_ms, triangle_ms, pixel_ms, total_ms;
        frame_start = clock();

        // reset memory pointer for each frame
        memory_ptr = memory_base;

        // Texture
        // const int text_w = 10, text_h = 10;
        // ALLOCATE_MEM(texture, texture_t, 1);
        // ALLOCATE_MEM(texture_buffer, vector_t, (text_w * text_h));
        // texture->w = text_w; texture->h = text_h;
        // texture->color_arr = texture_buffer;

        // const vector_t white = {1.0f, 1.0f, 1.0f};
        // const vector_t black = {0.0f, 0.0f, 0.0f};
        // for(int u = 0; u < text_w; u++) {
        //     for(int v = 0; v < text_h; v++) {
        //         texture->color_arr[GET_1D_INDEX(u, v, text_w)] = (u+v+1) % 2 ? white : black;
        //     }
        // }
        ALLOCATE_MEM(texture, texture_t, 1);
        *texture = loaded_texture;

        // Camera
        const vector_t abc[3] = { {1.0f, 0.0f, 0.0f}, {0.0f, -1.0f, 0.0f}, {-OUTPUT_W/2, OUTPUT_H/2, -1500.0f} };
        const vector_t abcTranspose[3] = {
            {abc[0].x, abc[1].x, abc[2].x}, {abc[0].y, abc[1].y, abc[2].y}, {abc[0].z, abc[1].z, abc[2].z}
        };
        ALLOCATE_MEM(camera_C, vector_t, 1);
        ALLOCATE_MEM(cameraProjMatrix, float, 9);
        ALLOCATE_MEM(project4x4, float, 16);

        // For this benchmark, move the camera instead of the object.
        // In the current vertex shader path, Oa is not acting like a visible world-space translation,
        // so sweeping camera z is the reliable way to create the near-plane clipping stress case.
        // {
        //     float t = (float)frame / (float)(total_frames - 1);
        //     float camera_z_start =300.0f;
        //     float camera_z_end = -120.0f;
        //     float camera_z = camera_z_start + t * (camera_z_end - camera_z_start);
        //     camera_C->x = 0.0f;
        //     camera_C->y = 0.0f;
        //     camera_C->z = camera_z;
        //     printf("Camera Z: %.2f\n", camera_z);
        // }
        {
            float t = (float)frame / (float)(total_frames - 1);
            float camera_x_start =110.0f;
            float camera_x_end = -110.0f;
            float camera_x = camera_x_start + t * (camera_x_end - camera_x_start);
            camera_C->x = camera_x;
            camera_C->y = 0.0f;
            camera_C->z = 100.0f;
            printf("Camera X: %.2f\n", camera_x);
        }
        matrix_inversion((float*)abcTranspose, cameraProjMatrix);

        // Projection parameter & matrix for 4D clip-space projection
        // Perspective projection parameters:
        // - fov: vertical field of view in degrees/radians
        // - aspect_ratio: output width / output height
        // - near_clip, far_clip: clipping distances from the camera
        // - proj_scale: 1 / tan(fov / 2), used to scale x/y in projection
        float vertical_fov_deg = 60.0f;
        float vertical_fov_rad = vertical_fov_deg * 3.141592f / 180.0f;
        float aspect_ratio = (float)OUTPUT_W / (float)OUTPUT_H;
        float near_clip = 30.0f;
        float far_clip = 500.0f;
        float focal_scale = 1.0f / tanf(vertical_fov_rad * 0.5f);

        for (int i = 0; i < 16; i++) project4x4[i] = 0.0f;
        // Column-major perspective projection matrix matching mat4_mul_vec4()
        project4x4[0]  = focal_scale / aspect_ratio;
        project4x4[5]  = focal_scale;
        project4x4[10] = (far_clip + near_clip) / (near_clip - far_clip);
        project4x4[11] = -1.0f;
        project4x4[14] = (2.0f * far_clip * near_clip) / (near_clip - far_clip);
        project4x4[15] = 0.0f;

        // Vertex Kernel (3D -> 2D projection)
        ALLOCATE_MEM(vertex_args, vertexShader_arg_t, 1);
        ALLOCATE_MEM(Oa, vector_t, 1);
        ALLOCATE_MEM(a_dist, vector_t, 1);
        ALLOCATE_MEM(alpha_r, float, 1);

        vertex_args->Oa = Oa;
        vertex_args->a_dist = a_dist;
        vertex_args->alpha_r = alpha_r;

        // Keep the bunny fixed in world space.
        // Oa is left at the origin because, in the current shader implementation,
        // changing Oa does not produce the visible object translation we want here.
        MAKE_VECTOR((*Oa), 0.0f, 0.0f, 0.0f);
        MAKE_VECTOR((*a_dist), 0.0f, 1.0f, 0.0f);
        *alpha_r = 0.0f;

        /*** CPU precomputation for vertex shader (to be reused across vertices) ***/
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

        vertex_args->rotMat[0] = 1.0f;
        vertex_args->rotMat[1] = 0.0f;
        vertex_args->rotMat[2] = 0.0f;
        vertex_args->rotMat[3] = 0.0f;
        vertex_args->rotMat[4] = 1.0f;
        vertex_args->rotMat[5] = 0.0f;
        vertex_args->rotMat[6] = 0.0f;
        vertex_args->rotMat[7] = 0.0f;
        vertex_args->rotMat[8] = 1.0f;

        vertex_args->vertex_input_buffer = vertex_input_buffer;
        vertex_args->camera = camera_C;
        for(int i = 0; i < 16; i++) {
            vertex_args->project4x4[i] = project4x4[i];
        }

        ALLOCATE_MEM(tVerts, vertex_t, num_verts);
        vertex_args->threeDVertTrans = tVerts;
        ALLOCATE_MEM(vertex_output_buffer, vertex_t, num_verts);
        vertex_args->vertex_output_buffer = vertex_output_buffer;
        
        /*** Stage 1: Run vertex shader kernel ***/
        vertex_start = clock();
        /* Vertex Shader Kernel Launch */
        {
            int total_threads = num_verts;
            int num_blocks = (total_threads + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
            run_kernel(kernel_vertexShader, num_blocks, THREADS_PER_BLOCK, (void*)vertex_args);
            printf("Launched Vertex Shader %d blocks\n", num_blocks);
        }
        vertex_end = clock();
        vertex_ms = (double)(vertex_end - vertex_start) * 1000.0 / CLOCKS_PER_SEC;
        printf("1. Vertex Shader Time: %.2f ms\n", vertex_ms);

        /*** Stage 2: Primitive Assembly ***/
        // primitive assembly outputs
        int max_assembled_verts = num_tris * 5;
        int max_surviving_tris = num_tris * 5;

        ALLOCATE_MEM(assembled_vertex_buffer, vertex_t, max_assembled_verts);
        ALLOCATE_MEM(surviving_triangle_index_buffer, triangle_t, max_surviving_tris);

        int assembled_vertex_count = 0;

        primitive_start = clock();
        int final_tri_count = primitive_assembly(vertex_output_buffer, triangle_index_buffer, num_tris, assembled_vertex_buffer, &assembled_vertex_count, max_assembled_verts, surviving_triangle_index_buffer);
        primitive_end = clock();
        primitive_ms = (double)(primitive_end - primitive_start) * 1000.0 / CLOCKS_PER_SEC;
        printf("2. Primitive Assembly Time: %.2f ms\n", primitive_ms);
        
        printf("\n[Primitive Assembly Result]\n");
        printf("Input Triangles: %d\n", num_tris);
        printf("Output Triangles: %d\n", final_tri_count);
        printf("Assembled Vertices: %d\n", assembled_vertex_count);

        /*** Stage 3: Triangle Kernel (rasterization) ***/
        ALLOCATE_MEM(triangle_args, triangle_arg_t, 1);
        const int frame_w = OUTPUT_W; const int frame_h = OUTPUT_H;
        ALLOCATE_MEM(depth_buffer, float, frame_w*frame_h); DEFAULT_ARR(depth_buffer, frame_w*frame_h, 1);
        ALLOCATE_MEM(tag_buffer, int, frame_w*frame_h);   DEFAULT_ARR(tag_buffer, frame_w*frame_h, -1);

        triangle_args->buffer_w = frame_w; triangle_args->buffer_h = frame_h;
        triangle_args->depth_buffer = depth_buffer; triangle_args->tag_buffer = tag_buffer;

        printf("--- Triangle Test ---\n");
        triangle_start = clock();
        // run the triangle kernel for each surviving triangle
        for(int tri = 0; tri < final_tri_count; tri++) {
            triangle_args->tag = tri;

            // take only the surviving triangles from primitive assembly
            triangle_args->triangle_verts[0] = assembled_vertex_buffer[surviving_triangle_index_buffer[tri].v1].coords;
            triangle_args->triangle_verts[1] = assembled_vertex_buffer[surviving_triangle_index_buffer[tri].v2].coords;
            triangle_args->triangle_verts[2] = assembled_vertex_buffer[surviving_triangle_index_buffer[tri].v3].coords;
            
            // Bounding Box
            int u_min, u_max, v_min, v_max;
            u_min = MIN3(triangle_args->triangle_verts[0].x, triangle_args->triangle_verts[1].x, triangle_args->triangle_verts[2].x) - .5; u_min = u_min < 0 ? 0 : u_min;
            u_max = MAX3(triangle_args->triangle_verts[0].x, triangle_args->triangle_verts[1].x, triangle_args->triangle_verts[2].x) + .5; u_max = u_max > (frame_w-1) ? (frame_w-1) : u_max;
            v_min = MIN3(triangle_args->triangle_verts[0].y, triangle_args->triangle_verts[1].y, triangle_args->triangle_verts[2].y) - .5; v_min = v_min < 0 ? 0 : v_min;
            v_max = MAX3(triangle_args->triangle_verts[0].y, triangle_args->triangle_verts[1].y, triangle_args->triangle_verts[2].y) + .5; v_max = v_max > (frame_h-1) ? (frame_h-1) : v_max;

            triangle_args->bb_start[0] = u_min;
            triangle_args->bb_start[1] = v_min;
            triangle_args->bb_size[0] = (u_max - u_min + 1);
            triangle_args->bb_size[1] = (v_max - v_min + 1);

            int bb_width = triangle_args->bb_size[0];
            int bb_height = triangle_args->bb_size[1];

            // Barycentric Matrix
            float m[3][3] = {
                {1, 1, 1},
                {triangle_args->triangle_verts[0].x, triangle_args->triangle_verts[1].x, triangle_args->triangle_verts[2].x},
                {triangle_args->triangle_verts[0].y, triangle_args->triangle_verts[1].y, triangle_args->triangle_verts[2].y}
            };
            matrix_inversion((float*)m, (float*) triangle_args->bc_im);

            /* Triangle Kernel Launch */
            {
                int total_threads = bb_width * bb_height;
                int num_blocks = (total_threads + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
                run_kernel(kernel_triangle, num_blocks, THREADS_PER_BLOCK, (void*)triangle_args);
            }
        }
        printf("--- Triangle Test Done ---\n");
        triangle_end = clock();
        triangle_ms = (double)(triangle_end - triangle_start) * 1000.0 / CLOCKS_PER_SEC;
        printf("3. Triangle Kernel Time: %.2f ms\n", triangle_ms);

        /*** Stage 4: Pixel Kernel ***/
        ALLOCATE_MEM(pixel_args, pixel_arg_t, 1);
        ALLOCATE_MEM(frame_buffer, vector_t, frame_w*frame_h);
        vector_t color_default = {30.0f / 255.0f, 30.0f / 255.0f, 30.0f / 255.0f};
        DEFAULT_ARR(frame_buffer, frame_w*frame_h, color_default);
        
        pixel_args->frame_buffer = frame_buffer;
        pixel_args->assembled_vertex_buffer = assembled_vertex_buffer;
        pixel_args->num_verts = assembled_vertex_count;

        // pass the culled triangles
        pixel_args->surviving_triangle_index_buffer = surviving_triangle_index_buffer; 
        pixel_args->num_tris = final_tri_count;

        pixel_args->buffer_w = frame_w; pixel_args->buffer_h = frame_h;
        pixel_args->depth_buffer = depth_buffer; pixel_args->tag_buffer = tag_buffer;
        pixel_args->texture_buffer = *texture;

        pixel_start = clock();
        /* Pixel Shader Kernel Launch */
        {
            int total_threads = frame_w * frame_h;
            int num_blocks = (total_threads + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
            run_kernel(kernel_pixel, num_blocks, THREADS_PER_BLOCK, (void*)pixel_args);
            printf("Launched Pixel Shader %d blocks\n", num_blocks);
        }
        pixel_end = clock();
        pixel_ms = (double)(pixel_end - pixel_start) * 1000.0 / CLOCKS_PER_SEC;
        printf("4. Pixel Kernel Time: %.2f ms\n", pixel_ms);

        int covered_pixels = 0;
        for(int i = 0; i < frame_w*frame_h; i++) {
            if (tag_buffer[i] != -1) covered_pixels++;
        }
        printf("Covered Pixels: %d / %d (%.2f%%)\n", covered_pixels, frame_w*frame_h, (float)covered_pixels / (frame_w*frame_h) * 100.0f);

        // Output Image
        int* int_color_output = malloc(sizeof(int) * frame_w * frame_h * 3);
        for(int i = 0; i < frame_w*frame_h; i++) {
            float r = frame_buffer[i].x;
            float g = frame_buffer[i].y;
            float b = frame_buffer[i].z;

            if (r < 0.0f) r = 0.0f;
            if (g < 0.0f) g = 0.0f;
            if (b < 0.0f) b = 0.0f;
            if (r > 1.0f) r = 1.0f;
            if (g > 1.0f) g = 1.0f;
            if (b > 1.0f) b = 1.0f;

            int_color_output[i*3 + 0] = (int)(r * 255.0f + 0.5f);
            int_color_output[i*3 + 1] = (int)(g * 255.0f + 0.5f);
            int_color_output[i*3 + 2] = (int)(b * 255.0f + 0.5f);
        }

        char fname[30];
        snprintf(fname, sizeof(fname), "build/output/frame_%03d.ppm", frame);
        createPPMFile(fname, int_color_output);

        free(int_color_output);
        frame_end = clock();
        total_ms = (double)(frame_end - frame_start) * 1000.0 / CLOCKS_PER_SEC;
        printf("Total Frame Time: %.2f ms\n", total_ms);
        printf("Frame Summary => frame=%d, camera_z=%.2f, output_tris=%d, covered_pixels=%d\n", frame, camera_C->z, final_tri_count, covered_pixels);
        printf("===== Frame %d Done =====\n\n", frame);
    }
    
    free(vertex_input_buffer);
    free(triangle_index_buffer);
    free(memory_base);
    free(loaded_texture.color_arr);
}