#ifndef KMEANS_H
#define KMEANS_H

typedef struct {
	int n_points; //number of points
	int n_dims; //number of dimensions for each point
	int k; //number of clusters
	const float* points; //array of points 
	const float* centers; //array of cluster centers
	int* labels; //cluster label for each point
} kmeans_assign_arg_t;

typedef struct {
	int n_points;
	int n_dims;
	int k;
	const float* points;
	const int* labels;
	float* center_sums; //sum of points for each cluster
	int* center_counts; //number of points assigned to each cluster
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
