#include <stdint.h>
#include <stdio.h>
#include <math.h>
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#include "include/graphics_lib.h"

int main() {
    texture_t text = load_jpg("build/wood_texture.jpg", 0);

    int x = 10; // Example coordinates
    int y = 10;
    vector_t color = text.color_arr[y * text.w + x];
    uint8_t red = (uint8_t)(color.x * 255);
    uint8_t green = (uint8_t)(color.y * 255); 
    uint8_t blue = (uint8_t)(color.z * 255);

    printf("Pixel at (%d, %d) - R: %u, G: %u, B: %u\n", x, y, red, green, blue);

    return 0;
}