# AI Chatbot Demo - Release v1.0.0

## Overview

This is the **demo release** of the AI Chatbot System - a streamlined, production-ready version that can be deployed in under 5 minutes.

## Highlights

- **One-Command Setup** - Just run `./setup_demo.sh`
- **Multi-LLM Support** - OpenAI & Anthropic providers
- **Intelligent Caching** - Redis-powered responses
- **Real-time Streaming** - WebSocket support
- **Professional UI** - Modern React/Next.js interface

## Quick Start

### 1. Download & Extract

```bash
# Download the release
wget https://github.com/cbratkovics/ai-chatbot-system/archive/refs/tags/v1.0.0-demo.tar.gz
tar -xzf v1.0.0-demo.tar.gz
cd ai-chatbot-system-1.0.0-demo
```

### 2. Configure

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and add your API keys
```

### 3. Deploy

```bash
./setup_demo.sh
```

### 4. Access

- **Chat UI:** <http://localhost:3000>
- **API Docs:** <http://localhost:8000/docs>

## What's Included

### Core Features

- Multiple LLM provider support
- Semantic caching system
- WebSocket streaming
- Rate limiting (30 req/min)
- Health monitoring
- Interactive API documentation

### Files & Structure

- **backend/** - FastAPI application
- **frontend/** - Next.js UI
- **docker-compose.demo.yml** - Service orchestration
- **setup_demo.sh** - Automated setup
- **README.demo.md** - Complete documentation

## System Requirements

- Docker & Docker Compose
- 4GB RAM minimum
- 2GB disk space
- macOS, Linux, or Windows with WSL2

## API Keys Required

At least one of:

- OpenAI API Key ([Get one here](https://platform.openai.com/api-keys))
- Anthropic API Key ([Get one here](https://console.anthropic.com/account/keys))

## Performance

- **Setup Time:** < 5 minutes
- **Memory Usage:** ~500MB
- **Docker Build:** ~2 minutes
- **Dependencies:** 35 packages

## Known Issues

- Redis connection errors are handled gracefully
- WebSocket requires modern browser
- Rate limiting is per-IP in demo mode

## Changelog

### Added

- Streamlined demo configuration
- One-command setup script
- Comprehensive documentation
- Health check endpoints
- Automatic API key validation

### Changed

- Reduced dependencies by 65%
- Simplified Docker configuration
- Optimized build process
- Improved error messages

### Removed

- Complex enterprise features
- Kubernetes configurations
- Extensive test suites
- FinOps dashboards

## Contributing

Contributions welcome! Please submit PRs to the `demo` branch.

## License

MIT License - See LICENSE file for details

## Credits

- OpenAI for GPT models
- Anthropic for Claude models
- FastAPI framework
- Next.js framework

## Support

- Create an issue for bugs
- Check README.demo.md for troubleshooting
- Join our Discord community

---

**Download Now:** [v1.0.0-demo.tar.gz](https://github.com/cbratkovics/ai-chatbot-system/releases/download/v1.0.0-demo/v1.0.0-demo.tar.gz)

**Docker Images:** Available on Docker Hub

**Documentation:** [README.demo.md](README.demo.md)
