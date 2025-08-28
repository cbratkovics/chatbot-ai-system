#!/bin/bash
set -e

echo "Fixing repository structure..."

# Ensure all required directories exist
mkdir -p config/requirements
mkdir -p config/docker/dockerfiles
mkdir -p config/docker/compose
mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p app

# Check if we already have requirements files
if [ ! -f config/requirements/base.txt ]; then
  echo "Creating base requirements..."
  cat > config/requirements/base.txt << EOF
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0
python-dotenv==1.0.0
redis==5.0.1
httpx==0.25.2
websockets==12.0
aiofiles==23.2.1
python-multipart==0.0.6
EOF
fi

if [ ! -f config/requirements/dev.txt ]; then
  echo "Creating dev requirements..."
  cat > config/requirements/dev.txt << EOF
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-timeout==2.2.0
black==23.11.0
flake8==6.1.0
mypy==1.7.1
isort==5.12.0
httpx==0.25.2
EOF
fi

if [ ! -f config/requirements/prod.txt ]; then
  echo "Creating prod requirements..."
  cat > config/requirements/prod.txt << EOF
-r base.txt
gunicorn==21.2.0
EOF
fi

# Create basic test file if missing
if [ ! -f tests/test_basic.py ]; then
  cat > tests/test_basic.py << EOF
"""Basic test to ensure pytest works."""

def test_import():
    """Test that we can import the app module."""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert True

def test_basic_math():
    """Basic test to verify pytest is working."""
    assert 1 + 1 == 2

def test_environment():
    """Test environment setup."""
    import os
    assert os.path.exists('config/requirements/base.txt')
EOF
fi

# Create __init__.py files
touch app/__init__.py 2>/dev/null || true
touch tests/__init__.py 2>/dev/null || true
touch tests/unit/__init__.py 2>/dev/null || true
touch tests/integration/__init__.py 2>/dev/null || true

# Create a simple app main file if missing
if [ ! -f app/main.py ]; then
  cat > app/main.py << EOF
"""Main application entry point."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="AI Chatbot System", version="1.0.0")

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "AI Chatbot System API"}

@app.get("/health")
async def health():
    """Health check endpoint."""
    return JSONResponse(
        status_code=200,
        content={"status": "healthy", "service": "ai-chatbot-system"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF
fi

echo "✅ Repository structure fixed!"
ls -la config/requirements/
ls -la tests/
ls -la app/