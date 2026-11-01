#include <cuda_runtime.h>
#include <device_launch_parameters.h>

__global__ void reduce_sum_kernel(const float* __restrict__ input, float* partial_sums, int n) {
    extern __shared__ float sdata[];
    int tid = threadIdx.x;
    int i = blockIdx.x * blockDim.x + tid;
    int grid_stride = gridDim.x * blockDim.x;

    float my_sum = 0.0f;
    while (i < n) {
        my_sum += input[i];
        i += grid_stride;
    }

    sdata[tid] = my_sum;
    __syncthreads();

    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (tid < s) {
            sdata[tid] += sdata[tid + s];
        }
        __syncthreads();
    }

    if (tid == 0) {
        partial_sums[blockIdx.x] = sdata[0];
    }
}

__global__ void final_reduce_kernel(const float* partial_sums, float* output, int num_partials) {
    extern __shared__ float sdata[];
    int tid = threadIdx.x;

    float my_sum = 0.0f;
    for (int i = tid; i < num_partials; i += blockDim.x) {
        my_sum += partial_sums[i];
    }

    sdata[tid] = my_sum;
    __syncthreads();

    for (int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (tid < s) {
            sdata[tid] += sdata[tid + s];
        }
        __syncthreads();
    }

    if (tid == 0) {
        *output = sdata[0];
    }
}

void reduce_sum(const float* d_in, float* d_out, int n) {
    if (n == 0) {
        cudaMemset(d_out, 0, sizeof(float));
        return;
    }

    const int block_size = 256;
    int num_blocks = (n + block_size - 1) / block_size;
    if (num_blocks > 65536) num_blocks = 65536;

    float* d_partials = nullptr;
    cudaMalloc(&d_partials, num_blocks * sizeof(float));

    size_t shared_mem = block_size * sizeof(float);
    reduce_sum_kernel<<<num_blocks, block_size, shared_mem>>>(d_in, d_partials, n);

    if (num_blocks == 1) {
        cudaMemcpy(d_out, d_partials, sizeof(float), cudaMemcpyDeviceToDevice);
    } else {
        int final_blocks = 1;
        int final_block_size = 256;
        if (num_blocks > final_block_size) {
            final_blocks = (num_blocks + final_block_size - 1) / final_block_size;
            if (final_blocks > 65536) final_blocks = 65536;
        }
        final_reduce_kernel<<<final_blocks, final_block_size, final_block_size * sizeof(float)>>>(d_partials, d_out, num_blocks);
    }

    cudaFree(d_partials);
}
