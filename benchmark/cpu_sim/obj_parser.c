#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "include/obj_parser.h"
#include "include/graphics_lib.h"

void calculate_normals(vertex_t* vertex_input_buffer, int num_verts, triangle_t* triangle_index_buffer, int num_tris) {
    // 1. initialize vertex normals to zero
    for (int i = 0; i < num_verts; i++) {
        vertex_input_buffer[i].normal.x = 0.0f;
        vertex_input_buffer[i].normal.y = 0.0f;
        vertex_input_buffer[i].normal.z = 0.0f;
        vertex_input_buffer[i].intensity = 0.0f;
    }

    // 2. for each triangle, calculate the face normal and accumulate it to the vertices
    for (int i = 0; i < num_tris; i++) {
        int idx1 = triangle_index_buffer[i].v1;
        int idx2 = triangle_index_buffer[i].v2;
        int idx3 = triangle_index_buffer[i].v3;

        vector_t p1 = vertex_input_buffer[idx1].coords;
        vector_t p2 = vertex_input_buffer[idx2].coords;
        vector_t p3 = vertex_input_buffer[idx3].coords;

        // calculate edge vectors
        vector_t edge1 = {p2.x - p1.x, p2.y - p1.y, p2.z - p1.z};
        vector_t edge2 = {p3.x - p1.x, p3.y - p1.y, p3.z - p1.z};

        // calculate face normal using cross product of edge vectors
        vector_t face_normal = cross_product(edge1, edge2);

        // accumulate the face normal to each vertex normal of the triangle
        vertex_input_buffer[idx1].normal.x += face_normal.x; vertex_input_buffer[idx1].normal.y += face_normal.y; vertex_input_buffer[idx1].normal.z += face_normal.z;
        vertex_input_buffer[idx2].normal.x += face_normal.x; vertex_input_buffer[idx2].normal.y += face_normal.y; vertex_input_buffer[idx2].normal.z += face_normal.z;
        vertex_input_buffer[idx3].normal.x += face_normal.x; vertex_input_buffer[idx3].normal.y += face_normal.y; vertex_input_buffer[idx3].normal.z += face_normal.z;
    }

    // 3. normalize accumulated vectors to get smooth vertex normals
    for (int i = 0; i < num_verts; i++) {
        normalize_vector(&vertex_input_buffer[i].normal);
    }
}

// count vertex and triangle elements in the .obj file
int count_obj_elements(const char* filename, int* out_num_verts, int* out_num_tris) {
    FILE* file = fopen(filename, "r");
    if (!file) {
        printf("Error: %s cannot be opened\n", filename);
        return 0;
    }

    int v_count = 0;
    int f_count = 0;
    char line[128];

    if (!out_num_verts || !out_num_tris) {
        printf("Error: Output pointers cannot be NULL\n");
        fclose(file);
        return 0;
    }

    // read through the file line by line
    while (fgets(line, sizeof(line), file)) {
        if (strncmp(line, "v ", 2) == 0) v_count++;
        else if (strncmp(line, "f ", 2) == 0) f_count++;
    }

    *out_num_verts = v_count;
    *out_num_tris = f_count;

    fclose(file);
    return 1;
}

// load vertex and triangle data from the .obj file into buffers (like Input Assembler)
int load_obj_data(const char* filename, vertex_t* vertex_input_buffer, triangle_t* triangle_index_buffer) {
    // buffer null check
    if (!vertex_input_buffer || !triangle_index_buffer) {
        printf("Error: Input buffers cannot be NULL\n");
        return 0;
    }

    FILE* file = fopen(filename, "r");
    // file open check
    if (!file) {
        printf("Error: %s cannot be opened\n", filename);
        return 0;
    }

    char line[128];
    int v_idx = 0;
    int f_idx = 0;

    while (fgets(line, sizeof(line), file)) {
        // "v x y z" -> x, y, z parsing
        if (strncmp(line, "v ", 2) == 0) {
            float x, y, z;
            sscanf(line, "v %f %f %f", &x, &y, &z);
            
            // save coordinates and set default texture coordinates
            vertex_input_buffer[v_idx].coords.x = x;
            vertex_input_buffer[v_idx].coords.y = y;
            vertex_input_buffer[v_idx].coords.z = z;
            vertex_input_buffer[v_idx].u = 0.0f; 
            vertex_input_buffer[v_idx].v = 0.0f;
            
            v_idx++;
        }
        // face data "f v1 v2 v3" -> v1, v2, v3 parsing
        else if (strncmp(line, "f ", 2) == 0) {
            int v1, v2, v3;

            sscanf(line, "f %d %d %d", &v1, &v2, &v3);
            
            triangle_index_buffer[f_idx].v1 = v1 - 1;
            triangle_index_buffer[f_idx].v2 = v2 - 1;
            triangle_index_buffer[f_idx].v3 = v3 - 1;
            
            f_idx++;
        }
    }

    fclose(file);
    return 1;
}

int obj_parser(const char* filename, vertex_t** vertex_input_buffer, int* out_num_verts, triangle_t** triangle_index_buffer, int* out_num_tris) {
    *vertex_input_buffer = NULL;
    *triangle_index_buffer = NULL;
    *out_num_verts = 0;
    *out_num_tris = 0;

    int v_count = 0;
    int f_count = 0;

    // 1. counting vertices and triangles
    if (!count_obj_elements(filename, &v_count, &f_count)) {
        return 0;
    }

    // 2. malloc for vertex and triangle data
    *vertex_input_buffer = (vertex_t*)malloc(sizeof(vertex_t) * v_count);
    *triangle_index_buffer = (triangle_t*)malloc(sizeof(triangle_t) * f_count);

    // check malloc success
    if (!(*vertex_input_buffer) || !(*triangle_index_buffer)) {
        printf("Error: Memory allocation failed\n");
        // reset
        free(*vertex_input_buffer);
        free(*triangle_index_buffer);
        *vertex_input_buffer = NULL;
        *triangle_index_buffer = NULL;

        return 0;
    }

    // 3. load vertex and triangle data
    if (!load_obj_data(filename, *vertex_input_buffer, *triangle_index_buffer)) {
        free(*vertex_input_buffer);
        free(*triangle_index_buffer);
        *vertex_input_buffer = NULL;
        *triangle_index_buffer = NULL;

        return 0;
    }

    // // 4. calculate vertex normals for lighting calculations
    // calculate_normals(*vertex_input_buffer, v_count, *triangle_index_buffer, f_count);

    // 5. set output counts
    *out_num_verts = v_count;
    *out_num_tris = f_count;

    printf("Obj Parser: Loaded %d vertices, %d triangles from %s\n", v_count, f_count, filename);
    return 1;
}


// // test
// int main() {
//     int v_count = 0;
//     int f_count = 0;
//     const char* filename = "teapot.obj";

//     printf("Test Start: %s reading\n", filename);

//     if (count_obj_elements(filename, &v_count, &f_count)) {
//         printf("Success!\n");
//         printf("Number of Vertex: %d\n", v_count);
//         printf("Number of Triangle: %d\n", f_count);
//     } else {
//         printf("Failed: File not found or read error.\n");
//     }

//     return 0;
// }