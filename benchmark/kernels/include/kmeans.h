#ifndef KMEANS_H
#define KMEANS_H

typedef struct {
	int n_points;
	int n_dims;
	int k;
	const float* points;
	const float* centers;
	int* labels;
} kmeans_assign_arg_t;

typedef struct {
	int n_points;
	int n_dims;
	int k;
	const float* points;
	const int* labels;
	float* center_sums;
	int* center_counts;
} kmeans_accum_arg_t;

typedef struct {
	int n_dims;
	int k;
	float* centers;
	const float* center_sums;
	const int* center_counts;
} kmeans_update_arg_t;

void kernel_kmeans_assign(void* arg);
void kernel_kmeans_accumulate(void* arg);
void kernel_kmeans_update(void* arg);

#endif
