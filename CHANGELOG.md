# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2024-01-XX

### Added
- Initial release of AI Chatbot System
- Multi-provider support (OpenAI, Anthropic, Mock)
- Async/streaming chat completions
- CLI tool with serve, demo, and bench commands
- FastAPI-based REST API
- Docker and docker-compose support
- Comprehensive test suite
- CI/CD with GitHub Actions
- Rate limiting and authentication middleware
- Health check and metrics endpoints
- Python SDK client
- Helm chart for Kubernetes deployment

### Security
- JWT-based authentication
- Rate limiting per client
- Environment-based configuration
- Non-root Docker container

[unreleased]: https://github.com/cbratkovics/chatbot-ai-system/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/cbratkovics/chatbot-ai-system/releases/tag/v0.1.0