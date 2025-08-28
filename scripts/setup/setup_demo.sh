#!/bin/bash
set -e

# Check for CI mode
CI_MODE=false
if [ "$1" = "--ci-mode" ]; then
    CI_MODE=true
fi

echo "AI Chatbot Demo - Quick Setup"
echo "================================"

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is required but not installed."
    echo "Please install Docker from https://docker.com"
    exit 1
fi

# Setup environment
if [ ! -f .env ]; then
    cp config/environments/.env.example .env
    echo "Created .env file"
    if [ "$CI_MODE" = false ]; then
        echo "WARNING: Please add your API keys to .env file:"
        echo "   - OPENAI_API_KEY"
        echo "   - ANTHROPIC_API_KEY (optional)"
    fi
fi

# Start services
echo "Building and starting services..."
docker-compose -f config/docker/compose/docker-compose.demo.yml up -d --build

# Wait for services
echo "Waiting for services to be ready..."
sleep 10

# Check health
if curl -f http://localhost:8000/health &>/dev/null; then
    echo "SUCCESS: Backend is running at http://localhost:8000"
    echo "API Docs at http://localhost:8000/docs"
else
    echo "WARNING: Backend may still be starting up..."
fi

echo ""
echo "Demo setup complete!"
echo "Chat UI: http://localhost:3000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "To stop: docker-compose -f docker-compose.demo.yml down"