# Multi-Tenant AI Chatbot Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](./tests)

## Overview

Enterprise-grade conversational AI platform delivering production-ready multi-tenant chatbot capabilities with sophisticated orchestration, real-time streaming, and comprehensive observability. Built for reliability, scalability, and cost efficiency.

## Performance Metrics

### Verified Benchmarks

| Metric | Target | Achieved | Evidence |
|--------|--------|----------|----------|
| **Availability** | 99.5% | 99.58% | [Load Test Results](benchmarks/results/rest_api_latest.json) - Error rate 0.42% under 50 VU load for 10m |
| **Latency P95** | <200ms | 185ms | [Performance Report](benchmarks/results/rest_api_latest.html) - Mixed workload, 50 concurrent users |
| **Cost Reduction** | 30% | 32.5% | [Cache Metrics](benchmarks/results/sample_metrics.json) - Semantic similarity threshold 0.85 |
| **WebSocket Capacity** | 100+ | 120 | [Concurrency Test](benchmarks/results/ws_latest.html) - Sustained for 10m, P95 < 150ms |
| **Failover Time** | <500ms | 423ms | [Failover Report](benchmarks/results/failover_timing_latest.json) - Isolated environment |

### Reproduction Steps

```bash
# Prerequisites: Docker, k6
git clone https://github.com/cbratkovics/ai-chatbot-system.git
cd ai-chatbot-system
git checkout b2746dc  # Tested commit

# Run complete benchmark suite
make demo            # Full demo: build, test, benchmark
make demo-up         # Start services only
make demo-test       # Run failover tests
make demo-benchmark  # Run load tests
make demo-clean      # Cleanup

# View results
open benchmarks/results/rest_api_latest.html
```

## Architecture

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│                   Load Balancer (HAProxy)                   │
│              SSL Termination | Rate Limiting                │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                    WebSocket Gateway                        │
│          Connection Management | Auth | Routing             │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                   FastAPI Service Layer                     │
├──────────────────────────────────────────────────────────────┤
│  Tenant Manager | Orchestrator | Cache | Stream Handler    │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                  Provider Adapter Layer                     │
├──────────────────────────────────────────────────────────────┤
│    OpenAI | Anthropic | Llama | Custom Provider Support    │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                     Data & Cache Layer                      │
├──────────────────────────────────────────────────────────────┤
│  PostgreSQL | Redis Cache | Vector Store | Message Queue   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                   Observability Stack                       │
├──────────────────────────────────────────────────────────────┤
│    Jaeger Tracing | Prometheus | Grafana | ELK Stack       │
└──────────────────────────────────────────────────────────────┘
```

### Technology Stack

**Backend**

- Python 3.11+, FastAPI, Pydantic V2, SQLAlchemy 2.0
- Async/await architecture with asyncio

**Frontend**  

- Next.js 14, TypeScript, Tailwind CSS
- Socket.io client for real-time communication

**Infrastructure**

- PostgreSQL 15+ (primary datastore)
- Redis 7+ (caching & session management)  
- Docker & Kubernetes ready
- Terraform modules for cloud deployment

**Observability**

- Distributed tracing (Jaeger)
- Metrics collection (Prometheus)
- Visualization (Grafana)
- Centralized logging (ELK)

## Core Features

### Multi-Tenant Architecture

- JWT-based authentication with RSA-256
- Row-level security and data isolation
- Per-tenant rate limiting with token bucket algorithm
- Usage tracking and billing integration
- Configurable model preferences per tenant

### AI Model Orchestration  

- Multi-provider support (OpenAI, Anthropic, Llama)
- Intelligent routing based on cost/performance
- Automatic failover with circuit breakers
- Model-specific retry strategies
- Load balancing across providers

### Performance Optimization

- Semantic caching with vector similarity
- Request batching and deduplication
- Connection pooling with multiplexing
- Streaming responses with backpressure control
- Predictive cache warming

### Enterprise Security

- End-to-end encryption (TLS 1.3)
- API key management with scopes
- OAuth 2.0 / OIDC integration
- Audit logging for compliance
- PII detection and redaction

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+

### Installation

```bash
# Clone repository
git clone https://github.com/cbratkovics/ai-chatbot-system.git
cd ai-chatbot-system

# Configure environment
cp config/environments/.env.example .env
vim .env  # Add your API keys and configuration

# Start services
docker-compose up -d

# Initialize database
python scripts/utils/manage.py migrate

# Access applications
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
# Grafana: http://localhost:3001
# Jaeger: http://localhost:16686
```

### Configuration

Essential environment variables:

```env
# AI Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
LLAMA_API_ENDPOINT=http://localhost:11434

# Database
DATABASE_URL=postgresql://user:pass@localhost/chatbot
REDIS_URL=redis://localhost:6379

# Security
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=RS256

# Performance
CACHE_TTL_SECONDS=3600
CONNECTION_POOL_SIZE=100
CIRCUIT_BREAKER_THRESHOLD=5
```

## API Reference

### Chat Completion

```http
POST /api/v1/chat/completions
Authorization: Bearer <token>
X-Tenant-ID: tenant_123

{
  "model": "gpt-4",
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "stream": true,
  "temperature": 0.7
}
```

### WebSocket Streaming

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat');
ws.send(JSON.stringify({
  type: 'auth',
  token: 'your-jwt-token'
}));
```

### Tenant Management

```http
POST /api/v1/tenants
{
  "name": "Enterprise Client",
  "tier": "premium",
  "rate_limits": {
    "requests_per_minute": 1000,
    "tokens_per_minute": 100000
  }
}
```

## Testing

### Test Execution

```bash
# Unit tests
pytest tests/unit/ -v --cov=app

# Integration tests  
pytest tests/integration/ --docker-compose

# Load testing
k6 run tests/load/scenario.js --vus=100

# E2E testing
pytest tests/e2e/ --browser=chrome
```

### Performance Benchmarks

```bash
# Run benchmark suite
python benchmarks/run_benchmarks.py

# Specific scenarios
python benchmarks/cache_benchmark.py  # Cache performance
python benchmarks/failover_test.py    # Provider failover
python benchmarks/ws_concurrency.py   # WebSocket limits
```

## Deployment

### Kubernetes

```bash
# Deploy with Helm
helm install chatbot ./helm/chatbot \
  --namespace production \
  --values values.production.yaml

# Enable autoscaling
kubectl autoscale deployment chatbot-api \
  --min=3 --max=20 --cpu-percent=70
```

### Docker Compose

```bash
# Production deployment
docker-compose -f docker-compose.prod.yml up -d

# With monitoring
docker-compose -f docker-compose.yml \
  -f docker-compose.monitoring.yml up -d
```

## Monitoring

### Available Dashboards

**System Health**

- Service uptime and availability
- Resource utilization (CPU, memory, disk)
- Network throughput and latency

**Application Metrics**  

- Request rate and latency percentiles
- Error rates by endpoint
- Cache hit ratios
- Model usage distribution

**Business Intelligence**

- Tenant usage patterns
- Cost analysis per model
- Token consumption trends
- Feature adoption metrics

### Alerting Rules

```yaml
- alert: HighLatency
  expr: http_request_duration_p95 > 0.2
  for: 5m
  
- alert: LowCacheHitRate
  expr: cache_hit_rate < 0.3
  for: 10m
  
- alert: ProviderFailure
  expr: provider_error_rate > 0.1
  for: 1m
```

## Project Structure

```
ai-chatbot-system/
├── api/                     # Backend application
│   ├── core/               # Core business logic
│   ├── providers/          # AI provider adapters
│   ├── infrastructure/     # Infrastructure code
│   ├── models/             # Database models
│   └── ws_handlers/        # WebSocket handlers
├── frontend/               # Next.js application
├── config/                 # Configuration files
│   ├── docker/            # Docker configurations
│   ├── environments/      # Environment configs
│   └── requirements/      # Python dependencies
├── tests/                  # Test suites
├── benchmarks/            # Performance tests
├── monitoring/            # Observability configs
├── scripts/               # Utility scripts
└── docs/                  # Documentation
```

## Development

### Code Standards

```bash
# Format code
make format

# Lint check
make lint

# Type checking
mypy api/ --strict

# Security scan
bandit -r api/
```

### Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/enhancement`)
3. Write tests for changes
4. Ensure CI passes
5. Submit pull request

## Security

### Reporting Vulnerabilities

Please report security vulnerabilities to <security@example.com>. Do not create public issues for security problems.

### Security Features

- Automatic dependency scanning
- Container image vulnerability scanning  
- SAST/DAST in CI pipeline
- Regular penetration testing
- SOC2 Type II compliance ready

## License

MIT License - see [LICENSE](LICENSE) file

## Support

- Documentation: [/docs](docs/)
- Issues: [GitHub Issues](https://github.com/cbratkovics/ai-chatbot-system/issues)
- Discussions: [GitHub Discussions](https://github.com/cbratkovics/ai-chatbot-system/discussions)

## Acknowledgments

- FastAPI for high-performance async framework
- OpenAI and Anthropic for AI models
- Contributors and maintainers
