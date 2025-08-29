# AI Chatbot System - Production-Ready Package

[![CI/CD Pipeline](https://github.com/cbratkovics/chatbot-ai-system/actions/workflows/ci.yml/badge.svg)](https://github.com/cbratkovics/chatbot-ai-system/actions)
[![codecov](https://codecov.io/gh/cbratkovics/chatbot-ai-system/branch/main/graph/badge.svg)](https://codecov.io/gh/cbratkovics/chatbot-ai-system)
[![PyPI version](https://badge.fury.io/py/chatbot-ai-system.svg)](https://badge.fury.io/py/chatbot-ai-system)
[![Docker](https://img.shields.io/docker/v/cbratkovics/chatbot-ai-system?label=docker)](https://ghcr.io/cbratkovics/chatbot-ai-system)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Enterprise-grade AI chatbot system with multi-provider support, production resilience patterns, and comprehensive observability.

## 🚀 Features

### Core Capabilities
- **Multi-Provider Support**: OpenAI, Anthropic, and custom providers with automatic failover
- **Circuit Breaker Pattern**: Intelligent provider failure handling with exponential backoff
- **Request Orchestration**: Load balancing, routing strategies, and provider health monitoring
- **Semantic Caching**: Hybrid caching with exact and semantic matching for cost optimization
- **WebSocket Support**: Real-time bidirectional communication with connection pooling
- **Multi-Tenancy**: Tenant isolation, per-tenant rate limiting, and usage tracking

### Production Features
- **Observability**: Structured logging, Prometheus metrics, OpenTelemetry tracing
- **Security**: JWT auth, API key management, PII redaction, OWASP headers
- **Resilience**: Circuit breakers, retry mechanisms, timeout management, idempotency
- **Performance**: P95 < 200ms latency, 99.5% availability SLO, automatic scaling
- **Cost Tracking**: Per-request cost calculation and tenant-based allocation

## 📦 Installation

### Via pip
```bash
pip install chatbot-ai-system
```

### Via Poetry
```bash
poetry add chatbot-ai-system
```

### Docker
```bash
docker pull ghcr.io/cbratkovics/chatbot-ai-system:latest
```

## 🎯 Quick Start

### CLI Usage
```bash
# Start the API server
chatbotai serve --host 0.0.0.0 --port 8000

# Interactive chat session
chatbotai chat --provider openai --model gpt-4

# Check system health
chatbotai doctor

# View metrics
chatbotai metrics --live
```

### Python SDK
```python
from chatbot_ai_system import ChatbotClient
from chatbot_ai_system.providers import ProviderConfig

# Initialize client
client = ChatbotClient(
    api_key="your-api-key",
    base_url="http://localhost:8000"
)

# Simple chat
response = await client.chat(
    message="Explain quantum computing",
    provider="openai",
    model="gpt-4"
)

# Streaming response
async for chunk in client.chat_stream(
    message="Write a story",
    provider="anthropic",
    model="claude-3-opus"
):
    print(chunk, end="")
```

### FastAPI Integration
```python
from chatbot_ai_system.server import create_app
from chatbot_ai_system.config import Settings

# Create FastAPI app with custom settings
settings = Settings(
    environment="production",
    redis_url="redis://localhost:6379",
    database_url="postgresql://user:pass@localhost/chatbot"
)

app = create_app(settings)

# Run with uvicorn
# uvicorn app:app --host 0.0.0.0 --port 8000
```

## 🏗️ Architecture

### System Overview
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│ Load Balancer│────▶│  API Gateway│
└─────────────┘     └──────────────┘     └─────────────┘
                                                │
                                    ┌───────────┴───────────┐
                                    │                       │
                            ┌───────▼────────┐     ┌───────▼────────┐
                            │  Orchestrator  │     │  WebSocket Mgr │
                            └───────┬────────┘     └────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
            ┌───────▼──────┐ ┌─────▼──────┐ ┌─────▼──────┐
            │Provider Pool │ │Cache Layer │ │Rate Limiter│
            └──────────────┘ └────────────┘ └────────────┘
```

### Provider Orchestration
- **Routing Strategies**: Round-robin, least-latency, least-cost, weighted, failover
- **Circuit Breaker**: Closed → Open → Half-Open state transitions
- **Health Checks**: Periodic provider health monitoring with automatic recovery
- **Cost Optimization**: Real-time cost tracking and budget enforcement

## 🔧 Configuration

### Environment Variables
```bash
# Core settings
ENVIRONMENT=production
LOG_LEVEL=INFO

# Provider API keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Database
DATABASE_URL=postgresql://user:pass@localhost/chatbot
REDIS_URL=redis://localhost:6379

# Security
JWT_SECRET_KEY=your-secret-key
API_KEY_HEADER=X-API-Key

# Performance
MAX_CONNECTIONS=1000
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60
```

### Docker Compose
```yaml
version: '3.8'

services:
  api:
    image: ghcr.io/cbratkovics/chatbot-ai-system:latest
    ports:
      - "8000:8000"
      - "9090:9090"  # Metrics
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql://chatbot:pass@postgres/chatbot
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: chatbot
      POSTGRES_USER: chatbot
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

## 🚢 Kubernetes Deployment

```bash
# Add Helm repository
helm repo add chatbot https://cbratkovics.github.io/chatbot-ai-system

# Install with custom values
helm install chatbot chatbot/chatbot-ai-system \
  --set image.tag=v1.0.0 \
  --set ingress.hosts[0].host=api.example.com \
  --set autoscaling.enabled=true \
  --set redis.enabled=true \
  --set postgresql.enabled=true
```

## 📊 Observability

### Metrics Endpoints
- `/metrics` - Prometheus metrics
- `/health` - Health check with provider status
- `/openapi.json` - OpenAPI specification

### Key Metrics
```prometheus
# Request rate
rate(chatbot_ai_system_requests_total[5m])

# P95 latency
histogram_quantile(0.95, rate(chatbot_ai_system_request_duration_seconds_bucket[5m]))

# Provider success rate
rate(chatbot_ai_system_model_requests_total{status="success"}[5m])

# Cost tracking
sum(rate(chatbot_ai_system_cost_usd_total[1h])) by (tenant_id)
```

### Structured Logging
```json
{
  "timestamp": "2024-01-15T10:23:45Z",
  "level": "INFO",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "tenant-123",
  "event": "request_completed",
  "duration_ms": 145,
  "provider": "openai",
  "model": "gpt-4",
  "tokens": 1250,
  "cost_usd": 0.0375
}
```

## 🔒 Security

### Authentication & Authorization
- JWT tokens with RS256 signing
- API key authentication per tenant
- Role-based access control (RBAC)
- OAuth2 integration support

### Data Protection
- Automatic PII redaction in logs
- TLS 1.3 enforcement
- Secrets management via environment variables
- Request/response encryption for sensitive data

### Security Headers
```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
```

## 🧪 Testing

```bash
# Run all tests
poetry run pytest

# Unit tests with coverage
poetry run pytest tests/unit/ --cov=chatbot_ai_system --cov-report=html

# Integration tests
poetry run pytest tests/integration/

# Load testing
poetry run locust -f tests/load/locustfile.py --host=http://localhost:8000

# Security scan
poetry run bandit -r src/
poetry run safety check
```

## 📈 Performance

### Benchmarks
- **Latency**: P50 < 50ms, P95 < 200ms, P99 < 500ms
- **Throughput**: 10,000+ requests/second (with caching)
- **Availability**: 99.5% SLO
- **Error Rate**: < 0.5%
- **Cache Hit Rate**: > 30% (semantic caching)

### Optimization Tips
1. Enable semantic caching for repeated queries
2. Use connection pooling for providers
3. Configure appropriate rate limits
4. Implement request batching for bulk operations
5. Use WebSocket for real-time streaming

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup
```bash
# Clone repository
git clone https://github.com/cbratkovics/chatbot-ai-system.git
cd chatbot-ai-system

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Setup pre-commit hooks
pre-commit install

# Run development server
poetry run chatbotai serve --reload
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- OpenAI for GPT models
- Anthropic for Claude models
- FastAPI for the web framework
- The open-source community

## 📞 Support

- Documentation: [https://docs.chatbot-ai-system.io](https://docs.chatbot-ai-system.io)
- Issues: [GitHub Issues](https://github.com/cbratkovics/chatbot-ai-system/issues)
- Discussions: [GitHub Discussions](https://github.com/cbratkovics/chatbot-ai-system/discussions)
- Email: cbratkovics@gmail.com

---

Built with ❤️ by Christopher Bratkovics