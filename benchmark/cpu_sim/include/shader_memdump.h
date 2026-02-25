#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>

#include "../../kernels/include/vertexShader.h"
#include "../../kernels/include/triangle.h"
#include "../../kernels/include/pixel.h"

void print_line(FILE* f, uintptr_t addr, uint32_t data);

void print_vertex_args(char* fname, vertexShader_arg_t* vertex_args, int num_verts);

void print_triangle_args(char* fname, triangle_arg_t* tri_args);

void print_pixel_args(char* fname, pixel_arg_t* pix_args);