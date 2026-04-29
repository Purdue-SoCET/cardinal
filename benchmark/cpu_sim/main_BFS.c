// Standard Includes
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>
#include <time.h>
#include <limits.h>
#include <sys/mman.h>
#include <errno.h>
#include <string.h>
#include <math.h>
#include <assert.h>
#include <stdbool.h>

#include "include/kernel_run.h"
#include "include/shader_memdump.h"
#include "include/graphics_lib.h"

// Include BFS Kernels
#include "../kernels/include/BFS.h" 

// Simulation Constants
#define ARGS_BASE_ADDR 0x00100000
#define HEAP_BASE_ADDR 0x10000000
#define MIN_EDGES 20
#define MAX_INIT_EDGES (1024*1024)

// Toggle memory dumps
#define INPUT_MEM_DUMP 1
#define OUTPUT_MEM_DUMP 1

// --- Macros ---
#define ALLOCATE_ARGS(dest, type, num) \
    type* dest = (type*) args_ptr; \
    args_ptr += (num) * sizeof(type);

#define ALLOCATE_HEAP(dest, type, num) \
    type* dest = (type*) heap_ptr; \
    heap_ptr += (num) * sizeof(type);

// --- Helper Functions ---

void initGraph(int *no_of_nodes, int *edge_list_size, int *source, Node **h_graph_nodes, int **h_graph_edges) {
    bool quiet = false;
    char* infile = "cpu_sim/data/BFS/bfs_128"; 
    
    FILE *fp = fopen(infile, "r");
    if(!fp && !quiet) printf("Error: Unable to read graph file %s.\n", infile);

    if(fp) {
        int n = fscanf(fp, "%d", no_of_nodes);
        assert(n == 1);
    } else {
        *no_of_nodes = 1024;
    }

    *h_graph_nodes = (Node*) malloc(sizeof(Node) * (*no_of_nodes));
    int start, edgeno;
    *edge_list_size = 0; 

    for (int i = 0; i < *no_of_nodes; i++) {
        if(fp) {
            fscanf(fp, "%d %d", &start, &edgeno);
        } else {
            start = *edge_list_size;
            edgeno = rand() % (MAX_INIT_EDGES - MIN_EDGES + 1) + MIN_EDGES;
        }
        (*h_graph_nodes)[i].starting = start;
        (*h_graph_nodes)[i].no_of_edges = edgeno;
        *edge_list_size += edgeno;
    }

    if (fp) fscanf(fp, "%d", source); else *source = 0;
    if (fp) { int dummy; fscanf(fp, "%d", &dummy); }

    *h_graph_edges = (int*) malloc(sizeof(int) * (*edge_list_size));
    for (int i = 0; i < *edge_list_size ; i++) {
        if (fp) {
            int id, cost;
            fscanf(fp, "%d %d", &id, &cost);
            (*h_graph_edges)[i] = id;
        } else {
            (*h_graph_edges)[i] = rand() % (*no_of_nodes);
        }
    }
    if(fp) fclose(fp);
}

void run_cpu_bfs(int no_of_nodes, Node *h_graph_nodes, int *h_graph_edges, int source, int *cpu_cost) {
    for (int i = 0; i < no_of_nodes; i++) cpu_cost[i] = -1;
    int *queue = (int*) malloc(sizeof(int) * no_of_nodes);
    int head = 0, tail = 0;
    cpu_cost[source] = 0;
    queue[tail++] = source;
    while (head < tail) {
        int u = queue[head++]; 
        for (int i = 0; i < h_graph_nodes[u].no_of_edges; i++) {
            int v = h_graph_edges[h_graph_nodes[u].starting + i];
            if (cpu_cost[v] == -1) {
                cpu_cost[v] = cpu_cost[u] + 1;
                queue[tail++] = v; 
            }
        }
    }
    free(queue);
}

// --- Main CPU Sim ---

int main(int argc, char** argv) {
    (void)argc; (void)argv;
    uint8_t *args_ptr, *heap_ptr;
    uint8_t *args_start_ptr, *heap_start_ptr;

    size_t args_size = 15 * 1024 * 1024;
    args_start_ptr = mmap((void*)ARGS_BASE_ADDR, args_size, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED, -1, 0);

    size_t heap_size = 256 * 1024 * 1024;
    heap_start_ptr = mmap((void*)HEAP_BASE_ADDR, heap_size, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED, -1, 0);

    if (args_start_ptr == MAP_FAILED || heap_start_ptr == MAP_FAILED) return -1;

    args_ptr = args_start_ptr;
    heap_ptr = heap_start_ptr;

    int no_of_nodes, edge_list_size, source;
    Node* h_graph_nodes_tmp;
    int* h_graph_edges_tmp;
    initGraph(&no_of_nodes, &edge_list_size, &source, &h_graph_nodes_tmp, &h_graph_edges_tmp);

    ALLOCATE_HEAP(d_graph_nodes, Node, no_of_nodes);
    ALLOCATE_HEAP(d_graph_edges, int, edge_list_size);
    ALLOCATE_HEAP(d_graph_mask, int, no_of_nodes);
    ALLOCATE_HEAP(d_updating_mask, int, no_of_nodes);
    ALLOCATE_HEAP(d_graph_visited, int, no_of_nodes);
    ALLOCATE_HEAP(d_cost, int, no_of_nodes);
    ALLOCATE_HEAP(d_over, int, 1);

    memcpy(d_graph_nodes, h_graph_nodes_tmp, no_of_nodes * sizeof(Node));
    memcpy(d_graph_edges, h_graph_edges_tmp, edge_list_size * sizeof(int));

    for (int i = 0; i < no_of_nodes; i++) {
        d_cost[i] = -1;
        d_graph_mask[i] = 0;
        d_updating_mask[i] = 0;
        d_graph_visited[i] = 0;
    }

    d_graph_visited[source] = 1;
    d_graph_mask[source] = 1;
    d_cost[source] = 0;

    ALLOCATE_ARGS(arg1, bfs_kernel1_arg_t, 1);
    arg1->g_graph_nodes = d_graph_nodes;
    arg1->g_graph_edges = d_graph_edges;
    arg1->g_graph_mask = d_graph_mask;
    arg1->g_updating_graph_mask = d_updating_mask;
    arg1->g_graph_visited = d_graph_visited;
    arg1->g_cost = d_cost;
    arg1->no_of_nodes = no_of_nodes;

    ALLOCATE_ARGS(arg2, bfs_kernel2_arg_t, 1);
    arg2->g_graph_mask = d_graph_mask;
    arg2->g_updating_graph_mask = d_updating_mask;
    arg2->g_graph_visited = d_graph_visited;
    arg2->g_over = d_over;
    arg2->no_of_nodes = no_of_nodes;

    size_t used_args_bytes = (uintptr_t)args_ptr - (uintptr_t)args_start_ptr;
    size_t used_heap_bytes = (uintptr_t)heap_ptr - (uintptr_t)heap_start_ptr;

    int k = 0;
    bool stop;

    FILE* file_thread = fopen("build/threads/BFSThreads.txt", "w");

    printf("Starting BFS Loop...\n");

    do {
        *d_over = 0;

        if (INPUT_MEM_DUMP) {
            char f_args[256], f_heap[256];
            snprintf(f_args, sizeof(f_args), "build/mem_dump/BFSInput%d_args_dump.txt", k);
            snprintf(f_heap, sizeof(f_heap), "build/mem_dump/BFSInput%d_heap_dump.txt", k);

            dump_memory(f_args, args_start_ptr, ARGS_BASE_ADDR, (uint32_t)used_args_bytes);
            dump_memory(f_heap, heap_start_ptr, HEAP_BASE_ADDR, (uint32_t)used_heap_bytes);
        }

        int block_dim = 1024;
        int grid_dim = (no_of_nodes + block_dim - 1) / block_dim;

        run_kernel(kernel_BFS_1, grid_dim, block_dim, (void*)arg1);

        if (OUTPUT_MEM_DUMP) {
            char f_args[256], f_heap[256];
            snprintf(f_args, sizeof(f_args), "build/mem_dump/BFSMid%d_args_dump.txt", k);
            snprintf(f_heap, sizeof(f_heap), "build/mem_dump/BFSMid%d_heap_dump.txt", k);

            dump_memory(f_args, args_start_ptr, ARGS_BASE_ADDR, (uint32_t)used_args_bytes);
            dump_memory(f_heap, heap_start_ptr, HEAP_BASE_ADDR, (uint32_t)used_heap_bytes);
        }

        run_kernel(kernel_BFS_2, grid_dim, block_dim, (void*)arg2);

        if (file_thread) {
            fprintf(file_thread,
                "Pass %d | Grid: %d, Block: %d\n",
                k, grid_dim, block_dim);
        }

        if (OUTPUT_MEM_DUMP) {
            char f_args[256], f_heap[256];
            snprintf(f_args, sizeof(f_args), "build/mem_dump/BFSOutput%d_args_dump.txt", k);
            snprintf(f_heap, sizeof(f_heap), "build/mem_dump/BFSOutput%d_heap_dump.txt", k);

            dump_memory(f_args, args_start_ptr, ARGS_BASE_ADDR, (uint32_t)used_args_bytes);
            dump_memory(f_heap, heap_start_ptr, HEAP_BASE_ADDR, (uint32_t)used_heap_bytes);
        }

        stop = (*d_over > 0);
        k++;

        if (k > 10000) {
            printf("Error: BFS exceeded max iterations\n");
            break;
        }

    } while (stop);

    if(file_thread) fclose(file_thread);

    int* cpu_cost = (int*)malloc(sizeof(int) * no_of_nodes);
    run_cpu_bfs(no_of_nodes, h_graph_nodes_tmp, h_graph_edges_tmp, source, cpu_cost);

    int errors = 0;
    for (int i = 0; i < no_of_nodes; i++) {
        if (d_cost[i] != cpu_cost[i]) errors++;
    }

    printf("\nBFS Complete. Passes: %d, Errors: %d\n", k, errors);

    free(cpu_cost);
    free(h_graph_nodes_tmp);
    free(h_graph_edges_tmp);

    munmap((void*)args_start_ptr, args_size);
    munmap((void*)heap_start_ptr, heap_size);

    return 0;
}