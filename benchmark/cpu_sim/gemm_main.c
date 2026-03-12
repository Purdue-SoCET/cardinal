#include <stdio.h>
#include <stdlib.h>
#include "include/kernel_run.h"
#include "../kernels/include/gemm.h"

static void generate_float_matrix(float* m, int rows, int cols) {
	for (int i = 0; i < rows; ++i) {
		for (int j = 0; j < cols; ++j) {
			m[i * cols + j] = (float)((i * cols + j) % 97) / 97.0f; //random number between 0 and 1
		}
	}
}

static void cpu_reference(const float* A, const float* B, float* C, int M, int N, int K) {
	for (int i = 0; i < M; ++i) {
		for (int j = 0; j < N; ++j) {
			float sum = 0.0f;
			for (int k = 0; k < K; ++k) {
				sum += A[i * K + k] * B[k * N + j];
			}
			C[i * N + j] = sum;
		}
	}
}

void save_binary(float* data, int count, const char* filename) {
    FILE* fp = fopen(filename, "wb");
    
    if (fp == NULL) {
        printf("error: failed to write binary");
        return;
    }

    int written = fwrite(data, sizeof(float), count, fp);

    if (written != count) {
        printf("Error, write counting wrong");
    }
    fclose(fp);
}

void save_text(float* data, int M, int N, const char* filename) {
    FILE* fp = fopen(filename, "w"); 
     if (fp == NULL) {
        printf("error: failed to write text");
        return;
    }

    for (int i = 0; i < M; ++i) {
        for (int j = 0; j < N; ++j) {
            fprintf(fp, "%.4f ", data[i * N + j]);//print with 4 decimal places
        }
        fprintf(fp, "\n");
    }
    fclose(fp);
}

int main(void) {
	const int M = 512;
	const int N = 512;
	const int K = 512;

    //allocating space  
	float* A = (float*)malloc(sizeof(float) * M * K);
	float* B = (float*)malloc(sizeof(float) * K * N);
	float* C = (float*)malloc(sizeof(float) * M * N);
	float* C_ref = (float*)malloc(sizeof(float) * M * N);

	if (!A || !B || !C || !C_ref) {
		printf("malloc failed\n");
		return 1;
	}

	generate_float_matrix(A, M, K);
	generate_float_matrix(B, K, N);

	gemm_arg_t args = {0};
	args.M = M;
	args.N = N;
	args.K = K;
	args.A = A;
	args.B = B;
	args.C = C;

    //kernel 
	int total = M * N;
	int block_dim = 128;
	int grid_dim = (total + block_dim - 1) / block_dim;

    run_kernel(kernel_gemm, grid_dim, block_dim, (void*)&args);

    //reference
	cpu_reference(A, B, C_ref, M, N, K);

    //compare 
    for (int i = 0; i < total; ++i) {
		if(C[i] !=C_ref[i])
        {
            printf("gemm cpu sim failed");
			break;
        }
	}
	
	printf("gemm cpu sim pass");

    //write to text file
    save_text(A, M, K, "matrix_a.txt"); 
    save_text(B, K, N, "matrix_b.txt");
    save_text(C_ref, M, N, "matrix_c_output.txt");

    //write to binary file
    save_binary(A, M * K, "matrix_a.bin");
    save_binary(B, K * N, "matrix_b.bin");
    save_binary(C_ref, M * N, "matrix_c_output.bin");

    //free  
	free(A);
	free(B);
	free(C);
	free(C_ref);

	return 0;
}
