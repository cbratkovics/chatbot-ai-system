#!/bin/bash
set -e

echo "AI Chatbot System - Quick Start"
echo "=================================="
echo ""

# Check Python version
echo "[1] Checking Python version..."
python3 --version

# Install dependencies
echo ""
echo "[2] Installing dependencies..."
if [ -f "pyproject.toml" ] && command -v poetry &> /dev/null; then
    echo "    Using Poetry..."
    poetry install --no-interaction --no-ansi || true
elif [ -f "requirements.txt" ]; then
    echo "    Using pip with requirements.txt..."
    pip install -r requirements.txt || true
else
    echo "    Installing minimal dependencies..."
    pip install fastapi uvicorn || true
fi

# Set Python path
export PYTHONPATH="${PWD}/src:${PYTHONPATH}"

# Run tests
echo ""
echo "[3] Running tests..."
if [ -f "tests/test_basic_working.py" ]; then
    python -m pytest tests/test_basic_working.py -v --tb=short || true
else
    echo "    No tests found, skipping..."
fi

# Start the API server
echo ""
echo "[4] Starting API server..."
echo "    Server will run at: http://localhost:8000"
echo "    API Docs at: http://localhost:8000/docs"
echo "    Press Ctrl+C to stop"
echo ""

# Start server
if command -v poetry &> /dev/null && [ -f "pyproject.toml" ]; then
    poetry run python src/chatbot_ai_system/server/main_simple.py
else
    python src/chatbot_ai_system/server/main_simple.py
fi