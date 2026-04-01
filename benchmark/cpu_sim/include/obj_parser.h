#ifndef OBJ_PARSER_H
#define OBJ_PARSER_H

#include "graphics_lib.h"

// 1. count vertex and triangle elements in the .obj file
int count_obj_elements(const char* filename, int* out_num_verts, int* out_num_tris);

// 2. load vertex and triangle data from the .obj file into the provided arrays
int load_obj_data(const char* filename, vertex_t* vertex_input_buffer, triangle_t* triangle_index_buffer);

// 3. obj_parser main function to be called from main.c
int obj_parser(const char* filename, vertex_t** vertex_input_buffer, int* out_num_verts, triangle_t** triangle_index_buffer, int* out_num_tris);

void calculate_normals(vertex_t* vertex_input_buffer, int num_verts, triangle_t* triangle_index_buffer, int num_tris);

#endif