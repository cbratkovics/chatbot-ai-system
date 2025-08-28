# Semantic Cache Benchmark Scenario

## Test Methodology

### Objective
Measure the cost reduction and performance improvement achieved through semantic caching of LLM responses.

### Test Parameters
- **Total Requests**: 500
- **Duplicate Query Rate**: 30% (150 repeated queries)
- **Cache Implementation**: Vector similarity search with 0.95 threshold
- **Embedding Model**: text-embedding-ada-002
- **Test Duration**: ~15 minutes per run

### Query Distribution
```
Unique queries: 350 (70%)
Repeated queries: 150 (30%)
Query types:
  - Technical questions: 40%
  - General knowledge: 30%
  - Code generation: 20%
  - Creative writing: 10%
```

### Metrics Collected
1. **Token Consumption**
   - Input tokens
   - Output tokens
   - Total tokens saved

2. **API Costs**
   - Baseline cost (no cache)
   - Optimized cost (with cache)
   - Cost reduction percentage

3. **Response Times**
   - Cache hit latency: ~50ms
   - Cache miss latency: ~2000ms
   - Average response time improvement

### Cost Calculation Formula
```
cost_per_1k_tokens = 0.002  # GPT-3.5-turbo pricing
total_cost = (input_tokens + output_tokens) / 1000 * cost_per_1k_tokens
savings = baseline_cost - optimized_cost
savings_percentage = (savings / baseline_cost) * 100
```

### Reproducibility Instructions

1. **Environment Setup**
   ```bash
   export OPENAI_API_KEY="your-key"
   export REDIS_URL="redis://localhost:6379"
   ```

2. **Run Baseline Test**
   ```bash
   python benchmarks/run_cache_benchmark.py --mode baseline
   ```

3. **Run Optimized Test**
   ```bash
   python benchmarks/run_cache_benchmark.py --mode optimized
   ```

4. **Generate Report**
   ```bash
   python benchmarks/run_cache_benchmark.py --report
   ```

### Expected Results
- Cache hit rate: ~30%
- Token savings: 28-32%
- Cost reduction: 28-32%
- Response time improvement: 60-70% for cached queries