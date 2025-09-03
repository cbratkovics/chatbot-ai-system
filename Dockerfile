# Multi-stage build for production-ready backend
# Stage 1: Build stage
FROM python:3.11-slim as builder

# Build arguments
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=1.0.0

# Labels for security scanning
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.authors="AI Chatbot Team" \
      org.opencontainers.image.url="https://github.com/yourusername/chatbot-ai-system" \
      org.opencontainers.image.source="https://github.com/yourusername/chatbot-ai-system" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.vendor="AI Chatbot System" \
      org.opencontainers.image.title="AI Chatbot Backend" \
      org.opencontainers.image.description="Production-ready AI chatbot with OpenAI and Anthropic support"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install dependencies
WORKDIR /build
COPY pyproject.toml poetry.lock ./
COPY src ./src

# Install Poetry and dependencies
RUN pip install --no-cache-dir poetry==1.8.3 && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi

# Compile Python files for optimization
RUN python -m compileall /opt/venv

# Stage 2: Runtime stage
FROM python:3.11-slim

# Security: Create non-root user
RUN groupadd -g 1000 appuser && \
    useradd -r -u 1000 -g appuser appuser && \
    mkdir -p /app /app/logs /app/data && \
    chown -R appuser:appuser /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Copy application code
WORKDIR /app
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser scripts/startup.sh scripts/healthcheck.sh ./scripts/
COPY --chown=appuser:appuser .env.example .env.example

# Make scripts executable
RUN chmod +x ./scripts/*.sh

# Security: Use non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health').raise_for_status()" || exit 1

# Expose port
EXPOSE 8000

# Use tini for proper signal handling
ENTRYPOINT ["tini", "--"]

# Start application
CMD ["./scripts/startup.sh"]