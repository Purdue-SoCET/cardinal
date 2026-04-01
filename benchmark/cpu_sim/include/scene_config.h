#ifndef SCENE_CONFIG_H
#define SCENE_CONFIG_H

#include "graphics_lib.h"

// camera configuration for scene setup
typedef struct {
    vector_t position;
    float invTrans[9];
    int viewport_w;
    int viewport_h;
} CameraConfig;

// light configuration for scene setup
typedef struct {
    vector_t direction;
    float ambient;
    float diffuse;
} LightConfig;

// object transformation configuration for scene setup
typedef struct {
    vector_t origin; // rotation origin
    vector_t axis; // rotation axis
    float angle; // rotation angle

    // precomputed matrices for rotation and local coordinate system
    float lcs[9];
    float lcsInv[9];
    float rotMat[9];
} ObjectConfig;

#endif