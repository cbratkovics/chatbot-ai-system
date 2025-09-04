#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}AI Chatbot System - One-Click Demo${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker from https://docs.docker.com/get-docker/"
    exit 1
fi

# Check docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: docker-compose is not installed${NC}"
    echo "Please install docker-compose from https://docs.docker.com/compose/install/"
    exit 1
fi

# Check Poetry (optional, for benchmarks)
if command -v poetry &> /dev/null; then
    POETRY_AVAILABLE=true
    echo -e "${GREEN}✓ Poetry found${NC}"
else
    POETRY_AVAILABLE=false
    echo -e "${YELLOW}⚠ Poetry not found (benchmarks will run in Docker)${NC}"
fi

# Setup environment if needed
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo -e "${YELLOW}Creating .env from .env.example...${NC}"
        cp .env.example .env
        echo -e "${RED}WARNING: Please add your API keys to .env file:${NC}"
        echo "  - OPENAI_API_KEY"
        echo "  - ANTHROPIC_API_KEY"
        echo ""
        echo "Get free API keys from:"
        echo "  - OpenAI: https://platform.openai.com/api-keys"
        echo "  - Anthropic: https://console.anthropic.com/settings/keys"
        echo ""
        read -p "Press Enter after adding API keys to .env, or Ctrl+C to exit..."
    else
        echo -e "${RED}Error: .env.example not found${NC}"
        exit 1
    fi
fi

# Check if API keys are set
if grep -q "sk-your" .env 2>/dev/null; then
    echo -e "${RED}WARNING: API keys in .env appear to be placeholders${NC}"
    echo "The demo will start but API calls will fail without valid keys"
    read -p "Press Enter to continue anyway, or Ctrl+C to exit..."
fi

# Stop any existing containers
echo -e "${YELLOW}Stopping existing services...${NC}"
docker-compose -f docker-compose.demo.yml down 2>/dev/null || true

# Start services
echo -e "${GREEN}Starting demo services...${NC}"
docker-compose -f docker-compose.demo.yml up -d --build

# Wait for services to be ready
echo -e "${YELLOW}Waiting for services to be ready...${NC}"
MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -f http://localhost:8000/health &>/dev/null; then
        echo -e "${GREEN}✓ API is ready!${NC}"
        break
    fi
    echo -n "."
    sleep 2
    ATTEMPT=$((ATTEMPT + 1))
done
echo ""

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo -e "${RED}Error: Services failed to start${NC}"
    echo "Check logs with: docker-compose -f docker-compose.demo.yml logs"
    exit 1
fi

# Run benchmarks if Poetry is available
if [ "$POETRY_AVAILABLE" = true ] && [ -f benchmarks/run_all_benchmarks.py ]; then
    echo -e "${GREEN}Running performance benchmarks...${NC}"
    poetry run python benchmarks/run_all_benchmarks.py || true
    
    if [ -f benchmarks/results/latest.json ]; then
        echo -e "${GREEN}Benchmark results generated successfully${NC}"
    fi
fi

# Display access information
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}Demo is ready!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Access points:"
echo -e "  ${GREEN}API Documentation:${NC} http://localhost:8000/docs"
echo -e "  ${GREEN}Alternative Docs:${NC}  http://localhost:8000/redoc"
echo -e "  ${GREEN}Health Check:${NC}      http://localhost:8000/health"
echo -e "  ${GREEN}Grafana:${NC}           http://localhost:3001 (admin/admin)"
echo -e "  ${GREEN}Prometheus:${NC}        http://localhost:9090"
echo ""
echo "Test the API:"
echo -e "  ${YELLOW}curl -X POST http://localhost:8000/api/v1/chat/completions \\${NC}"
echo -e "  ${YELLOW}  -H 'Content-Type: application/json' \\${NC}"
echo -e "  ${YELLOW}  -d '{\"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}]}'${NC}"
echo ""
if [ -f benchmarks/results/latest.json ]; then
    echo "Benchmark results: benchmarks/results/"
    echo ""
fi
echo "To view logs:"
echo -e "  ${YELLOW}docker-compose -f docker-compose.demo.yml logs -f${NC}"
echo ""
echo "To stop the demo:"
echo -e "  ${YELLOW}docker-compose -f docker-compose.demo.yml down${NC}"
echo ""
echo -e "${GREEN}Enjoy exploring the AI Chatbot System!${NC}"