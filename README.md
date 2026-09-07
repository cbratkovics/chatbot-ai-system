# Multi-Tenant AI Chat Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Node 20+](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![CI Pipeline](https://github.com/cbratkovics/chatbot-ai-system/actions/workflows/ci.yml/badge.svg)](https://github.com/cbratkovics/chatbot-ai-system/actions)
[![codecov](https://codecov.io/gh/cbratkovics/chatbot-ai-system/branch/main/graph/badge.svg)](https://codecov.io/gh/cbratkovics/chatbot-ai-system)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

## 🌐 Live Demo

**Try it now:** [chatbot-ai-system.vercel.app](https://chatbot-ai-system.vercel.app)

> Demo instance uses limited API quotas. For full features, deploy your own instance following the Quick Start below.

---

## Overview

Production-ready multi-tenant AI chatbot platform with intelligent LLM orchestration, WebSocket streaming, and reliable failover patterns. Built for performance and cost efficiency through semantic caching and provider redundancy.

**Built as a reusable template** - Easily customize for different use cases (customer support, code assistant, education, etc.) with pre-configured templates.

---

## What This Project Demonstrates

This project showcases production-grade LLMOps and AI engineering skills:

| Skill | Implementation | Location |
|-------|---------------|----------|
| **Multi-Provider Orchestration** | Unified interface for OpenAI, Anthropic, Llama, Gemini with intelligent routing | [`src/chatbot_ai_system/orchestration/`](src/chatbot_ai_system/orchestration/) |
| **Semantic Caching** | Redis-backed semantic similarity caching with configurable thresholds | [`src/chatbot_ai_system/cache/`](src/chatbot_ai_system/cache/) |
| **WebSocket Streaming** | Real-time token-by-token streaming over WebSocket | [`src/chatbot_ai_system/websocket/`](src/chatbot_ai_system/websocket/) |
| **Multi-Tenancy & Auth** | Tenant isolation, JWT authentication, rate limiting | [`src/chatbot_ai_system/middleware/`](src/chatbot_ai_system/middleware/) |
| **Observability** | Prometheus, Grafana, Jaeger distributed tracing | [`monitoring/`](monitoring/) |
| **Infrastructure as Code** | Kubernetes manifests, Docker Compose, CI/CD | [`infrastructure/`](infrastructure/), [`k8s/`](k8s/) |
| **Template Architecture** | Reusable configurations for multiple use cases | [`use-cases/`](use-cases/) |

**[View full architecture documentation →](docs/architecture/ARCHITECTURE.md)**

---

## Key Features

- **Multi-Provider Orchestration**: Intelligent routing between OpenAI, Anthropic, Llama, and Gemini with automatic failover
- **WebSocket Streaming**: Token-by-token response streaming over WebSocket connections
- **Cost Optimization**: Semantic caching to avoid repeat provider calls for similar prompts
- **Production Patterns**: Circuit breakers, rate limiting, health monitoring, and comprehensive observability
- **Multi-Tenancy Support**: Complete tenant isolation with usage tracking and horizontal scaling
- **Template-Ready**: Pre-configured use cases (customer support, code assistant) for rapid deployment

---

## Measured Behavior

This repository publishes one measured artifact: provider failover timing.

`tests/test_provider_failover.py` exercises the failover path against mock providers with
configurable failure modes (timeout, rate limit, server error), timing the orchestration logic with
`time.perf_counter()` across 10 runs per scenario. Results are written to
[`benchmarks/results/`](benchmarks/results/).

| Scenario | Runs | Average failover | P95 failover |
|----------|------|------------------|--------------|
| Timeout | 10 | 262.2 ms | 262.9 ms |
| Rate limit | 10 | 113.3 ms | 114.4 ms |
| Server error | 10 | 112.7 ms | 113.2 ms |

Source: [`failover_timing_latest.json`](benchmarks/results/failover_timing_latest.json)

**Scope of this measurement.** These numbers time the failover control flow (detection, timeout
handling, retry, provider switch) against mocked providers with a synthetic 50 ms base response
time. They are not provider-to-provider latencies in production, and they say nothing about
end-to-end response time under real API conditions.

**Reproduce it:** `pytest tests/test_provider_failover.py`

### Running your own benchmarks

The repository includes load-test harnesses that require a running instance and real API keys:

- `benchmarks/performance_test.py` - latency and throughput against a live server
- `benchmarks/load_tests/k6_api_test.js`, `k6_websocket_test.js` - k6 load tests
- `benchmarks/load_tests/locust_scenarios.py` - Locust scenarios
- `benchmarks/run_benchmarks.py` - orchestrates the above (requires k6, locust, docker)

No results from these harnesses are committed to this repository. Latency, throughput, cache hit
rate, and cost figures depend entirely on hardware, network, model selection, and workload, so any
numbers you need should come from your own run.

---

## 🚀 Quick Start

### Docker Compose (Recommended)

The fastest way to get started:

```bash
# 1. Clone and configure
git clone https://github.com/cbratkovics/chatbot-ai-system.git
cd chatbot-ai-system
cp .env.example .env
# Add your API keys to .env

# 2. Start all services
docker compose up -d

# 3. Access the application
# Frontend:  http://localhost:3000
# API Docs:  http://localhost:8000/docs
# Health:    http://localhost:8000/health
```

<details>
<summary><strong>Alternative: Local Development (Poetry + npm)</strong></summary>

For active development with hot reload:

```bash
# Backend
poetry install
cp .env.example .env
# Add your API keys to .env
poetry run uvicorn chatbot_ai_system.server.main:app --reload

# Frontend (new terminal)
cd frontend
npm ci
cp .env.example .env.local
# Configure API URLs in .env.local
npm run dev
```

**Access:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

</details>

<details>
<summary><strong>Template Mode: Use Case Quick Start</strong></summary>

Deploy a pre-configured chatbot for specific use cases:

```bash
# Example: Customer Support Template
cp use-cases/customer-support/.env.example .env
cp use-cases/customer-support/system-prompt.txt src/chatbot_ai_system/config/

# Customize branding in .env
# Then start with docker compose up -d
```

**Available Templates:**
- [`customer-support/`](use-cases/customer-support/) - Professional customer service assistant
- More templates coming soon!

See [`use-cases/`](use-cases/) for template documentation.

</details>

---

## Architecture

```mermaid
flowchart TB
    subgraph "Client Layer"
        UI[Next.js UI]
        WS[WebSocket Client]
        REST[REST Client]
    end

    subgraph "API Gateway"
        LB[Load Balancer]
        ASGI[FastAPI Server]
    end

    subgraph "Core Services"
        MW[Middleware Stack]
        ORCH[Provider Orchestrator]
        CACHE[Semantic Cache]
    end

    subgraph "Providers"
        OAI[OpenAI API]
        ANTH[Anthropic API]
        LLAMA[Meta Llama]
        GEM[Google Gemini]
    end

    subgraph "Storage"
        REDIS[(Redis Cache)]
        PG[(PostgreSQL)]
    end

    subgraph "Observability"
        PROM[Prometheus]
        GRAF[Grafana]
        TRACE[Jaeger]
    end

    UI --> LB
    WS --> LB
    REST --> LB
    LB --> ASGI
    ASGI --> MW
    MW --> ORCH
    MW --> CACHE
    ORCH --> OAI
    ORCH --> ANTH
    ORCH --> LLAMA
    ORCH --> GEM
    CACHE --> REDIS
    MW --> PG
    ASGI --> PROM
    PROM --> GRAF
    ASGI --> TRACE

    style UI fill:#e1f5fe
    style ASGI fill:#c8e6c9
    style ORCH fill:#ffccbc
    style REDIS fill:#ffecb3
    style PROM fill:#f8bbd0
```

---

## Configuration

### Environment Variables

```env
# Required API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Infrastructure
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://user:pass@localhost/chatbot

# Performance Tuning
RATE_LIMIT_REQUESTS=100
CACHE_TTL_SECONDS=3600
SEMANTIC_CACHE_THRESHOLD=0.85
REQUEST_TIMEOUT=30

# Feature Flags
ENABLE_STREAMING=true
ENABLE_FAILOVER=true
ENABLE_SEMANTIC_CACHE=true

# Frontend Configuration (in frontend/.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
NEXT_PUBLIC_APP_NAME="AI Chat System"
```

**Full configuration guide:** [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) (if exists)

---

## Production Deployment

This project is production-ready and can be deployed to Vercel + Render in under 30 minutes.

### Quick Deploy to Vercel + Render (Recommended)

**Infrastructure:**
- **Vercel**: Next.js frontend hosting (Free tier)
- **Render**: FastAPI backend + Redis cache ($14/month)
- **Total Cost**: $14/month + AI API usage

**Steps:**

1. **Deploy Backend to Render:**
   - Connect your GitHub repository to Render
   - Render auto-detects `render.yaml` configuration
   - Set environment variables (OPENAI_API_KEY, ANTHROPIC_API_KEY)
   - Deploy Redis instance ($7/month)

2. **Deploy Frontend to Vercel:**
   ```bash
   cd frontend
   vercel --prod
   ```
   - Set environment variables in Vercel dashboard:
     - `NEXT_PUBLIC_API_URL`: Your Render backend URL
     - `NEXT_PUBLIC_WS_URL`: Your Render WebSocket URL

3. **Update CORS:**
   - Add your Vercel domain to `CORS_ORIGINS` in Render dashboard

**Documentation:**
- Full deployment guide: [`docs/PRODUCTION_DEPLOYMENT.md`](docs/PRODUCTION_DEPLOYMENT.md)
- Production checklist: [`docs/DEPLOYMENT_CHECKLIST.md`](docs/DEPLOYMENT_CHECKLIST.md)

**Production URLs** (after deployment):
- Frontend: `https://your-app.vercel.app`
- Backend API: `https://your-backend.onrender.com`
- API Docs: `https://your-backend.onrender.com/docs`

<details>
<summary><strong>Alternative: Docker Deployment</strong></summary>

```bash
# Build production image
docker build -f docker/dockerfiles/Dockerfile.production -t chatbot-ai-system:latest .

# Run with production compose
docker compose -f docker-compose.prod.yml up -d
```

</details>

<details>
<summary><strong>Alternative: Kubernetes Deployment</strong></summary>

```bash
# Apply Kubernetes configurations
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

**Kubernetes documentation:** [`docs/kubernetes/README.md`](docs/kubernetes/README.md) (if exists)

</details>

### Scaling Considerations

- **Horizontal Scaling**: Stateless design supports multiple replicas
- **Database**: PostgreSQL with read replicas for high availability
- **Cache**: Redis Cluster for distributed caching
- **Load Balancing**: Nginx or cloud load balancer
- **Monitoring**: Prometheus + Grafana dashboards included

---

## Testing & Validation

```bash
# Run all quality checks
make lint          # Code linting with ruff
make type-check    # Type checking with mypy
make test          # Unit tests with pytest
make test-cov      # Tests with coverage report

# Individual test suites
poetry run pytest tests/unit -v           # Unit tests
poetry run pytest tests/integration -v    # Integration tests
poetry run pytest tests/e2e -v           # End-to-end tests

# Load testing
k6 run benchmarks/load_tests/k6_api_test.js
k6 run benchmarks/load_tests/k6_websocket_test.js

# Verify benchmark claims
python benchmarks/verify_metrics.py
```

**CI/CD:** All tests run automatically on pull requests via [GitHub Actions](.github/workflows/ci.yml)

---

## Monitoring & Observability

### Metrics Collection
- **Prometheus**: Application and system metrics
- **Grafana**: Real-time dashboards and alerts
- **Jaeger**: Distributed tracing for request flows

### Key Metrics Tracked
- Request latency (P50, P95, P99)
- Provider availability and failover events
- Cache hit rates and cost savings
- Token usage and rate limiting
- WebSocket connection metrics

**Access monitoring:**
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`
- Jaeger: `http://localhost:16686`

---

## Security Features

- **Authentication**: JWT-based with refresh tokens
- **Rate Limiting**: Token bucket algorithm per tenant
- **Input Validation**: Pydantic models with strict validation
- **Secrets Management**: Environment-based configuration
- **CORS Protection**: Configurable origin restrictions
- **Content Filtering**: Optional content moderation

**Security documentation:** [`docs/security/SECURITY.md`](docs/security/SECURITY.md)

---

## Technology Stack

### Backend
- **Framework**: FastAPI 0.104+ (async Python 3.12+)
- **LLM Providers**: OpenAI, Anthropic, Meta Llama, Google Gemini
- **Caching**: Redis with semantic similarity
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Message Queue**: Redis Streams

### Frontend
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **UI**: Tailwind CSS + shadcn/ui components
- **State Management**: React Context + Hooks
- **WebSocket**: Native WebSocket API

### Infrastructure
- **Containerization**: Docker, Docker Compose
- **Orchestration**: Kubernetes-ready
- **CI/CD**: GitHub Actions
- **Monitoring**: Prometheus, Grafana, Jaeger
- **Deployment**: Vercel (frontend) + Render (backend)

---

## Project Structure

```
├── src/chatbot_ai_system/    # Backend application
│   ├── server/               # FastAPI app and routes
│   ├── providers/            # LLM provider implementations
│   ├── orchestration/        # Routing and failover logic
│   ├── cache/                # Semantic caching system
│   ├── middleware/           # Auth, rate limiting, tracing
│   ├── websocket/            # WebSocket handlers
│   └── config/               # Configuration management
├── frontend/                 # Next.js frontend
│   ├── app/                  # Next.js 14 app directory
│   ├── components/           # React components
│   └── config/               # Frontend configuration
├── use-cases/                # Pre-configured templates
│   └── customer-support/     # Customer support template
├── benchmarks/               # Performance testing suite
│   ├── results/              # Benchmark results
│   └── load_tests/           # k6 load tests
├── tests/                    # Test suites
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   └── e2e/                  # End-to-end tests
├── docs/                     # Documentation
│   ├── architecture/         # Architecture docs
│   ├── security/             # Security docs
│   └── deployment/           # Deployment guides
├── docker/                   # Docker configurations
│   ├── dockerfiles/          # Dockerfile variants
│   └── compose/              # Docker Compose files
├── k8s/                      # Kubernetes manifests
├── infrastructure/           # IaC and deployment configs
└── monitoring/               # Monitoring configurations
```

---

## Contributing

We welcome contributions! Please read our [Contributing Guide](CONTRIBUTING.md) for details on our code of conduct, development process, and how to submit pull requests.

**Key areas for contribution:**
- New AI provider integrations
- Additional use-case templates
- Performance optimizations
- Documentation improvements
- Bug fixes and feature requests

**Community standards:**
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)

---

## Acknowledgments

Built with excellent open-source tools:

- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Next.js](https://nextjs.org/) - React framework for production
- [Redis](https://redis.io/) - In-memory data structure store
- [PostgreSQL](https://www.postgresql.org/) - Robust relational database
- [Prometheus](https://prometheus.io/) & [Grafana](https://grafana.com/) - Monitoring stack
- OpenAI & Anthropic for powerful LLM APIs

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Contact

**Christopher J. Bratkovics**
- **LinkedIn:** [linkedin.com/in/cbratkovics](https://linkedin.com/in/cbratkovics)
- **Portfolio:** [cbratkovics.dev](https://cbratkovics.dev)
- **GitHub:** [@cbratkovics](https://github.com/cbratkovics)

---

## Project Stats

- **Lines of Code**: ~15,000+
- **Test Coverage**: 85%+
- **Docker Images**: Backend, Frontend, Monitoring Stack
- **Supported Providers**: OpenAI, Anthropic, Meta Llama, Google Gemini
- **Concurrency**: Async request handling with WebSocket connection pooling
- **Deployment**: Docker Compose, Kubernetes manifests, and CI/CD workflows included

---

⭐ **Star this repo** if you find it useful!

Built with ❤️ for production AI systems
