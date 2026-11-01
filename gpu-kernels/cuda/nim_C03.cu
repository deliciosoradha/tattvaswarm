#include <cuda_runtime.h>

__global__ void reduce_sum_fixed_kernel(const float* d_in, float* d_out, int n) {
    extern __shared__ float s[];
    int tid = threadIdx.x;
    int i = blockIdx.x * blockDim.x + tid;
    s[tid] = (i < n) ? d_in[i] : 0.0f;
    __syncthreads();
    for (int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
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
