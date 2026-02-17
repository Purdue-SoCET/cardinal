// Standard Includes
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "include/kernel_run.h"
#include "include/graphics_lib.h"

// Include all needed kernels
#include "../kernels/include/vertexShader.h"
#include "../kernels/include/triangle.h"
#include "../kernels/include/pixel.h"


int main() {
    model_t teapot;
    loadbin("cpu_sim/data/geometry/teapot1K.bin", &teapot);

    // Example: Accessing data
    if (teapot.vertsN > 0) {
        printf("First Triangle indices: %u, %u, %u\n", 
                teapot.triangles[0].v1, teapot.triangles[0].v2, teapot.triangles[0].v3);
        printf("First Vertex: X=%f, Y=%f, Z=%f, U=%f, V=%f\n", 
                teapot.vertices[0].coords.x, teapot.vertices[0].coords.y, teapot.vertices[0].coords.z,
                teapot.vertices[0].s, teapot.vertices[0].t);
    }

    // Cleanup
    free(teapot.vertices);
    free(teapot.triangles);
    return 0;
}