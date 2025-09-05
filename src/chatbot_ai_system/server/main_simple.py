"""Main FastAPI application."""
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Create FastAPI app
app = FastAPI(
    title="AI Chatbot System",
    description="Production-ready multi-provider chatbot orchestration platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AI Chatbot System API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "ai-chatbot-system",
            "version": "1.0.0",
            "environment": os.getenv("ENVIRONMENT", "development"),
            "checks": {
                "api": True,
                "database": True,
                "cache": True
            }
        }
    )

@app.get("/api/v1/models")
async def list_models():
    """List available AI models."""
    return {
        "models": [
            {"provider": "openai", "model": "gpt-3.5-turbo", "status": "available"},
            {"provider": "openai", "model": "gpt-4", "status": "available"},
            {"provider": "anthropic", "model": "claude-3-haiku-20240307", "status": "available"},
            {"provider": "anthropic", "model": "claude-3-sonnet", "status": "available"}
        ]
    }

@app.post("/api/v1/chat/completions")
async def chat_completion(request: dict):
    """Mock chat completion endpoint."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": request.get("model", "gpt-3.5-turbo"),
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is a demo response from the AI Chatbot System."
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)