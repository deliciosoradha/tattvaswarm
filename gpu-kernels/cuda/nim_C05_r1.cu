#include <cuda_runtime.h>

__global__ void transpose_tiled_kernel(const float* __restrict__ d_in,
                                       float* __restrict__ d_out,
                                       int rows, int cols) {
    const int TILE_DIM = 32;
    __shared__ float tile[TILE_DIM][TILE_DIM + 1];

    int x = blockIdx.x * TILE_DIM + threadIdx.x;
    int y = blockIdx.y * TILE_DIM + threadIdx.y;

    if (x < cols && y < rows) {
        tile[threadIdx.y][threadIdx.x] = d_in[y * cols + x];
    } else {
        tile[threadIdx.y][threadIdx.x] = 0.0f;
    }
    __syncthreads();

    int x_out = blockIdx.x * TILE_DIM + threadIdx.y;
    int y_out = blockIdx.y * TILE_DIM + threadIdx.x;

    if (x_out < rows && y_out < cols) {
        d_out[y_out * rows + x_out] = tile[threadIdx.x][threadIdx.y];
    }
}

void transpose_tiled(const float* d_in, float* d_out, int rows, int cols) {
    const int TILE_DIM = 32;
    dim3 block(TILE_DIM, TILE_DIM);
    dim3 grid((cols + TILE_DIM - 1) / TILE_DIM,
              (rows + TILE_DIM - 1) / TILE_DIM);
    transpose_tiled_kernel<<<grid, block>>>(d_in, d_out, rows, cols);
}
