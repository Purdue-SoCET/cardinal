#include "include/kernel.h"
#include "include/kmeans.h"

void kernel_kmeans_assign(void* arg) {
	kmeans_assign_arg_t* args = (kmeans_assign_arg_t*)arg;

	int idx = blockIdx * blockDim + threadIdx;
	if (idx >= args->n_points)
		return;

	int best_center = 0;
	float best_dist = 0;

	for (int d = 0; d < args->n_dims; d++) {
		float diff = args->points[idx * args->n_dims + d] - args->centers[d];
		best_dist += diff * diff;
	}

	for (int c = 1; c < args->k; c++) {
		float dist = 0;
		for (int d = 0; d < args->n_dims; d++) {
			float diff = args->points[idx * args->n_dims + d] - args->centers[c * args->n_dims + d];
			dist += diff * diff;
		}

		if (dist < best_dist) {
			best_dist = dist;
			best_center = c;
		}
	}

	args->labels[idx] = best_center;
}

void kernel_kmeans_accumulate(void* arg) {
	kmeans_accum_arg_t* args = (kmeans_accum_arg_t*)arg;

	int idx = blockIdx * blockDim + threadIdx;
	if (idx >= args->n_points)
		return;

	int c = args->labels[idx];
	args->center_counts[c] += 1;

	for (int d = 0; d < args->n_dims; d++) {
		args->center_sums[c * args->n_dims + d] += args->points[idx * args->n_dims + d];
	}
}

void kernel_kmeans_update(void* arg) {
	kmeans_update_arg_t* args = (kmeans_update_arg_t*)arg;

	int idx = blockIdx * blockDim + threadIdx;
	int total = args->k * args->n_dims;
	if (idx >= total)
		return;

	int c = idx / args->n_dims;
	//int d = idx % args->n_dims;
	int d = idx - (idx / args->n_dims) * args->n_dims;
	int count = args->center_counts[c];

	if (count > 0) {
		args->centers[idx] = args->center_sums[c * args->n_dims + d] / (float)count;
	}
}