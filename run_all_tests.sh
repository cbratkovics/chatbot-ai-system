#!/bin/bash
set -e  # Exit on any error

echo "🧹 Cleaning up..."
rm -f fix*.py

echo "📦 Checking dependencies..."
poetry lock

echo "🎨 Running formatters..."
poetry run black src/ tests/

echo "🔍 Running linters..."
poetry run ruff check src/ tests/

echo "🧪 Running all tests..."
# Test specific categories incrementally
poetry run pytest tests/unit/test_package.py -xvs
poetry run pytest tests/integration/test_cache_integration.py -xvs
poetry run pytest tests/integration/test_model_switching.py -xvs
poetry run pytest tests/integration/test_websocket_flow.py -xvs
poetry run pytest tests/e2e/ -xvs
poetry run pytest tests/ -v --cov=src/chatbot_ai_system --cov-report=html --cov-report=term

echo "✅ All checks passed!"
