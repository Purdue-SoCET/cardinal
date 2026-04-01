#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#include "include/kernel_run.h"
#include "../kernels/include/pathFinder.h"

#define base_out 0x00002000

static void cpu_reference_row(const int* input_row, const int* weight_row, int* out, int width) {
	for (int idx = 0; idx < width; ++idx) {
		int left = idx > 0 ? idx - 1 : idx;
		int right = idx + 1 < width ? idx + 1 : idx;

		int min_val = input_row[idx];
		if (input_row[left] < min_val) {
			min_val = input_row[left];
		}
		if (input_row[right] < min_val) {
			min_val = input_row[right];
		}

		out[idx] = min_val + weight_row[idx];
	}
}

int main(void) {
	
	//width and height of the grid 
	const int width = 128;
	const int height = 128;

	// allocate weights for the whole grid and two buffers for rows.
	int* weights = (int*)malloc(sizeof(int) * width * height);
	int* row_a = (int*)malloc(sizeof(int) * width);
	int* row_b = (int*)malloc(sizeof(int) * width);
	int* row_ref = (int*)malloc(sizeof(int) * width);

	if (!weights || !row_a || !row_b || !row_ref) {
		printf("malloc failed\n");
		return 1;
	}

	// deterministic grid weights so results are repeatable.
	for (int r = 0; r < height; ++r) {
		for (int c = 0; c < width; ++c) {
			weights[r * width + c] = (r * 17 + c * 7) % 101; // weights between 0-100
		}
	}

	// initialize first row input as zeros so output becomes just the first row weights
	int* prev_out = row_a;
	int* curr_out = row_b;
	memset(prev_out, 0, sizeof(int) * width);

	pathfinder_arg_t args;
	args.width = width;
	int block_dim = 128;
	int grid_dim = (width + block_dim - 1) / block_dim;

	int mismatches = 0;

	for (int r = 0; r < height; ++r) {
		int* weight_row = &weights[r * width];
		args.input_row = prev_out;
		args.current_row_weight = weight_row;
		args.output_row = curr_out;

		// cpu-sim computation.
		run_kernel(kernel_pathFinder, grid_dim, block_dim, (void*)&args);

		// CPU reference for this row.
		cpu_reference_row(prev_out, weight_row, row_ref, width);

		// mismatch will be printed
		for (int i = 0; i < width; ++i) {
			if (curr_out[i] != row_ref[i]) {
				printf("Row %d idx %d mismatch: got %d expected %d\n", r, i, curr_out[i], row_ref[i]);
				mismatches++;
			}
		}

		// current output becomes next iteration's input.
		int* tmp = prev_out;
		prev_out = curr_out;
		curr_out = tmp;
	}

	if (mismatches == 0) {
		printf("pathFinder full-grid cpu sim pass (%dx%d)\n", height, width);
	}

	// dump the last row results for verification   
	for (int i = 0; i < width; ++i) {
		printf("0x%08x 0x%08x\n", (uint32_t)(base_out + 4 * i), (uint32_t)prev_out[i]);
	}

	free(weights);
	free(row_a);
	free(row_b);
	free(row_ref);

	return mismatches == 0 ? 0 : 1;
}
