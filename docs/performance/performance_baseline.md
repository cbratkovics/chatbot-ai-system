# Performance Baseline Documentation

## Test Environment Specifications

### Hardware Configuration
- **Machine**: MacBook Pro M1 (2021) / GitHub Actions Ubuntu Runner
- **CPU**: Apple M1 8-core / Intel Xeon 2-core
- **Memory**: 16GB / 7GB
- **Storage**: 512GB SSD / 14GB SSD
- **Network**: 1Gbps local / Cloud datacenter

### Docker Resource Limits
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8192M
        reservations:
          cpus: '2.0'
          memory: 4096M
```

### Environment Variables
```bash
# Core Configuration
API_URL=http://localhost:8000
ENVIRONMENT=development
LOG_LEVEL=INFO

# Provider Configuration
OPENAI_API_KEY=${OPENAI_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
GOOGLE_API_KEY=${GOOGLE_API_KEY}

# Cache Configuration
REDIS_URL=redis://localhost:6379
CACHE_TTL_SECONDS=3600
SEMANTIC_THRESHOLD=0.85

# Performance Tuning
WORKER_PROCESSES=4
WORKER_CONNECTIONS=1000
REQUEST_TIMEOUT_SECONDS=30
KEEPALIVE_TIMEOUT=65

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=100

# Database
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
DATABASE_POOL_TIMEOUT=30
```

## Test Commands

### REST API Load Test
```bash
# Basic test
k6 run benchmarks/load/rest_api_load.js

# With custom parameters
k6 run -e API_URL=http://localhost:8000 \
       -e API_KEY=test-key-123 \
       benchmarks/load/rest_api_load.js

# Specific scenario
k6 run --scenario smoke benchmarks/load/rest_api_load.js
k6 run --scenario load benchmarks/load/rest_api_load.js
k6 run --scenario stress benchmarks/load/rest_api_load.js

# With output to InfluxDB
k6 run --out influxdb=http://localhost:8086/k6 \
       benchmarks/load/rest_api_load.js
```

### WebSocket Concurrency Test
```bash
# Basic test
k6 run benchmarks/load/websocket_concurrency.js

# With parameters
k6 run -e WS_URL=ws://localhost:8000/ws \
       -e API_KEY=test-key-123 \
       benchmarks/load/websocket_concurrency.js

# Long-running soak test
k6 run --scenario soak benchmarks/load/websocket_concurrency.js
```

### Provider Failover Test
```bash
# Run with pytest
pytest tests/test_provider_failover.py -v

# Generate timing report
pytest tests/test_provider_failover.py::test_generate_failover_report -v

# With coverage
pytest tests/test_provider_failover.py --cov=backend --cov-report=html

# Run specific test
pytest tests/test_provider_failover.py::TestProviderFailover::test_failover_under_load -v
```

## Dataset and Prompt Mix

### Prompt Distribution
- **Short prompts (30%)**: 10-50 tokens
  - "What is machine learning?"
  - "Explain neural networks"
  
- **Medium prompts (50%)**: 50-150 tokens
  - Technical explanations
  - Code generation requests
  
- **Long prompts (20%)**: 150-500 tokens
  - Complex analysis requests
  - Multi-step instructions

### Test Data Characteristics
- **Languages**: English (primary), code snippets (Python, JavaScript)
- **Domains**: Technical documentation, conversational, analytical
- **Token distribution**:
  - Average input: 85 tokens
  - Average output: 150 tokens
  - Max tokens: 500

## Performance Targets

### Latency Targets
| Metric | Production | Development | Degraded |
|--------|------------|-------------|----------|
| P50 | < 100ms | < 150ms | < 300ms |
| P95 | < 200ms | < 300ms | < 500ms |
| P99 | < 300ms | < 500ms | < 1000ms |

### Throughput Targets
| Metric | Target | Minimum | Maximum |
|--------|--------|---------|---------|
| RPS (single instance) | 200 | 100 | 500 |
| Concurrent users | 100 | 50 | 200 |
| WebSocket connections | 100 | 50 | 150 |

### Reliability Targets
| Metric | SLO | SLA | Measurement |
|--------|-----|-----|-------------|
| Availability | 99.5% | 99.0% | Monthly |
| Error rate | < 0.5% | < 1% | Rolling 5m |
| Cache hit rate | > 30% | > 20% | Daily average |

## Grafana Dashboard Configuration

### Import Dashboard
```json
{
  "dashboard": {
    "title": "AI Gateway Performance",
    "panels": [
      {
        "title": "Request Latency",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, http_request_duration_seconds_bucket)"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~'5..'}[5m])"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "targets": [
          {
            "expr": "rate(cache_hits_total[5m]) / rate(cache_requests_total[5m])"
          }
        ]
      },
      {
        "title": "WebSocket Connections",
        "targets": [
          {
            "expr": "websocket_connections_active"
          }
        ]
      }
    ]
  }
}
```

### Key Metrics to Monitor
1. **Golden Signals**
   - Latency: P50, P95, P99
   - Traffic: Requests per second
   - Errors: Error rate, error types
   - Saturation: CPU, memory, connections

2. **Business Metrics**
   - Cost per request
   - Token consumption
   - Cache efficiency
   - Provider distribution

3. **Infrastructure Metrics**
   - Container resource usage
   - Database connection pool
   - Redis memory usage
   - Network I/O

## Interpretation Guidelines

### Good Performance Indicators
✅ **P95 latency < 200ms** - Meeting SLO
✅ **Error rate < 0.5%** - Within error budget
✅ **Cache hit rate > 30%** - Cost optimization working
✅ **100+ concurrent WebSockets** - Scalability achieved

### Warning Signs
⚠️ **P95 latency 200-300ms** - Monitor closely
⚠️ **Error rate 0.5-1%** - Error budget depleting
⚠️ **Cache hit rate 20-30%** - Below target
⚠️ **Memory usage > 80%** - Resource pressure

### Critical Issues
❌ **P95 latency > 300ms** - SLO violation
❌ **Error rate > 1%** - SLA breach
❌ **Cache hit rate < 20%** - Cost inefficiency
❌ **OOM kills** - Resource exhaustion

## Troubleshooting Guide

### High Latency
1. Check provider response times
2. Verify cache is operational
3. Review database query performance
4. Check for resource throttling

### High Error Rate
1. Check provider API status
2. Review rate limiting configuration
3. Verify authentication tokens
4. Check circuit breaker state

### Low Cache Hit Rate
1. Review semantic threshold settings
2. Analyze prompt diversity
3. Check Redis memory usage
4. Verify embedding service

### WebSocket Issues
1. Check connection limits
2. Review keepalive settings
3. Verify load balancer configuration
4. Check for memory leaks

## Continuous Improvement

### Weekly Reviews
- Analyze P95 latency trends
- Review error budget consumption
- Optimize cache hit patterns
- Update provider weights

### Monthly Optimization
- Baseline performance tests
- Capacity planning review
- Cost analysis
- SLO/SLA assessment

### Quarterly Planning
- Architecture review
- Scaling strategy update
- Disaster recovery testing
- Performance target revision