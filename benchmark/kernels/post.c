#include "include/kernel.h"
#include "include/post.h"
#include "include/graphics_lib.h"

//Don't pad, just check for out of bounds. This is doing FXAA currently. Should probably have called all this FXAA.

void kernel_post(void* arg) {
    post_arg_t* args = (post_arg_t*) arg;

    //Make 3x3 idxs
    //tl up tr
    //ml ctr mr
    //bl down br

    int ctr_idx = threadIdx;
    int up_idx = ctr_idx - args->buff_w;
    int down_idx = ctr_idx + args->buff_w;
    int tl_idx = up_idx - 1;
    int tr_idx = up_idx + 1;
    int bl_idx = down_idx - 1;
    int br_idx = down_idx + 1;
    int left_idx = ctr_idx - 1;
    int right_idx = ctr_idx + 1;

    float* zbuff = args->depth_buff;
    vector_t* out = args->color;

    //Bounds and edge check (if you're out of bounds you don't want to seg fault you just want to ignore!)
    float ctr = zbuff[ctr_idx];
    int* edge = malloc (sizeof(int) * 8);
    for (int i = 0; i < 8; i++) {
        edge[i] = -1;
    }

    if (up_idx >= 0) {
        edge[0] = (zbuff[up_idx] - ctr)/ctr;
    } 
    if (down_idx >= 0) {
        edge[1] = (zbuff[down_idx] - ctr)/ctr;
    } 
    if (tl_idx >= 0) {
        edge[2] = (zbuff[tl_idx] - ctr)/ctr;
    } 
    if (tr_idx >= 0) {
        edge[3] = (zbuff[tr_idx] - ctr)/ctr;
    } 
    if (bl_idx >= 0) {
        edge[4] = (zbuff[bl_idx] - ctr)/ctr;
    } 
    if (br_idx >= 0) {
        edge[5] = (zbuff[br_idx] - ctr)/ctr;
    } 
    if (left_idx >= 0) {
        edge[6] = (zbuff[left_idx] - ctr)/ctr;
    }
    if (right_idx >= 0) {
        edge[7] = (zbuff[left_idx] - ctr)/ctr;
    }
    
    int edge_check = max(edge) > args->threshold ? 1 : 0;

    //Perform vertical and horizontal strength check then pick dominant edge

    if (edge_check) {
        float vert = edge[0] != -1 && edge[1] != -1 ? abs((out[up_idx].x - out[down_idx].x)) + 
                     abs(((out[up_idx].y - out[down_idx].y))) + 
                     abs(((out[up_idx].z - out[down_idx].z))) : -1; 

        float horz = edge[6] != -1 && edge[7] != -1 ? abs((out[right_idx].x - out[left_idx].x)) + 
                     abs(((out[right_idx].y - out[left_idx].y))) + 
                     abs(((out[right_idx].z - out[left_idx].z))) : -1;

        //Do linear interpolation (saxpy op) perpendicular to the most dominant edge

        if (horz >= vert && vert != -1) { //If vertical edge is more dominant. Only checking for vert != -1 cause thats the edge were working with.
            out[ctr_idx].x = out[ctr_idx].x + 
                             abs((out[up_idx].x - out[down_idx].x)) * (((out[up_idx].x + out[down_idx].x)/2) - out[ctr_idx].x);
            out[ctr_idx].y = out[ctr_idx].y + 
                             abs((out[up_idx].y - out[down_idx].y)) * (((out[up_idx].y + out[down_idx].y)/2) - out[ctr_idx].y);
            out[ctr_idx].z = out[ctr_idx].z + 
                             abs((out[up_idx].z - out[down_idx].z)) * (((out[up_idx].z + out[down_idx].z)/2) - out[ctr_idx].z);
        }
        else if (vert >= horz && horz != -1) { //If horizontal edge is more dominant. Only checking for horz != -1 cause thats the edge were working with.
            out[ctr_idx].x = out[ctr_idx].x + 
                             abs((out[right_idx].x - out[left_idx].x)) * (((out[right_idx].x + out[left_idx].x)/2) - out[ctr_idx].x);
            out[ctr_idx].y = out[ctr_idx].y + 
                             abs((out[right_idx].y - out[left_idx].y)) * (((out[right_idx].y + out[left_idx].y)/2) - out[ctr_idx].y);
            out[ctr_idx].z = out[ctr_idx].z + 
                             abs((out[right_idx].z - out[left_idx].z)) * (((out[right_idx].z + out[left_idx].z)/2) - out[ctr_idx].z);
        }
    }  
}