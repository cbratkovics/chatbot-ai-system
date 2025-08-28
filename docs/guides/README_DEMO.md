# AI Chatbot System - Demo Branch

## 5-Minute Quick Start

### Prerequisites
- Docker & Docker Compose
- OpenAI or Anthropic API Key

### Setup

1. **Clone and checkout demo:**
```bash
git clone https://github.com/cbratkovics/ai-chatbot-system.git
cd ai-chatbot-system
git checkout demo
```

2. **Run automated setup:**
```bash
./scripts/setup/setup_demo.sh
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
- Real-time streaming responses  
- Semantic caching for cost optimization  
- WebSocket connections  
- Rate limiting (30 req/min)  
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
docker-compose -f config/docker/compose/docker-compose.demo.yml down
```