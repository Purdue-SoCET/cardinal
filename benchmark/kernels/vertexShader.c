#include "include/kernel.h"
#include "include/vertexShader.h"

void kernel_vertexShader(void* arg)
{
    vertexShader_arg_t* args = (vertexShader_arg_t*) arg;

    int i = blockIdx.x * blockDim.x + threadIdx.x;

    if(i > 1023) return;

    /****** ThreeD Rotation ******/ 
    // - assuming radians and following V3::RotateThisPointAboutArbitraryAxis and TM::RotateAboutArbitraryAxis

    float lcs[9]; 
    float selAxis[3] = {0.0f, 0.0f, 0.0f};

    /*
    if((args->a_dist[i]*args->a_dist[i]) < (args->a_dist[i+1]*args->a_dist[i+1]))
    { 
        selAxis[0] = 1.0f;
    }
    else
    {
        selAxis[1] = 1.0f;
    }
    */

   selAxis[1] = 1.0f;

    /* Build Local Coordinates System*/

    //cross(selAxis, args->a_dist)
    lcs[0] = selAxis[1] * args->a_dist[3*i+2] - selAxis[2] * args->a_dist[3*i+1];
    lcs[1] = selAxis[2] * args->a_dist[3*i]   - selAxis[0] * args->a_dist[3*i+2];
    lcs[2] = selAxis[0] * args->a_dist[3*i+1] - selAxis[1] * args->a_dist[3*i];

    //normalize(lcs[0 to 2])

    // CPU Sim Version
    #ifdef CPU_SIM
    float lcs_dist = sqrt(lcs[0]*lcs[0] + lcs[1]*lcs[1] + lcs[2]*lcs[2]);
    #endif
    // Hardware/Emulator Version (isqrt not sqrt)
    #ifdef HARDWARE_SIM
    float inv_lcs_dist = isqrt(lcs[0]*lcs[0] + lcs[1]*lcs[1] + lcs[2]*lcs[2]);
    float lcs_dist = 1 / (inv_lcs_dist);
    #endif

    for(int j = 0; j < 3; j++)
    {
        lcs[j] = lcs[j] / lcs_dist;
    }

    lcs[3] = args->a_dist[3*i];
    lcs[4] = args->a_dist[3*i+1];
    lcs[5] = args->a_dist[3*i+2];

    lcs[6] = lcs[1] * lcs[5] - lcs[2] * lcs[4];
    lcs[7] = lcs[2] * lcs[3] - lcs[0] * lcs[5];
    lcs[8] = lcs[0] * lcs[4] - lcs[1] * lcs[3];

    //normalize(lcs[3 to 5])
    lcs_dist = sqrt(lcs[3]*lcs[3] + lcs[4]*lcs[4] + lcs[5]*lcs[5]);
    for(int j = 3; j < 6; j++)
    {
        lcs[j] = lcs[j] / lcs_dist;
    }

    //normalize(lcs[6 to 8])
    lcs_dist = sqrt(lcs[6]*lcs[6] + lcs[7]*lcs[7] + lcs[8]*lcs[8]);
    for(int j = 6; j < 9; j++)
    {
        lcs[j] = lcs[j] / lcs_dist;
    }

    // vertex normalized to rotation origin
    float p_tempAxis[3] = {
        (args->threeDVert[3*i]   - args->Oa[3*i]),
        (args->threeDVert[3*i+1] - args->Oa[3*i+1]),
        (args->threeDVert[3*i+2] - args->Oa[3*i+2])
    };

    /*Create Rotation Matrix */

    //Y AXIS M33::MakeRotationMatrix
    float rotMat[9] = {
        cosf(args->alpha_r[i]), 0, sinf(args->alpha_r[i]),
        0, 1, 0,
        -sinf(args->alpha_r[i]), 0, cosf(args->alpha_r[i])
    };

    /*invert LCS where LCS^-1 = LCS.T*/
    float lcsInv[9];
    for (int row = 0; row < 3; ++row) {
        for (int col = 0; col < 3; ++col) {
            lcsInv[col*3 + row] = lcs[row*3 + col];
        }
    }

    /*world -> local*/
    float p1[3] = {0, 0, 0};
    for(int j = 0; j < 3; j++)
    {
        for(int k = 0; k < 3; k++)
        {
            p1[j] += lcsInv[k*3 + j] * p_tempAxis[k];
        }
    }

    /* rotate in local space */
    float p2[3] = {0, 0, 0};
    for(int j = 0; j < 3; j++)
    {
        for(int k = 0; k < 3; k++)
        {
            p2[j] += rotMat[k*3 + j] * p1[k]; 
        }
    }

    /* local -> world */
    float p_world[3] = {0, 0, 0};
    for(int j = 0; j < 3; j++)
    {
        for(int k = 0; k < 3; k++)
        {
            p_world[j] += lcs[k*3 + j] * p2[k]; 
        }
        args->threeDVertTrans[i*3 + j] = p_world[j] + args->Oa[3*i+j];
    }

    
    /****** Projection ******/
    //PPC::Project

    /*Normalize 3D matrix w.r.t the camera*/
    float threeD_norm[3] = { 
        args->threeDVertTrans[3*i] - args->camera[0],
        args->threeDVertTrans[3*i + 1] - args->camera[1],
        args->threeDVertTrans[3*i + 2] - args->camera[2]
    };

    float q[3] = {0, 0, 0};

    //q = 3Dnorm @ trans^-1
    for(int j = 0; j < 3; j++)
    {
        for(int k = 0; k < 3; k++)
        {
            q[j] += threeD_norm[k] * args->invTrans[k*3 + j]; 
        }
    }

    if (q[2] <= 0.0f) return;

    args->twoDVert[3*i]   = q[0] / q[2];
    args->twoDVert[3*i+1] = q[1] / q[2];
    args->twoDVert[3*i+2] = 1.0f / q[2];

    return;
}