# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Live demo outage: OpenAI `insufficient_quota` was retried as a rate limit and surfaced as "Request failed"; it is now a non-retryable 402 with a structured error envelope, and the request fails over to Groq (`docs/DIAGNOSIS.md`, ADR 0003).
- Unhandled 500s now carry CORS headers (error-envelope middleware inside CORS).
- Unreachable `REDIS_URL` no longer blocks startup for ~75 s; it falls back to an in-process cache within 2 s (ADR 0001).
- OpenAI streaming mixin crashed on the SDK's trailing usage chunk and let raw SDK errors escape the failover chain.
- 79 failing integration tests triaged: fixtures repaired, drift fixed, 19 tests for APIs that never existed deleted with git evidence (`docs/TEST_TRIAGE.md`).

### Added
- Semantic (paraphrase) cache on the demo path: exact key first, then OpenAI embeddings in a bounded in-process index scoped by tenant, model, temperature and prior conversation; degrades to exact-match with `cache.semantic = "unavailable"` (ADR 0007, supersedes the exact-match-only part of ADR 0001).
- Telemetry additions on `done` / JSON: `cost_avoided_usd`, `cache.match`, real `cache.similarity`, `cache.semantic`, `cache.matched_key`, `cache.threshold`, `cache.age_seconds`, `embedding {model, tokens, latency_ms, cost_usd}`; a hit now preserves the original `usage.source` instead of relabelling an estimate as provider-reported.
- `GET /api/v1/evals/latest` serving the committed eval artifact with ETag / 304 / 404 envelope.
- `/metrics` is real Prometheus exposition: `http_requests_total`, `http_request_duration_seconds`, `cache_hits_total`, `cache_misses_total`, `chat_cache_lookups_total{result}` (TEST_TRIAGE escalation 4 resolved). Per-worker, reset on deploy; documented in `docs/API.md`.
- Provider failover chain with per-request attempt log; Groq via the OpenAI-compatible endpoint (no new SDK).
- SSE streaming on `POST /api/v1/chat/completions` (ADR 0005) and a per-message telemetry chip in the UI.
- Demo guardrails: per-IP limits, token caps, daily budget (ADR 0004); env-gated "simulate provider failure" toggle.
- `scripts/bench_demo.py`, `docs/DEMO_SCRIPT.md`, five ADRs, `docs/audits/`.
- `make help` with `install`, `dev`, `check`, `up`, `bench`, and friends.

### Changed
- Default model `gpt-4o-mini`; legacy ids (`gpt-3.5-turbo`) map forward.
- Vector search is off by default and never imports Pinecone unless `ENABLE_VECTOR_SEARCH=true` (ADR 0002).
- `render.yaml` targets the free tier: one worker, no Redis service.
- README metrics restricted to committed artifacts; measured coverage (31%) replaces the "85%+" claim.
- Repository layout: `config/`, `deploy/`, `demo/`, `examples/`, `use-cases/`, `nginx/`, `redis/`, `monitoring/` and 20+ legacy scripts removed or merged under `docker/` and `infrastructure/` (`docs/audits/REPO_AUDIT.md`).
- Poetry metadata moved to PEP 621 `[project]`; `mypy.ini` folded into `pyproject.toml`.

## [1.1.0] - 2025-01-10

### Added
- **Pinecone Vector Store Integration**: Production-ready vector database support for semantic search
  - Complete `PineconeVectorStore` implementation with automatic index management
  - `EmbeddingGenerator` for OpenAI text-embedding-ada-002 model
  - Batch upsert operations with configurable batch sizes
  - Filtered queries with metadata support
  - Namespace support for multi-tenancy
  - Comprehensive unit tests (29 new tests, 100% coverage on embeddings module)
- **Production Readiness Tests**: Comprehensive integration test suite (`test_production_readiness.py`)
  - 32 tests covering all critical system components
  - Health checks, API endpoints, configuration validation
  - Docker and CI/CD validation
  - Security checks for hardcoded secrets
  - Performance benchmarks for cache operations
- **Performance Benchmarks**: Pinecone-specific benchmarks (`test_pinecone_performance.py`)
  - Embedding generation speed tests
  - Batch upsert performance
  - Query performance with different top_k values
  - Concurrent query benchmarks
  - End-to-end workflow testing

### Changed
- **Docker Configuration**: Consolidated duplicate Dockerfiles
  - Removed 4 duplicate Dockerfiles from root directory
  - Standardized on `docker/dockerfiles/` as canonical location
  - Updated all docker-compose files to use correct Dockerfile paths
  - Added Pinecone environment variables to all docker-compose configurations
- **Settings**: Enhanced configuration with Pinecone support
  - Added 8 new Pinecone-specific settings fields
  - Added `is_vector_search_enabled` property for runtime checks
  - Updated `.env.example` with complete Pinecone configuration
- **CI/CD Pipeline**: Updated GitHub Actions workflow
  - Added Pinecone environment variables to test jobs
  - Ensured tests run without real Pinecone connectivity
  - All 166 tests passing (up from 137)
- **Package Dependencies**: Fixed critical Pinecone package issue
  - Migrated from deprecated `pinecone-client` to `pinecone` package
  - Updated to `pinecone ^7.3.0`

### Fixed
- Health check endpoint no longer requires Redis/API providers in test mode
- Test infrastructure properly mocks all external dependencies
- All type checking passes with MyPy
- Code formatting consistent with Ruff

### Documentation
- Added comprehensive production readiness tests
- Created performance benchmark suite
- Updated package description to include vector search capabilities

## [1.0.0] - 2025-01-03

### Added
- Multi-provider AI support (OpenAI, Anthropic)
- WebSocket streaming for real-time responses
- Semantic caching with Redis backend
- Token-bucket rate limiting per tenant
- Comprehensive benchmarking suite
- Circuit breaker for fault tolerance
- Load balancing across provider instances
- Automatic failover between providers
- Prometheus metrics and observability
- Docker Compose setup for local development
- Next.js frontend for demonstration
- CLI tool for system management
- Poetry-based dependency management
- Pre-commit hooks for code quality
- GitHub Actions CI/CD pipeline

### Fixed
- Repository structure consolidation
- Import path consistency across modules
- Removal of duplicate namespaces and files
- Standardization on `chatbot_ai_system.server.main:app` entry point
- CI/CD pipeline with real tests
- Package configuration for src layout
- Version consistency across all files

### Changed
- Migrated from scattered modules to organized src/ structure
- Updated all imports to use canonical paths
- Improved .env.example with comprehensive configuration
- Enhanced Dockerfile with Poetry-based builds
- Modernized CI workflow with proper caching

### Security
- Added JWT authentication support
- Implemented per-tenant isolation
- Added rate limiting for API endpoints
- Secure Redis connection handling

## [0.1.0] - 2024-08-29

### Added
- Initial project structure
- Basic FastAPI application
- OpenAI integration
- Simple WebSocket support
- Basic rate limiting
- Docker support

---

## Upcoming Features

### [1.2.0] - Planned
- Google Vertex AI integration
- Advanced prompt templates
- RAG (Retrieval Augmented Generation) with Pinecone
- Enhanced monitoring dashboard
- Kubernetes deployment manifests
- Horizontal scaling improvements
- LangChain integration
- Advanced caching strategies
- A/B testing framework
- Cost optimization algorithms
- GraphQL API endpoint

## Migration Guide

### From 0.1.0 to 1.0.0

1. **Update imports**: Change from `chatbot_system_api` to `chatbot_ai_system`
2. **Update entry point**: Use `chatbot_ai_system.server.main:app`
3. **Environment variables**: Review and update `.env` based on `.env.example`
4. **Dependencies**: Run `poetry install` to get latest dependencies
5. **Database**: If using PostgreSQL, run migration scripts in `scripts/migrations/`
