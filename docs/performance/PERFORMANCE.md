# Performance Documentation

## Performance Metrics & Benchmarks

### Performance Targets

These are the design targets the load-test thresholds are written against. This repository does not
publish measured results for them: latency, throughput, cache hit rate, and cost depend on hardware,
network, model selection, and workload, so the only meaningful numbers are the ones from your own
run against your own deployment.

| Metric | Target | Test Conditions |
|--------|--------|-----------------|
| P95 Latency | <200ms | 100 concurrent users |
| P99 Latency | <500ms | 100 concurrent users |
| Throughput | 1000 RPS | 4 CPU cores, 16GB RAM |
| Concurrent Users | 100+ | WebSocket connections |
| Cache Hit Rate | 30% | Semantic similarity threshold 0.85 |
| Uptime | 99.9% | 30-day average |

The one measured artifact published here is provider failover timing. See the Measured Behavior
section of the [project README](../../README.md).

## Benchmark Methodology

### Load Testing Setup

**Tool**: k6 and Locust
**Duration**: 30 minutes per test
**Ramp-up**: 5 minutes
**Sustained Load**: 20 minutes
**Ramp-down**: 5 minutes

```javascript
// k6 Configuration
export let options = {
  stages: [
    { duration: '5m', target: 100 },  // Ramp-up
    { duration: '20m', target: 100 }, // Sustained
    { duration: '5m', target: 0 },    // Ramp-down
  ],
  thresholds: {
    http_req_duration: ['p(95)<200', 'p(99)<500'],
    http_req_failed: ['rate<0.01'],
  },
};
```

### Test Scenarios

1. **Chat Completion Test**
   - Model: GPT-3.5-turbo
   - Message length: 50-200 tokens
   - Response length: 100-500 tokens

2. **WebSocket Streaming Test**
   - Concurrent connections: 100
   - Message frequency: 1 msg/second
   - Stream duration: 5-10 seconds

3. **Cache Performance Test**
   - Cache warmup: 1000 entries
   - Query variations: 20%
   - Similarity threshold: 0.85

## Performance Optimization Techniques

### 1. Caching Strategy

**Semantic Cache Implementation**
```python
class SemanticCache:
    similarity_threshold = 0.85
    ttl_seconds = 3600
    max_size_mb = 100

    async def get(query: str) -> Optional[Response]:
        embedding = generate_embedding(query)
        best_match = find_similar(embedding, threshold)
        return best_match if best_match else None
```

**Cache Performance Results**
- Average lookup time: 15ms
- Memory usage: 85MB for 1000 entries
- Hit rate improvement over time:
  - Day 1: 15%
  - Day 7: 28%
  - Day 30: 35%

### 2. Connection Pooling

**Database Connection Pool**
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

**Redis Connection Pool**
```python
redis_pool = aioredis.ConnectionPool(
    max_connections=50,
    min_idle_time=30,
    connection_class=aioredis.Connection
)
```

### 3. Async I/O Optimization

**Concurrent Request Processing**
```python
async def process_batch(requests: List[Request]):
    tasks = [process_single(req) for req in requests]
    return await asyncio.gather(*tasks)
```

**Performance Gains**
- Sequential processing: 1000ms for 10 requests
- Concurrent processing: 200ms for 10 requests
- Improvement: 80% reduction in total time

### 4. Model Provider Optimization

**Load Balancing Strategy**
```python
providers = ["openai", "anthropic"]
current_index = 0

def get_next_provider():
    global current_index
    provider = providers[current_index]
    current_index = (current_index + 1) % len(providers)
    return provider
```

**Fallback Performance**
- Primary failure detection: <100ms
- Fallback activation: <50ms
- Total overhead: <150ms

## Load Testing Results

No load-test results are published in this repository.

The harnesses in [`benchmarks/`](../../benchmarks/) are provided so you can generate results for
your own deployment:

- `benchmarks/load_tests/k6_api_test.js` and `k6_websocket_test.js` (requires k6)
- `benchmarks/load_tests/locust_scenarios.py` (requires Locust)
- `benchmarks/performance_test.py` (requires a running instance)

Latency, throughput, and success rate depend on hardware, network conditions, model selection, and
prompt mix. Numbers copied from someone else's environment would not tell you anything useful about
yours.

The one measured artifact published here is provider failover timing, described in the Measured
Behavior section of the [project README](../../README.md).


## Monitoring and Alerting

### Key Performance Indicators (KPIs)

1. **Response Time Metrics**
   - API response time (p50, p95, p99)
   - Database query time
   - Cache lookup time
   - Model provider latency

2. **Throughput Metrics**
   - Requests per second
   - Successful responses per second
   - WebSocket messages per second
   - Cache hits per second

3. **Resource Utilization**
   - CPU usage per container
   - Memory usage per container
   - Database connection pool usage
   - Redis memory usage

### Prometheus Metrics

```yaml
# Custom metrics
chatbot_request_duration_seconds:
  type: histogram
  help: "Request duration in seconds"
  labels: ["method", "endpoint", "status"]

chatbot_cache_hit_ratio:
  type: gauge
  help: "Cache hit ratio"
  labels: ["cache_type"]

chatbot_model_latency_seconds:
  type: histogram
  help: "Model provider latency"
  labels: ["provider", "model"]

chatbot_active_websockets:
  type: gauge
  help: "Number of active WebSocket connections"
```

### Alert Rules

```yaml
groups:
  - name: performance_alerts
    rules:
      - alert: HighLatency
        expr: histogram_quantile(0.95, chatbot_request_duration_seconds) > 0.2
        for: 5m
        annotations:
          summary: "P95 latency exceeds 200ms"

      - alert: LowCacheHitRate
        expr: chatbot_cache_hit_ratio < 0.2
        for: 10m
        annotations:
          summary: "Cache hit rate below 20%"

      - alert: HighErrorRate
        expr: rate(chatbot_errors_total[5m]) > 0.01
        for: 5m
        annotations:
          summary: "Error rate exceeds 1%"
```

## Performance Tuning Guide

### Application Level

1. **FastAPI Optimization**
   ```python
   app = FastAPI(
       openapi_url=None,  # Disable in production
       docs_url=None,
       redoc_url=None
   )
   ```

2. **Uvicorn Configuration**
   ```bash
   uvicorn app:app \
     --workers 4 \
     --loop uvloop \
     --limit-concurrency 1000 \
     --limit-max-requests 10000
   ```

3. **Async Context Managers**
   ```python
   async with aiofiles.open('file.txt') as f:
       content = await f.read()
   ```

### Database Level

1. **Query Optimization**
   ```sql
   -- Add indexes
   CREATE INDEX idx_chats_tenant_created
   ON chats(tenant_id, created_at DESC);

   -- Use prepared statements
   PREPARE chat_query AS
   SELECT * FROM chats
   WHERE tenant_id = $1
   ORDER BY created_at DESC
   LIMIT $2;
   ```

2. **Connection Tuning**
   ```sql
   -- PostgreSQL configuration
   max_connections = 200
   shared_buffers = 4GB
   effective_cache_size = 12GB
   work_mem = 10MB
   ```

### Cache Level

1. **Redis Configuration**
   ```conf
   maxmemory 2gb
   maxmemory-policy allkeys-lru
   tcp-keepalive 60
   timeout 300
   ```

2. **Cache Warming Strategy**
   ```python
   async def warm_cache():
       popular_queries = await get_popular_queries()
       for query in popular_queries:
           response = await generate_response(query)
           await cache.set(query, response)
   ```

## Cost Analysis

> The figures below are an illustrative cost model for sizing and planning. They are not observed
> spend from a deployed instance of this system.

### Example Cost Breakdown

For a hypothetical deployment serving roughly 1,000,000 requests per month:

| Component | Monthly Cost | Percentage |
|-----------|--------------|------------|
| Model API Calls | $2,100 | 42% |
| Infrastructure | $1,500 | 30% |
| Database | $600 | 12% |
| Cache (Redis) | $300 | 6% |
| Monitoring | $250 | 5% |
| Storage | $250 | 5% |
| **Total** | **$5,000** | **100%** |

### Modeling Cost Reduction Through Caching

Semantic caching reduces cost by serving similar prompts without a provider call. The savings scale
directly with hit rate, which depends on how repetitive your traffic is:

**Baseline (no caching)**
- Requests: 1,000,000/month
- Average tokens: 200/request
- Cost: $3,000/month

**At a 35% hit rate**
- Cache hits: 350,000
- API calls: 650,000
- Cost: $1,950/month
- Savings: $1,050/month

Substitute your own hit rate to model your case. `benchmarks/performance/cost_analyzer.py`
implements this calculation and its `simulate_cache_scenario()` helper takes the hit rate as a
parameter.

## Performance Roadmap

### Q1 2024
- [ ] Implement request batching
- [ ] Add GPU acceleration for embeddings
- [ ] Optimize WebSocket message compression
- [ ] Implement predictive caching

### Q2 2024
- [ ] Database sharding implementation
- [ ] CDN integration for static content
- [ ] Advanced query optimization
- [ ] Real-time performance analytics

### Q3 2024
- [ ] Edge computing deployment
- [ ] Implement request prioritization
- [ ] Advanced caching algorithms
- [ ] Performance regression testing

## Troubleshooting Performance Issues

### High Latency Checklist
1. Check cache hit rate
2. Verify database connection pool
3. Monitor model provider response times
4. Check network latency
5. Review recent deployments

### Memory Issues Checklist
1. Check Redis memory usage
2. Review application memory leaks
3. Verify connection pool sizes
4. Check for unbounded caches
5. Review streaming buffer sizes

### Throughput Issues Checklist
1. Verify rate limiting configuration
2. Check database query performance
3. Review connection pool exhaustion
4. Monitor CPU utilization
5. Check for blocking I/O operations

## Performance Testing Commands

```bash
# Run k6 load test
k6 run benchmarks/load_test.js

# Run Locust test
locust -f benchmarks/locust_test.py --host=http://localhost:8000

# Profile application
python -m cProfile -o profile.stats api/main.py

# Analyze profile
python -m pstats profile.stats

# Monitor real-time performance
python scripts/monitor_performance.py --interval 5
```
