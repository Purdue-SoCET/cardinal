#ifndef BFS_H
#define BFS_H

typedef struct {
    int starting;
    int no_of_edges;
} Node;

typedef struct {
    Node* g_graph_nodes;
    int* g_graph_edges;
    int* g_graph_mask;
    int* g_updating_graph_mask;
    int* g_graph_visited;
    int* g_cost;
    int no_of_nodes;
} bfs_kernel1_arg_t;

typedef struct {
    int* g_graph_mask;
    int* g_updating_graph_mask;
    int* g_graph_visited;
    int* g_over;
    int no_of_nodes;
} bfs_kernel2_arg_t;

void kernel_BFS_1(void*);
void kernel_BFS_2(void*);

#endif