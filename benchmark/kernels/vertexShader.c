#include "include/kernel.h"
#include "include/vertexShader.h"
#include "include/graphics_lib.h"


#ifdef GPU_SIM
void main(void* arg)
#else
void kernel_vertexShader(void* arg)
#endif
{
    #ifdef GPU_SIM
    vertexShader_arg_t* args = (vertexShader_arg_t*) argPtr();
    int i = blockIdx() * blockDim() + threadIdx();
    #else
    vertexShader_arg_t* args = (vertexShader_arg_t*) arg;
    int i = blockIdx * blockDim + threadIdx;
    #endif

    if(i >= args->num_verts) return;

    /****** ThreeD Rotation ******/
    // assuming radian
    // V3::RotateThisPointAboutArbitraryAxis and TM::RotateAboutArbitraryAxis

    float lcs[9];
    float selAxis[3] = {0.0, 0.0, 0.0};

    if((args->a_dist->x*args->a_dist->x) < (args->a_dist->y*args->a_dist->y))
    {
        selAxis[0] = 1.0;
    }
    else
    {
        selAxis[1] = 1.0;
    }

   selAxis[1] = 1.0;

    /* Build Local Coordinates System*/

    //cross(selAxis, args->a_dist)
    lcs[0] = selAxis[1] * args->a_dist->z - selAxis[2] * args->a_dist->y;
    lcs[1] = selAxis[2] * args->a_dist->x - selAxis[0] * args->a_dist->z;
    lcs[2] = selAxis[0] * args->a_dist->y - selAxis[1] * args->a_dist->x;

    //normalize(lcs[0 to 2])
    float inv_lcs_dist = isqrt(lcs[0]*lcs[0] + lcs[1]*lcs[1] + lcs[2]*lcs[2]);
    
    // Unrolled j loop (0 to 2)
    lcs[0] = lcs[0] * inv_lcs_dist;
    lcs[1] = lcs[1] * inv_lcs_dist;
    lcs[2] = lcs[2] * inv_lcs_dist;

    lcs[3] = args->a_dist->x;
    lcs[4] = args->a_dist->y;
    lcs[5] = args->a_dist->z;

    lcs[6] = lcs[1] * lcs[5] - lcs[2] * lcs[4];
    lcs[7] = lcs[2] * lcs[3] - lcs[0] * lcs[5];
    lcs[8] = lcs[0] * lcs[4] - lcs[1] * lcs[3];

    //normalize(lcs[3 to 5])
    inv_lcs_dist = isqrt(lcs[3]*lcs[3] + lcs[4]*lcs[4] + lcs[5]*lcs[5]);
    
    // Unrolled j loop (3 to 5)
    lcs[3] = lcs[3] * inv_lcs_dist;
    lcs[4] = lcs[4] * inv_lcs_dist;
    lcs[5] = lcs[5] * inv_lcs_dist;

    //normalize(lcs[6 to 8])
    inv_lcs_dist = isqrt(lcs[6]*lcs[6] + lcs[7]*lcs[7] + lcs[8]*lcs[8]);
    
    // Unrolled j loop (6 to 8)
    lcs[6] = lcs[6] * inv_lcs_dist;
    lcs[7] = lcs[7] * inv_lcs_dist;
    lcs[8] = lcs[8] * inv_lcs_dist;

    // vertex normalized to rotation origin
    float p_tempAxis[3] = {
        (args->threeDVert[i].coords.x   - args->Oa->x),
        (args->threeDVert[i].coords.y - args->Oa->y),
        (args->threeDVert[i].coords.z - args->Oa->z)
    };

    /*Create Rotation Matrix */

    // Y AXIS M33::MakeRotationMatrix

    float rotMat[9] = {
        cos(*(args->alpha_r)), 0, sin(*(args->alpha_r)),
        0, 1, 0,
        -sin(*(args->alpha_r)), 0, cos(*(args->alpha_r))
    };


    /*invert LCS where LCS^-1 = LCS.T*/
    float lcsInv[9];
    
    // Unrolled row and col loops
    // row = 0
    lcsInv[0*3 + 0] = lcs[0*3 + 0]; // col = 0
    lcsInv[1*3 + 0] = lcs[0*3 + 1]; // col = 1
    lcsInv[2*3 + 0] = lcs[0*3 + 2]; // col = 2
    
    // row = 1
    lcsInv[0*3 + 1] = lcs[1*3 + 0]; // col = 0
    lcsInv[1*3 + 1] = lcs[1*3 + 1]; // col = 1
    lcsInv[2*3 + 1] = lcs[1*3 + 2]; // col = 2
    
    // row = 2
    lcsInv[0*3 + 2] = lcs[2*3 + 0]; // col = 0
    lcsInv[1*3 + 2] = lcs[2*3 + 1]; // col = 1
    lcsInv[2*3 + 2] = lcs[2*3 + 2]; // col = 2

    /*world -> local*/
    float p1[3] = {0, 0, 0};
    
    // Unrolled j and k loops
    // j = 0
    p1[0] += lcsInv[0*3 + 0] * p_tempAxis[0]; // k = 0
    p1[0] += lcsInv[1*3 + 0] * p_tempAxis[1]; // k = 1
    p1[0] += lcsInv[2*3 + 0] * p_tempAxis[2]; // k = 2
    
    // j = 1
    p1[1] += lcsInv[0*3 + 1] * p_tempAxis[0]; // k = 0
    p1[1] += lcsInv[1*3 + 1] * p_tempAxis[1]; // k = 1
    p1[1] += lcsInv[2*3 + 1] * p_tempAxis[2]; // k = 2
    
    // j = 2
    p1[2] += lcsInv[0*3 + 2] * p_tempAxis[0]; // k = 0
    p1[2] += lcsInv[1*3 + 2] * p_tempAxis[1]; // k = 1
    p1[2] += lcsInv[2*3 + 2] * p_tempAxis[2]; // k = 2

    /* rotate in local space */
    float p2[3] = {0, 0, 0};
    
    // Unrolled j and k loops
    // j = 0
    p2[0] += rotMat[0*3 + 0] * p1[0]; // k = 0
    p2[0] += rotMat[1*3 + 0] * p1[1]; // k = 1
    p2[0] += rotMat[2*3 + 0] * p1[2]; // k = 2
    
    // j = 1
    p2[1] += rotMat[0*3 + 1] * p1[0]; // k = 0
    p2[1] += rotMat[1*3 + 1] * p1[1]; // k = 1
    p2[1] += rotMat[2*3 + 1] * p1[2]; // k = 2
    
    // j = 2
    p2[2] += rotMat[0*3 + 2] * p1[0]; // k = 0
    p2[2] += rotMat[1*3 + 2] * p1[1]; // k = 1
    p2[2] += rotMat[2*3 + 2] * p1[2]; // k = 2

    /* local -> world */
    float p_world[3] = {0, 0, 0};
    
    // Unrolled j and k loops
    // j = 0
    p_world[0] += lcs[0*3 + 0] * p2[0]; // k = 0
    p_world[0] += lcs[1*3 + 0] * p2[1]; // k = 1
    p_world[0] += lcs[2*3 + 0] * p2[2]; // k = 2
    args->threeDVertTrans[i].coords.x = p_world[0] + args->Oa->x;
    
    // j = 1
    p_world[1] += lcs[0*3 + 1] * p2[0]; // k = 0
    p_world[1] += lcs[1*3 + 1] * p2[1]; // k = 1
    p_world[1] += lcs[2*3 + 1] * p2[2]; // k = 2
    args->threeDVertTrans[i].coords.y = p_world[1] + args->Oa->y;
    
    // j = 2
    p_world[2] += lcs[0*3 + 2] * p2[0]; // k = 0
    p_world[2] += lcs[1*3 + 2] * p2[1]; // k = 1
    p_world[2] += lcs[2*3 + 2] * p2[2]; // k = 2
    args->threeDVertTrans[i].coords.z = p_world[2] + args->Oa->z;
    
    args->threeDVertTrans[i].s = args->threeDVert[i].s;
    args->threeDVertTrans[i].t = args->threeDVert[i].t;


    /****** Projection ******/
    //PPC::Project

    /*Normalize 3D matrix w.r.t the camera*/
    float threeD_norm[3] = {
        args->threeDVertTrans[i].coords.x - args->camera->x,
        args->threeDVertTrans[i].coords.y - args->camera->y,
        args->threeDVertTrans[i].coords.z - args->camera->z
    };

    float q[3] = {0.0, 0.0, 0.0};

    // q = 3Dnorm @ trans^-1
    // Unrolled j and k loops
    // j = 0
    q[0] += threeD_norm[0] * args->invTrans[0*3 + 0]; // k = 0
    q[0] += threeD_norm[1] * args->invTrans[0*3 + 1]; // k = 1
    q[0] += threeD_norm[2] * args->invTrans[0*3 + 2]; // k = 2
    
    // j = 1
    q[1] += threeD_norm[0] * args->invTrans[1*3 + 0]; // k = 0
    q[1] += threeD_norm[1] * args->invTrans[1*3 + 1]; // k = 1
    q[1] += threeD_norm[2] * args->invTrans[1*3 + 2]; // k = 2
    
    // j = 2
    q[2] += threeD_norm[0] * args->invTrans[2*3 + 0]; // k = 0
    q[2] += threeD_norm[1] * args->invTrans[2*3 + 1]; // k = 1
    q[2] += threeD_norm[2] * args->invTrans[2*3 + 2]; // k = 2

    // if (q[2] < 0.0){
    //     return;
    // }
    // if (q[2] == 0.0){
    //     return;
    // }
    if(q[2] >= 0.0){
        args->twoDVert[i].coords.x = q[0] / q[2];
        args->twoDVert[i].coords.y = q[1] / q[2];
        args->twoDVert[i].coords.z = 1.0 / q[2];

        args->twoDVert[i].s = args->threeDVert[i].s;
        args->twoDVert[i].t = args->threeDVert[i].t;
    }
    return;
}