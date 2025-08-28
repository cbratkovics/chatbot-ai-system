# Request Batching Benchmark Scenario

## Test Methodology

### Objective
Measure the API call reduction and efficiency gains achieved through intelligent request batching for embedding generation.

### Test Parameters
- **Total Embedding Requests**: 1,000
- **Batch Size**: 8 requests per batch
- **Embedding Model**: text-embedding-ada-002
- **Test Duration**: ~10 minutes per run
- **Concurrency**: 10 parallel workers

### Workload Characteristics
```
Request types:
  - Document chunks: 40% (400 requests)
  - User queries: 30% (300 requests)
  - System prompts: 20% (200 requests)
  - Metadata text: 10% (100 requests)

Average text length:
  - Short (< 100 tokens): 30%
  - Medium (100-500 tokens): 50%
  - Long (500-1000 tokens): 20%
```

### Test Scenarios

#### Scenario A: Sequential Processing (Baseline)
- Each embedding request sent individually
- No batching or request aggregation
- Immediate processing of each request

#### Scenario B: Batched Processing (Optimized)
- Requests aggregated into batches of 8
- 50ms wait window for batch formation
- Parallel batch processing

### Metrics Collected

1. **API Call Metrics**
   - Total API calls made
   - Requests per API call
   - API call reduction percentage

2. **Latency Distribution**
   - P50, P95, P99 latencies
   - Average request-to-completion time
   - Batch formation wait time

3. **Throughput Metrics**
   - Requests processed per second
   - Effective throughput improvement
   - Concurrent processing capacity

### Implementation Details

#### Batching Algorithm
```python
batch_size = 8
wait_window = 50  # milliseconds
timeout = 100  # max wait time

# Batch formation logic
if len(queue) >= batch_size or time_elapsed > wait_window:
    process_batch(queue[:batch_size])
```

### Reproducibility Instructions

1. **Environment Setup**
   ```bash
   export OPENAI_API_KEY="your-key"
   export BATCH_SIZE=8
   export WAIT_WINDOW_MS=50
   ```

2. **Run Sequential Baseline**
   ```bash
   python benchmarks/run_batching_benchmark.py --mode sequential
   ```

3. **Run Batched Processing**
   ```bash
   python benchmarks/run_batching_benchmark.py --mode batched
   ```

4. **Generate Comparison Report**
   ```bash
   python benchmarks/run_batching_benchmark.py --compare
   ```

### Expected Results
- API call reduction: 38-42%
- Throughput improvement: 3.5-4x
- Average latency increase: 25-50ms (acceptable trade-off)
- Cost efficiency: ~40% reduction in API overhead

### Performance Considerations
- Batch size optimization based on payload limits
- Dynamic batch sizing for variable workloads
- Priority queue for time-sensitive requests
- Fallback to individual requests on batch failures