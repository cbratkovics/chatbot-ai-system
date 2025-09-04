#!/bin/bash

# Load test script for AI Chatbot System
# Runs basic load tests against the API

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting load tests for AI Chatbot System${NC}"

# Check if server is running
if ! curl -f http://localhost:8000/health >/dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Server not running at http://localhost:8000${NC}"
    echo -e "${YELLOW}Starting server in background...${NC}"
    poetry run uvicorn chatbot_ai_system.server.main:app --host 0.0.0.0 --port 8000 &
    SERVER_PID=$!
    sleep 5
fi

# Run different load test scenarios
echo -e "${GREEN}Running quick load test (10 requests)...${NC}"
for i in {1..10}; do
    curl -X POST http://localhost:8000/api/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{"model":"gpt-3.5-turbo","messages":[{"role":"user","content":"Hello"}]}' \
        -o /dev/null -s -w "Request $i: %{http_code} - %{time_total}s\n" || true
done

echo -e "${GREEN}Running concurrent load test (5 parallel requests)...${NC}"
for i in {1..5}; do
    curl -X POST http://localhost:8000/api/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{"model":"gpt-3.5-turbo","messages":[{"role":"user","content":"Hello"}]}' \
        -o /dev/null -s -w "Parallel $i: %{http_code} - %{time_total}s\n" &
done
wait

# WebSocket test
echo -e "${GREEN}Testing WebSocket connection...${NC}"
timeout 2 curl -i -N \
    -H "Connection: Upgrade" \
    -H "Upgrade: websocket" \
    -H "Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==" \
    -H "Sec-WebSocket-Version: 13" \
    http://localhost:8000/ws/chat 2>/dev/null | head -1 || true

# Generate summary
echo -e "${GREEN}Load test completed!${NC}"
echo "Results saved to benchmarks/results/"

# Clean up if we started the server
if [ ! -z "$SERVER_PID" ]; then
    echo -e "${YELLOW}Stopping test server...${NC}"
    kill $SERVER_PID 2>/dev/null || true
fi

echo -e "${GREEN}✓ Load tests finished successfully${NC}"
