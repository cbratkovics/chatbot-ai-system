#!/bin/bash

# Backup script for Redis and PostgreSQL data

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backup}"
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-chatbot}"
POSTGRES_DB="${POSTGRES_DB:-chatbot}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS="${RETENTION_DAYS:-7}"

# Create backup directory
mkdir -p "$BACKUP_DIR/redis" "$BACKUP_DIR/postgres"

echo "Starting backup at $(date)"

# Backup Redis
echo "Backing up Redis..."
if redis-cli -h $REDIS_HOST -p $REDIS_PORT ping > /dev/null 2>&1; then
    redis-cli -h $REDIS_HOST -p $REDIS_PORT --rdb "$BACKUP_DIR/redis/dump_${TIMESTAMP}.rdb"
    echo "Redis backup completed: dump_${TIMESTAMP}.rdb"
else
    echo "Warning: Redis is not accessible, skipping Redis backup"
fi

# Backup PostgreSQL
echo "Backing up PostgreSQL..."
if PGPASSWORD="${POSTGRES_PASSWORD:-chatbot123}" pg_isready -h $POSTGRES_HOST -U $POSTGRES_USER > /dev/null 2>&1; then
    PGPASSWORD="${POSTGRES_PASSWORD:-chatbot123}" pg_dump \
        -h $POSTGRES_HOST \
        -U $POSTGRES_USER \
        -d $POSTGRES_DB \
        -f "$BACKUP_DIR/postgres/dump_${TIMESTAMP}.sql" \
        --verbose \
        --clean \
        --if-exists

    # Compress the backup
    gzip "$BACKUP_DIR/postgres/dump_${TIMESTAMP}.sql"
    echo "PostgreSQL backup completed: dump_${TIMESTAMP}.sql.gz"
else
    echo "Warning: PostgreSQL is not accessible, skipping PostgreSQL backup"
fi

# Clean up old backups
echo "Cleaning up old backups (older than $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -name "dump_*" -type f -mtime +$RETENTION_DAYS -delete

echo "Backup completed at $(date)"

# List current backups
echo "Current backups:"
ls -lh "$BACKUP_DIR/redis/" 2>/dev/null || echo "No Redis backups"
ls -lh "$BACKUP_DIR/postgres/" 2>/dev/null || echo "No PostgreSQL backups"
