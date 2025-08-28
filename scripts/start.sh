#!/bin/bash
# Start script for the AI Chatbot System

set -e

echo "Starting AI Chatbot System..."

# Check environment
if [ -z "$ENVIRONMENT" ]; then
    export ENVIRONMENT="production"
fi

echo "Environment: $ENVIRONMENT"

# Run migrations if needed
# python -m alembic upgrade head

# Start the application
if [ "$ENVIRONMENT" = "production" ]; then
    exec gunicorn api.app.main:app \
        --bind 0.0.0.0:8000 \
        --workers ${WORKERS:-4} \
        --worker-class uvicorn.workers.UvicornWorker \
        --access-logfile - \
        --error-logfile -
else
    exec python -m uvicorn api.app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload
fi