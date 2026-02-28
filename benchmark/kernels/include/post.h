#ifndef POST_H
#define POST_H
#include "graphics_lib.h"

typedef struct {
    //Image
    vector_t* color;

    // Pixel buffers
    int buff_w, buff_h;
    float* depth_buff;

    //Edge detection
    int threshold;
} post_arg_t;

void kernel_post(void*);

#endif