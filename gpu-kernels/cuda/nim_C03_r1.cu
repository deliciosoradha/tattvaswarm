#include <cuda_runtime.h>

__global__ void reduce_sum_fixed_kernel(const float* d_in, float* d_out, int n) {
    extern __shared__ float s[];
    int tid = threadIdx.x;
    int bid = blockIdx.x;
    int blockSize = blockDim.x;

    float sum = 0.0f;
    int i = bid * blockSize + tid;
    while (i < n) {
        sum += d_in[i];
        i += gridDim.x * blockSize;
    }
    s[tid] = sum;
    __syncthreads();

    for (int stride = blockSize / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            s[tid] += s[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        atomicAdd(d_out, s[0]);
    }
}

void reduce_sum_fixed(const float* d_in, float* d_out, int n) {
    if (n <= 65536) {
        reduce_sum_fixed_kernel<<<1, 256, 256 * sizeof(float)>>>(d_in, d_out, n);
    } else {
        cudaMemset(d_out, 0, sizeof(float));
        int blockSize = 256;
        int gridSize = (n + blockSize - 1) / blockSize;
        reduce_sum_fixed_kernel<<<gridSize, blockSize, blockSize * sizeof(float)>>>(d_in, d_out, n);
    }
}
