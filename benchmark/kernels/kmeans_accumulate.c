#include "include/kernel.h"
#include "include/kmeans.h"

#ifdef GPU_SIM
void main(void* arg)
#else
void kernel_kmeans_accumulate(void* arg) 
#endif		
{
	#ifdef GPU_SIM
	kmeans_accum_arg_t* args = (kmeans_accum_arg_t*)argPtr();
	int idx = blockIdx() * blockDim() + threadIdx();
	#else
	kmeans_accum_arg_t* args = (kmeans_accum_arg_t*)arg;
	int idx = blockIdx * blockDim + threadIdx;
	#endif
	
	if (idx >= args->n_points)
		return;

	int c = args->labels[idx];
	args->center_counts[c] += 1;

	for (int d = 0; d < args->n_dims; d++) {
		args->center_sums[c * args->n_dims + d] += args->points[idx * args->n_dims + d];
	}
}
