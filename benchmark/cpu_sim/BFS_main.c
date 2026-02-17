#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <assert.h>
#include <stdbool.h>
#include "include/kernel_run.h"

// Include the kernels we wrote previously
#include "../kernels/include/BFS.h" 

// Defines
#define BLOCK_SIZE 1024 

#define MIN_EDGES 20
#define MAX_INIT_EDGES (1024*1024)


/*Adopted from https://github.com/utcs-scea/altis/blob/master/data/bfs/graphgen.cpp*/
void initGraph(int *no_of_nodes, int *edge_list_size, int *source, Node **h_graph_nodes, int **h_graph_edges) {
    // Configuration Settings: Adjust before run
    bool quiet = false;
    int size_setting = 1024;      
    char* infile = "cpu_sim/data/BFS/bfs_524288"; // Graphes can be generate with cpu_sim/data/BFS/datagen.py
    
    FILE *fp = NULL;
    if(infile != NULL && infile[0] != '\0') {
        fp = fopen(infile, "r");
        if(!fp && !quiet) {
            printf("Error: Unable to read graph file %s.\n", infile);
        }
    }

    if(!quiet) {
        if(fp) {
            printf("Reading graph file\n");
        } else {
            printf("Generating graph with problem size %d\n", size_setting);
        }
    }

    if(fp) {
        int n = fscanf(fp, "%d", no_of_nodes);
        assert(n == 1);
    } else {
        int problemSizes[5] = {10, 50, 200, 400, 600};
        *no_of_nodes = problemSizes[size_setting - 1] * 1024 * 1024;
    }

    *h_graph_nodes = (Node*) malloc(sizeof(Node) * (*no_of_nodes));
    assert(*h_graph_nodes);
    
    int start;
    int edgeno;
    *edge_list_size = 0; 

    for (int i = 0; i < *no_of_nodes; i++) {
        if(fp) {
            int n = fscanf(fp, "%d %d", &start, &edgeno);
            assert(n == 2);
        } else {
            start = *edge_list_size;
            edgeno = rand() % (MAX_INIT_EDGES - MIN_EDGES + 1) + MIN_EDGES;
        }
        (*h_graph_nodes)[i].starting = start;
        (*h_graph_nodes)[i].no_of_edges = edgeno;
        *edge_list_size += edgeno;
    }

    if (fp) {
        int n = fscanf(fp, "%d", source);
        assert(n == 1);
    } else {
        *source = 0; 
    }

    if (fp) {
        int edges_in_file;
        int n = fscanf(fp, "%d", &edges_in_file);
        assert(n == 1);
    }

    *h_graph_edges = (int*) malloc(sizeof(int) * (*edge_list_size));
    assert(*h_graph_edges);
    
    for (int i = 0; i < *edge_list_size ; i++) {
        if (fp) {
            int id, cost;
            int n = fscanf(fp, "%d %d", &id, &cost);
            assert(n == 2);
            (*h_graph_edges)[i] = id;
        } else {
            (*h_graph_edges)[i] = rand() % (*no_of_nodes);
        }
    }

    if(fp) fclose(fp);
    
    if (!quiet) {
        printf("Graph size: %d nodes, %d edges\n", *no_of_nodes, *edge_list_size);
    }
}

void run_cpu_bfs(int no_of_nodes, Node *h_graph_nodes, int *h_graph_edges, int source, int *cpu_cost) {
    for (int i = 0; i < no_of_nodes; i++) {
        cpu_cost[i] = -1;
    }

    int *queue = (int*) malloc(sizeof(int) * no_of_nodes);
    int head = 0, tail = 0;

    cpu_cost[source] = 0;
    queue[tail++] = source;

    while (head < tail) {
        int u = queue[head++]; 
        
        int start_idx = h_graph_nodes[u].starting;
        int num_edges = h_graph_nodes[u].no_of_edges;

        for (int i = 0; i < num_edges; i++) {
            int v = h_graph_edges[start_idx + i];
            
            if (cpu_cost[v] == -1) {
                cpu_cost[v] = cpu_cost[u] + 1;
                queue[tail++] = v; 
            }
        }
    }

    free(queue);
}

int main() {
    int no_of_nodes;
    int edge_list_size;
    int source;
    Node* h_graph_nodes = NULL;
    int* h_graph_edges = NULL;

    // Read graph data 
    initGraph(&no_of_nodes, &edge_list_size, &source, &h_graph_nodes, &h_graph_edges);

    // Calculate memory requirements
    size_t nodes_sz   = no_of_nodes * sizeof(Node);
    size_t edges_sz   = edge_list_size * sizeof(int);
    size_t mask_sz    = no_of_nodes * sizeof(int);
    size_t cost_sz    = no_of_nodes * sizeof(int);
    size_t over_sz    = sizeof(int);

    size_t total_sz = nodes_sz + edges_sz + (3 * mask_sz) + cost_sz + over_sz;

    uint8_t* mem_space = malloc(total_sz);
    memset(mem_space, 0, total_sz);

    Node* d_graph_nodes   = (Node*) mem_space;
    int* d_graph_edges    = (int*) (mem_space + nodes_sz);
    int* d_graph_mask     = (int*) (mem_space + nodes_sz + edges_sz);
    int* d_updating_mask  = (int*) (mem_space + nodes_sz + edges_sz + mask_sz);
    int* d_graph_visited  = (int*) (mem_space + nodes_sz + edges_sz + 2 * mask_sz);
    int* d_cost           = (int*) (mem_space + nodes_sz + edges_sz + 3 * mask_sz);
    int* d_over           = (int*) (mem_space + nodes_sz + edges_sz + 3 * mask_sz + cost_sz);

    // Copy data from initGraph/host to GPU
    memcpy(d_graph_nodes, h_graph_nodes, nodes_sz);
    memcpy(d_graph_edges, h_graph_edges, edges_sz);

    // Initialize 
    for (int i = 0; i < no_of_nodes; i++) {
        d_cost[i] = -1; 
        d_graph_mask[i] = 0;
        d_updating_mask[i] = 0;
        d_graph_visited[i] = 0;
    }

    d_graph_mask[source] = 1;
    d_graph_visited[source] = 1;
    d_cost[source] = 0;

    int grid = 1;
    int block = no_of_nodes; 

    bfs_kernel1_arg_t arg1 = { d_graph_nodes, d_graph_edges, d_graph_mask, 
                               d_updating_mask, d_graph_visited, d_cost, no_of_nodes };

    bfs_kernel2_arg_t arg2 = { d_graph_mask, d_updating_mask, d_graph_visited, 
                               d_over, no_of_nodes };

    // BFS loop
    printf("Starting BFS from source node %d...\n", source);
    int k = 0;
    bool stop;

    do {
        *d_over = 0; 
        run_kernel(kernel_BFS_1, grid, block, (void*)&arg1);
        run_kernel(kernel_BFS_2, grid, block, (void*)&arg2);
        
        stop = (*d_over > 0);
        k++;
    } while (stop);

    // Results
    printf("BFS Completed in %d passes.\n", k);

    int reached = 0;
    for (int i = 0; i < no_of_nodes; i++) {
        if (d_graph_visited[i]) reached++;
    }
    printf("\nResults Summary:\n");
    printf("Total Nodes: %d\n", no_of_nodes);
    printf("Nodes Reached: %d (%.2f%%)\n", reached, (float)reached/no_of_nodes * 100);

    /*
    printf("\nFinal Costs (Distance from Source %d):\n", source);
    for (int i = 0; i < no_of_nodes; i++) {
        if (d_cost[i] == -1) {
            printf("Node %d: Unreachable\n", i);
        } else {
            printf("Node %d: %d hops\n", i, d_cost[i]);
        }
    }
    */

    printf("Starting CPU validation...\n");

    int* cpu_cost = (int*) malloc(sizeof(int) * no_of_nodes);
    run_cpu_bfs(no_of_nodes, h_graph_nodes, h_graph_edges, source, cpu_cost);

    int errors = 0;
    for (int i = 0; i < no_of_nodes; i++) {
        if (d_cost[i] != cpu_cost[i]) {
            errors++;
            if (errors < 5) { 
                printf("Mismatch at Node %d: GPU Cost %d, CPU Cost %d\n", i, d_cost[i], cpu_cost[i]);
            }
        }
    }

    if (errors == 0) {
        printf("VERIFICATION SUCCESS: Parallel results match CPU ground truth.\n");
    } else {
        printf("VERIFICATION FAILURE: %d mismatches found.\n", errors);
    }

    free(cpu_cost);
    free(h_graph_nodes);
    free(h_graph_edges);
    free(mem_space);

    return 0;
}