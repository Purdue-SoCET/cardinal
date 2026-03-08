#include "include/kernel.h"
#include "include/BFS.h"

/*Abopted from https://github.com/utcs-scea/altis/blob/master/src/cuda/level1/bfs/bfs.cu#L658*/

// Kernel 1
// Checks current mask and updates neighbors
void kernel_BFS_1(void* arg) {
    bfs_kernel1_arg_t* args = (bfs_kernel1_arg_t*) arg;

    int tid = blockIdx * blockDim + threadIdx;
    
    if (tid < args->no_of_nodes && args->g_graph_mask[tid]) {
        // Mark current node as processed in the mask
        args->g_graph_mask[tid] = 0;

        int start_edge = args->g_graph_nodes[tid].starting;
        int end_edge = start_edge + args->g_graph_nodes[tid].no_of_edges;

        // Visit all neighbors
        for (int i = start_edge; i < end_edge; i++) {
            int id = args->g_graph_edges[i];
            
            // If neighbor hasn't been visited, add to next mask
            if (!args->g_graph_visited[id]) {
                args->g_cost[id] = args->g_cost[tid] + 1;
                args->g_updating_graph_mask[id] = 1;
            }
        }
    }
}

// Kernel 2
// Updates the masks and visited status for the next iteration
void kernel_BFS_2(void* arg) {
    bfs_kernel2_arg_t* args = (bfs_kernel2_arg_t*) arg;

    int tid = blockIdx * blockDim + threadIdx;

    if (tid < args->no_of_nodes && args->g_updating_graph_mask[tid]) {
        args->g_graph_mask[tid] = 1;
        args->g_graph_visited[tid] = 1;
        *(args->g_over) = 1;
        args->g_updating_graph_mask[tid] = 0;
    }
}