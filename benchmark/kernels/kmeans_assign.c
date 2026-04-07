#include "include/kernel.h"
#include "include/kmeans.h"

#ifdef GPU_SIM
void main(void* arg)
#else
void kernel_kmeans_assign(void* arg) 
#endif
{
	#ifdef GPU_SIM
	kmeans_assign_arg_t* args = (kmeans_assign_arg_t*)argPtr();
	int idx = blockIdx() * blockDim() + threadIdx();
	#else
	kmeans_assign_arg_t* args = (kmeans_assign_arg_t*)arg;
	int idx = blockIdx * blockDim + threadIdx;
	#endif
	
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
