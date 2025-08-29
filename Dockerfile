# Multi-stage build for production
FROM python:3.11-slim as builder

# Build arguments
ARG VERSION=0.1.0
ARG BUILD_DATE
ARG VCS_REF

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_VERSION=1.7.1
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VENV=/opt/poetry-venv
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_IN_PROJECT=1
ENV POETRY_VIRTUALENVS_CREATE=1

RUN python -m venv $POETRY_VENV \
    && $POETRY_VENV/bin/pip install -U pip setuptools \
    && $POETRY_VENV/bin/pip install poetry==${POETRY_VERSION}

ENV PATH="${PATH}:${POETRY_VENV}/bin"

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --only main --no-root

# Copy source code
COPY src/ ./src/
COPY README.md ./

# Build wheel
RUN poetry build --format wheel

# Final stage
FROM python:3.11-slim

# Build arguments
ARG VERSION=0.1.0
ARG BUILD_DATE
ARG VCS_REF

# Labels
LABEL org.opencontainers.image.title="AI Chatbot System"
LABEL org.opencontainers.image.description="Production-ready multi-provider AI chatbot platform"
LABEL org.opencontainers.image.version=$VERSION
LABEL org.opencontainers.image.created=$BUILD_DATE
LABEL org.opencontainers.image.revision=$VCS_REF
LABEL org.opencontainers.image.authors="Christopher Bratkovics <cbratkovics@gmail.com>"
LABEL org.opencontainers.image.source="https://github.com/cbratkovics/chatbot-ai-system"
LABEL org.opencontainers.image.licenses="MIT"

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r chatbot && useradd -r -g chatbot chatbot

# Set working directory
WORKDIR /app

# Copy wheel from builder
COPY --from=builder /app/dist/*.whl /tmp/

# Install application
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Copy configuration files if they exist
COPY --chown=chatbot:chatbot config/ ./config/ 2>/dev/null || true

# Create necessary directories
RUN mkdir -p /app/logs /app/data && \
    chown -R chatbot:chatbot /app

# Switch to non-root user
USER chatbot

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV HOST=0.0.0.0
ENV PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE ${PORT}

# Run application
CMD ["chatbotai", "serve", "--host", "0.0.0.0", "--port", "8000"]