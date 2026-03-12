#include "include/kernel.h"
#include "include/pathFinder.h"

void kernel_pathFinder(void* arg) {
	pathfinder_arg_t* args = (pathfinder_arg_t*)arg;

	int idx = blockIdx * blockDim + threadIdx;
	
    //boundry check
    if (idx >= args->width) 
        return;

    //column index
    int left = idx - 1;
    int right = idx + 1;

    //boundry check for left and right
    if (left < 0) left = 0;
    if (right >= args->width) right = args->width - 1;

    //min (left,mid,right)
    int min_val = args->input_row[idx];
    if (args->input_row[left] < min_val) {
        min_val = args->input_row[left];
    }
    if (args->input_row[right] < min_val) {
        min_val = args->input_row[right];
    }
    //add the current cell weight to the minimum value
    args->output_row[idx] = min_val + args->current_row_weight[idx];
    





}