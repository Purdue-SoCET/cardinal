#ifndef GEMM_H
#define GEMM_H

typedef struct {
    // Dimensions
    int M; // rows for matrix A 
    int N; // column for matrix B
    int K; // column for matrix A / row for matrix B

    // Matrices
    float* A; // Matrix A
    float* B; // Matrix B
    float* C; // Matrix C = A * B
} gemm_arg_t;

void kernel_gemm(void*);

#endif