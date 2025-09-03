#!/bin/bash
set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to log messages
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Function to handle signals
handle_shutdown() {
    log "Received shutdown signal, gracefully stopping services..."
    
    # Send SIGTERM to the main process
    if [ -n "$MAIN_PID" ]; then
        kill -TERM "$MAIN_PID" 2>/dev/null || true
        
        # Wait for process to exit (max 30 seconds)
        local count=0
        while kill -0 "$MAIN_PID" 2>/dev/null && [ $count -lt 30 ]; do
            sleep 1
            count=$((count + 1))
        done
        
        # Force kill if still running
        if kill -0 "$MAIN_PID" 2>/dev/null; then
            warning "Process did not exit gracefully, forcing shutdown"
            kill -KILL "$MAIN_PID" 2>/dev/null || true
        fi
    fi
    
    log "Shutdown complete"
    exit 0
}

# Set up signal handlers
trap handle_shutdown SIGTERM SIGINT SIGQUIT

# Check environment
log "Starting AI Chatbot Backend..."
log "Environment: ${ENVIRONMENT:-development}"
log "Python version: $(python --version)"

# Create necessary directories
mkdir -p /app/logs /app/data

# Check for required environment variables
if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
    error "At least one API key (OPENAI_API_KEY or ANTHROPIC_API_KEY) must be set"
    exit 1
fi

# Wait for dependencies
log "Checking dependencies..."

# Wait for Redis
if [ -n "$REDIS_URL" ]; then
    REDIS_HOST=$(echo $REDIS_URL | sed -n 's/.*\/\/\([^:]*\).*/\1/p')
    REDIS_PORT=$(echo $REDIS_URL | sed -n 's/.*:\([0-9]*\).*/\1/p')
    
    log "Waiting for Redis at $REDIS_HOST:$REDIS_PORT..."
    count=0
    while ! nc -z "$REDIS_HOST" "$REDIS_PORT" 2>/dev/null && [ $count -lt 30 ]; do
        sleep 1
        count=$((count + 1))
    done
    
    if [ $count -eq 30 ]; then
        warning "Redis is not available after 30 seconds, continuing anyway..."
    else
        log "Redis is available"
    fi
fi

# Wait for PostgreSQL
if [ -n "$DATABASE_URL" ]; then
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\).*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    
    log "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
    count=0
    while ! nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null && [ $count -lt 30 ]; do
        sleep 1
        count=$((count + 1))
    done
    
    if [ $count -eq 30 ]; then
        warning "PostgreSQL is not available after 30 seconds, continuing anyway..."
    else
        log "PostgreSQL is available"
    fi
fi

# Run database migrations if needed
if [ -n "$DATABASE_URL" ] && [ -f "/app/src/chatbot_ai_system/database/migrations.py" ]; then
    log "Running database migrations..."
    python -m chatbot_ai_system.database.migrations || warning "Migration failed, continuing anyway"
fi

# Warm up cache if Redis is available
if [ -n "$REDIS_URL" ] && [ "$CACHE_ENABLED" = "true" ]; then
    log "Warming up cache..."
    python -c "
from chatbot_ai_system.cache.redis_cache import RedisCache
import asyncio

async def warm_cache():
    cache = RedisCache()
    await cache.connect()
    await cache.warm_cache(['greeting', 'help', 'about'])
    await cache.disconnect()

asyncio.run(warm_cache())
" || warning "Cache warm-up failed"
fi

# Start the application
log "Starting application..."

if [ "$ENVIRONMENT" = "production" ]; then
    # Production mode with Gunicorn
    exec gunicorn chatbot_ai_system.server.main:app \
        --bind ${HOST:-0.0.0.0}:${PORT:-8000} \
        --workers ${WORKERS:-4} \
        --worker-class uvicorn.workers.UvicornWorker \
        --timeout 120 \
        --keep-alive 5 \
        --max-requests 1000 \
        --max-requests-jitter 50 \
        --access-logfile /app/logs/access.log \
        --error-logfile /app/logs/error.log \
        --log-level ${LOG_LEVEL:-info} \
        --capture-output \
        --enable-stdio-inheritance &
    
    MAIN_PID=$!
    
elif [ "$ENVIRONMENT" = "development" ]; then
    # Development mode with auto-reload
    exec python -m uvicorn chatbot_ai_system.server.main:app \
        --host ${HOST:-0.0.0.0} \
        --port ${PORT:-8000} \
        --reload \
        --log-level ${LOG_LEVEL:-debug} &
    
    MAIN_PID=$!
    
else
    # Default mode
    exec python -m uvicorn chatbot_ai_system.server.main:app \
        --host ${HOST:-0.0.0.0} \
        --port ${PORT:-8000} \
        --workers ${WORKERS:-1} \
        --log-level ${LOG_LEVEL:-info} &
    
    MAIN_PID=$!
fi

# Wait for the main process
wait $MAIN_PID