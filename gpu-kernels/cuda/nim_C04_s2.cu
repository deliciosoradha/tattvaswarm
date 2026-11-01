#include <cuda_runtime.h>
#include <cstdio>

__global__ void reduce_sum_kernel(const float* __restrict__ in, float* partial, int n) {
    extern __shared__ float sdata[];
    int tid = threadIdx.x;
    int i = blockIdx.x * blockDim.x + tid;
    int gridStride = gridDim.x * blockDim.x;

    float sum = 0.0f;
    while (i < n) {
        sum += in[i];
        i += gridStride;
    }
    sdata[tid] = sum;
    __syncthreads();

    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (tid < s) {
            sdata[tid] += sdata[tid + s];
        }
        __syncthreads();
    }

    if (tid == 0) {
        partial[blockIdx.x] = sdata[0];
    }
}

__global__ void final_reduce_kernel(const float* partial, float* out, int num_partials) {
    extern __shared__ float sdata[];
    int tid = threadIdx.x;
    int i = tid;
    float sum = 0.0f;
    while (i < num_partials) {
        sum += partial[i];
        i += blockDim.x;
    }
    sdata[tid] = sum;
    __syncthreads();

    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (tid < s) {
            sdata[tid] += sdata[tid + s];
        }
        __syncthreads();
    }

    if (tid == 0) {
        *out = sdata[0];
    }
}

void reduce_sum(const float* d_in, float* d_out, int n) {
    if (n == 0) {
        float h_zero = 0.0f;
        cudaMemcpy(d_out, &h_zero, sizeof(float), cudaMemcpyHostToDevice);
        return;
    }

    const int blockSize = 256;
    int numBlocks = (n + blockSize - 1) / blockSize;
    int maxBlocks = 65536;
    if (numBlocks > maxBlocks) numBlocks = maxBlocks;

    float* d_partial = nullptr;
    cudaMalloc(&d_partial, numBlocks * sizeof(float));

    size_t sharedMem = blockSize * sizeof(float);
    reduce_sum_kernel<<<numBlocks, blockSize, sharedMem>>>(d_in, d_partial, n);

    if (numBlocks == 1) {
        cudaMemcpy(d_out, d_partial, sizeof(float), cudaMemcpyDeviceToDevice);
    } else {
        int finalBlocks = 1;
        int finalBlockSize = 256;
        if (numBlocks > finalBlockSize) finalBlockSize = 512;
        final_reduce_kernel<<<finalBlocks, finalBlockSize, finalBlockSize * sizeof(float)>>>(d_partial, d_out, numBlocks);
    }

    cudaFree(d_partial);
}
