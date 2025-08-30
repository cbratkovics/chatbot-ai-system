"""FastAPI application."""

from typing import Any, Dict, List, Tuple, Optional
from chatbot_system_core.config import Settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

settings = Settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "AI Chatbot System API", "version": "0.1.0"}
