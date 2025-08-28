# Performance Benchmarks

## Overview
This directory contains comprehensive performance benchmarking tools for the Chatbot System. These benchmarks validate all performance claims and provide reproducible metrics.

## Directory Structure
```
benchmarks/
├── load_tests/         # Load testing scripts (k6, Locust)
├── performance/        # Performance tracking and analysis
├── results/           # Benchmark results and reports
├── docker-compose.benchmark.yml  # Benchmark environment setup
└── run_benchmarks.py  # Orchestration script
```

## Benchmarking Methodology

### Test Environment
- **Hardware**: Minimum 4 CPU cores, 8GB RAM
- **Network**: Local network latency < 1ms
- **Database**: PostgreSQL 14+ with 100 connection pool
- **Cache**: Redis 6+ with persistence disabled
- **Load Generator**: Isolated from target system

### Load Patterns
1. **Gradual Ramp-up**: 0 to 100 users over 5 minutes
2. **Sustained Load**: 100 concurrent users for 10 minutes
3. **Spike Testing**: Sudden increase to 200 users
4. **Soak Testing**: 50 users for 1 hour

### Key Metrics
- **Latency**: P50, P95, P99 percentiles
- **Throughput**: Requests per second
- **Error Rate**: Percentage of failed requests
- **Cost**: API calls and estimated charges
- **Resource Usage**: CPU, Memory, Network I/O

## Running Benchmarks

### Prerequisites
```bash
# Install k6
brew install k6  # macOS
# or
sudo apt-get install k6  # Ubuntu

# Install Python dependencies
pip install locust redis prometheus-client matplotlib pandas

# Install Node.js dependencies for k6 extensions
npm install -g @grafana/k6
```

### Quick Start
```bash
# Run all benchmarks
python benchmarks/run_benchmarks.py

# Run specific test
k6 run benchmarks/load_tests/k6_websocket_test.js

# Run with custom parameters
k6 run -u 200 -d 30s benchmarks/load_tests/k6_api_test.js
```

### Docker-based Testing
```bash
# Start benchmark environment
docker-compose -f benchmarks/docker-compose.benchmark.yml up

# Run benchmarks in containers
docker-compose -f benchmarks/docker-compose.benchmark.yml run k6

# View results
open benchmarks/results/report.html
```

## Performance Targets

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| P95 Latency | <200ms | TBD | ⏳ |
| P99 Latency | <500ms | TBD | ⏳ |
| Concurrent Users | 100+ | TBD | ⏳ |
| Cost Reduction (w/ cache) | 30% | TBD | ⏳ |
| Uptime | 99.9% | TBD | ⏳ |

## Interpreting Results

### Latency Distribution
- **P50 (Median)**: Half of requests are faster than this
- **P95**: 95% of requests are faster than this
- **P99**: 99% of requests are faster than this

### Success Criteria
✅ **Pass**: Metric meets or exceeds target
⚠️ **Warning**: Within 10% of target
❌ **Fail**: More than 10% below target

### Cost Analysis
The cost analyzer tracks:
- Direct API costs (OpenAI, Anthropic, etc.)
- Cache hit ratio and savings
- Cost per conversation
- Monthly projection based on load

## Continuous Benchmarking

Benchmarks are automatically run:
- On every pull request
- Nightly against main branch
- Before production deployments

Results are:
- Stored in `benchmarks/results/` with timestamps
- Compared against baseline metrics
- Posted as PR comments
- Tracked in Grafana dashboards

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure services are running: `docker-compose ps`
   - Check port availability: `lsof -i :8000`

2. **High Latency**
   - Check database connection pool
   - Verify Redis is running
   - Monitor network conditions

3. **Memory Issues**
   - Increase Docker memory allocation
   - Reduce concurrent users in tests
   - Check for memory leaks

## Contributing

To add new benchmarks:
1. Create test script in appropriate directory
2. Update `run_benchmarks.py` to include new test
3. Document expected outcomes
4. Add to CI/CD pipeline
5. Submit PR with baseline results