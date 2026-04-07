#include "include/kernel.h"
#include "include/kmeans.h"

#ifdef GPU_SIM
void main(void* arg)
#else
void kernel_kmeans_update(void* arg) 
#endif
{
	#ifdef GPU_SIM
	kmeans_update_arg_t* args = (kmeans_update_arg_t*)argPtr();
	int idx = blockIdx() * blockDim() + threadIdx();
	#else
	kmeans_update_arg_t* args = (kmeans_update_arg_t*)arg;
	int idx = blockIdx * blockDim + threadIdx;
	#endif
	
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