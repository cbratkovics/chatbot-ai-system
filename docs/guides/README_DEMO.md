# AI Chatbot System - Demo Branch

## 5-Minute Quick Start

### Prerequisites
- Docker & Docker Compose
- OpenAI or Anthropic API Key

### Setup

1. **Clone and checkout demo:**
```bash
git clone https://github.com/cbratkovics/chatbot-ai-system.git
cd chatbot-ai-system
git checkout demo
```

2. **Run automated setup:**
```bash
make up   # docker compose up -d with the root docker-compose.yml
```

3. **Add your API keys to `.env`:**
```bash
OPENAI_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here  # Optional
```

4. **Access the application:**
- Chat Interface: http://localhost:3000
- API Documentation: http://localhost:8000/docs

## Features Included

- Multi-model support (OpenAI GPT-4, Anthropic Claude)
- Real-time streaming responses (Server-Sent Events)
- Semantic caching for cost optimization
- Rate limiting (demo guardrails, 10 req/min per IP)
- Professional React UI

## Simplified for Demo

This branch removes enterprise complexity:
- No Kubernetes configs
- No complex monitoring
- Simplified Docker setup
- Basic configuration
- Quick deployment focus

For full enterprise features, check the `main` branch.

## Stop Demo

```bash
docker compose down
```
