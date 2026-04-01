#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "include/kernel_run.h"
#include "../kernels/include/kmeans.h"

static void init_clustered_points(float* points, int n_points, int n_dims, int k) {
    for (int i = 0; i < n_points; i++) {
        int cluster = i % k;
        for (int d = 0; d < n_dims; d++) {
            // Build clusters with noise.
            int cluster_distance = 20; // distance between cluster centers. small distance for more iterations to converge
            float base = (float)(cluster * cluster_distance + d * 3);
            float noise = (float)((i * 17 + d * 13) % 10) * 0.1f;
            points[i * n_dims + d] = base + noise;
        }
    }
}

static void init_random_points(float* points, int n_points, int n_dims,
                               float min_value, float max_value) {
    float range = max_value - min_value;
    for (int i = 0; i < n_points; i++) {
        for (int d = 0; d < n_dims; d++) {
            // determined random value in [0, 1]
            float unit = (float)((i * 17 + d * 13 + i * d * 7) % 1000) / 999.0f;
            points[i * n_dims + d] = min_value + unit * range;
        }
    }
}

static void init_centers_from_points(const float* points, float* centers, int n_dims, int k) {
    for (int c = 0; c < k; c++) {
        for (int d = 0; d < n_dims; d++) {
            centers[c * n_dims + d] = points[c * n_dims + d];
        }
    }
}

static float center_delta(const float* a, const float* b, int count) {
    float accum = 0.0f;
    for (int i = 0; i < count; i++) {
        float diff = a[i] - b[i];
        accum += diff * diff;
    }
    return sqrtf(accum);
}

int main(void) {
    const int n_points = 8192;
    const int n_dims = 8;
    const int k = 4;
    const int max_iters = 100;
    const int block_dim = 128;

    float* points = (float*)malloc(sizeof(float) * n_points * n_dims);
    float* centers = (float*)malloc(sizeof(float) * k * n_dims);
    float* centers_prev = (float*)malloc(sizeof(float) * k * n_dims);
    float* center_sums = (float*)malloc(sizeof(float) * k * n_dims);
    int* center_counts = (int*)malloc(sizeof(int) * k);
    int* labels = (int*)malloc(sizeof(int) * n_points);

    if (!points || !centers || !centers_prev || !center_sums || !center_counts || !labels) {
        printf("malloc failed\n");
        free(points);
        free(centers);
        free(centers_prev);
        free(center_sums);
        free(center_counts);
        free(labels);
        return 1;
    }

    //initilized cluster points
    //init_clustered_points(points, n_points, n_dims, k);

    //random points 
    init_random_points(points, n_points, n_dims, 0.0f, 5.0f);
    // Seed centers from the first k points to keep initialization deterministic.
    init_centers_from_points(points, centers, n_dims, k);

    kmeans_assign_arg_t assign_args = {0};
    assign_args.n_points = n_points;
    assign_args.n_dims = n_dims;
    assign_args.k = k;
    assign_args.points = points;
    assign_args.centers = centers;
    assign_args.labels = labels;

    kmeans_accum_arg_t accum_args = {0};
    accum_args.n_points = n_points;
    accum_args.n_dims = n_dims;
    accum_args.k = k;
    accum_args.points = points;
    accum_args.labels = labels;
    accum_args.center_sums = center_sums;
    accum_args.center_counts = center_counts;

    kmeans_update_arg_t update_args = {0};
    update_args.n_dims = n_dims;
    update_args.k = k;
    update_args.centers = centers;
    update_args.center_sums = center_sums;
    update_args.center_counts = center_counts;

    int assign_grid = (n_points + block_dim - 1) / block_dim;
    int update_total = k * n_dims;
    int update_grid = (update_total + block_dim - 1) / block_dim;

    for (int iter = 0; iter < max_iters; iter++) {
        // Keep previous centers for convergence measurement
        memcpy(centers_prev, centers, sizeof(float) * k * n_dims);
        memset(center_sums, 0, sizeof(float) * k * n_dims);
        memset(center_counts, 0, sizeof(int) * k);

        // k-means pipeline: assign -> accumulate -> update.
        run_kernel(kernel_kmeans_assign, assign_grid, block_dim, (void*)&assign_args);
        run_kernel(kernel_kmeans_accumulate, assign_grid, block_dim, (void*)&accum_args);
        run_kernel(kernel_kmeans_update, update_grid, block_dim, (void*)&update_args);

        // Converge when center movement (L2 norm) is small enough.
        float delta = center_delta(centers, centers_prev, k * n_dims);
        printf("iter %d, delta = %.6f\n", iter, delta);
        if (delta < 1e-4f) {
            printf("converged at iter %d\n", iter);
            break;
        }
    }

    printf("final centers:\n");
    for (int c = 0; c < k; c++) {
        printf("center %d: ", c);
        for (int d = 0; d < n_dims; d++) {
            printf("%.4f ", centers[c * n_dims + d]);
        }
        printf("\n");
    }

    free(points);
    free(centers);
    free(centers_prev);
    free(center_sums);
    free(center_counts);
    free(labels);

    return 0;
}
