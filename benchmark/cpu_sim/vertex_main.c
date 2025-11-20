

#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include "include/kernel_run.h"

// Include all needed kernels
#include "../kernels/include/add.h"
#include "../kernels/include/vertexShader.h"

kernel_ptr_t* kernel_functions;

int main() {

    //****Main for Vertex Shader Kernel**** 
    // gcc -o main cpu_sim/vertex_main.c kernels/vertexShader.c cpu_sim/kernel_run.c cpu_sim/include/* kernels/include/* -DCPU_SIM

    int THREAD_NUM = 8;

    uint8_t* mem_space = malloc(sizeof(float) * (6 + (THREAD_NUM * (24+6))));

    vertexShader_arg_t arg;

    float *buf = (float*) mem_space;
    size_t off = 0;

    arg.camera = buf + off; off += 3;
    arg.alpha_r = buf + off; off += 3;
    arg.a_dist = buf + off; off += (3*THREAD_NUM);
    arg.threeDVert = (vertex_t*)(buf + off); off += ((3+2)*THREAD_NUM);
    arg.threeDVertTrans = (vertex_t*)(buf + off); off += ((3+2)*THREAD_NUM);
    arg.twoDVert = (vertex_t*)(buf + off); off += ((3+2)*THREAD_NUM);
    arg.invTrans= buf + off; off += (9*THREAD_NUM);
    arg.Oa = buf + off; off += (3*THREAD_NUM);

    for(int a = 0; a < (THREAD_NUM*3); a++){
        if(a<3){
            arg.camera[a] = 0.f;
            arg.alpha_r[a] = 0.f;
        }
        arg.Oa[a] = 0.f;
        arg.a_dist[a] = 1.f;
    }

    for(int a = 0; a < (THREAD_NUM); a++) {
        arg.threeDVert[a].coords.x = 1;
        arg.threeDVert[a].coords.y = 1;
        arg.threeDVert[a].coords.z = 1;
        arg.threeDVert[a].s = .5f;
        arg.threeDVert[a].t = .5f;

        arg.threeDVertTrans[a].coords.x = 0.f;
        arg.threeDVertTrans[a].coords.y = 0.f;
        arg.threeDVertTrans[a].coords.z = 0.f;
        arg.threeDVertTrans[a].s = 0.f;
        arg.threeDVertTrans[a].t = 0.f;

        arg.twoDVert[a].coords.x = 0.f;
        arg.twoDVert[a].coords.y = 0.f;
        arg.twoDVert[a].coords.z = 0.f;
        arg.twoDVert[a].s = 0.f;
        arg.twoDVert[a].t = 0.f;
    }

    for (int b = 0; b < 3; b++) {
        for (int a = 0; a < 3; a++) {
        arg.invTrans[a + 3 * b] = (a == b) ? 1.f : 0.f;
        }
    }

    printf("*****************\n");
    printf("Trans:");
    for(int a = 0; a < (3*3); a++){
        if(a%3 == 0) printf("\n");
        if(a%9 == 0) printf("---------------\ni=%d\n", a/9);
        printf("%.2f ", arg.invTrans[a]);
    }
    printf("\n");
    printf("*****************\n");

    dim_t grid; grid.x = 1; grid.y = 1; grid.z = 1;
    dim_t block; block.x = THREAD_NUM; block.y = 1; block.z = 1;
    run_kernel(kernel_vertexShader, grid, block, (void*)&arg);

    for(int i = 0; i < (THREAD_NUM*3); i=i+3) {
        printf("i = %d\n", i/3);
        printf("Original: ");
        printf("%.2f %.2f %.2f - %.2f %.2f\n", arg.threeDVert[i/3].coords.x, arg.threeDVert[i/3].coords.y, arg.threeDVert[i/3].coords.z, arg.threeDVert[i/3].s, arg.threeDVert[i/3].t);
        printf("3D: ");
        printf("%.2f %.2f %.2f - %.2f %.2f\n", arg.threeDVertTrans[i/3].coords.x, arg.threeDVertTrans[i/3].coords.y, arg.threeDVertTrans[i/3].coords.z, arg.threeDVertTrans[i/3].s, arg.threeDVertTrans[i/3].t);
        printf("2D: ");
        printf("%.2f %.2f %.2f - %.2f %.2f\n", arg.twoDVert[i/3].coords.x, arg.twoDVert[i/3].coords.y, arg.twoDVert[i/3].coords.z, arg.twoDVert[i/3].s, arg.twoDVert[i/3].t);
        printf("------------------\n");
    }
    printf("*****************\n");

    //glDrawPixels(width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels);

    free(mem_space);

    return 0;
}