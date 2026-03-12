#ifndef PATHFINDER_H
#define PATHFINDER_H

typedef struct {
    int* input_row; // pointer to the previous row results
    int* current_row_weight;  // pointer to the current row wall weights
    int* output_row;    // pointer to the current row computation results
    int  width; // width of the grid
} pathfinder_arg_t;

void kernel_pathFinder(void* arg);   

#endif





