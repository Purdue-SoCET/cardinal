#include "include/kernel.h"
#include "include/BFS.h"

/*Abopted from https://github.com/utcs-scea/altis/blob/master/src/cuda/level1/bfs/bfs.cu#L658*/

// Updates the masks and visited status for the next iteration
#ifdef GPU_SIM
void main(void* arg)
#else
void kernel_BFS_2(void* arg) 
#endif
{
    #ifdef GPU_SIM
    bfs_kernel2_arg_t* args = (bfs_kernel2_arg_t*) argPtr();

    int tid = blockIdx() * blockDim() + threadIdx();
    #else
    bfs_kernel2_arg_t* args = (bfs_kernel2_arg_t*) arg;

    int tid = blockIdx * blockDim + threadIdx;
    #endif

    if (tid < args->no_of_nodes && args->g_updating_graph_mask[tid]) {
        args->g_graph_mask[tid] = 1;
        args->g_graph_visited[tid] = 1;
        *(args->g_over) = 1;
        args->g_updating_graph_mask[tid] = 0;
    }
}