#include "include/kernel.h"
#include "include/gemm.h"

void kernel_gemm(void* arg) {

    gemm_arg_t* args = (gemm_arg_t*)arg;
    int idx = blockIdx * blockDim + threadIdx;
	int total = args->M * args->N;

	if (idx < total) {
		int row = idx / args->N;
		//int col = idx % args->N;
		int col = idx - (idx / args->N) * args->N;

		float sum = 0.0;
		for (int k = 0; k < args->K; ++k) {
			sum += args->A[row * args->K + k] * args->B[k * args->N + col];
		}
		args->C[row * args->N + col] = sum;
	}
}
