#!/bin/bash

# Restore script for Redis and PostgreSQL data

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backup}"
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-chatbot}"
POSTGRES_DB="${POSTGRES_DB:-chatbot}"

# Function to list available backups
list_backups() {
    echo "Available Redis backups:"
    ls -lh "$BACKUP_DIR/redis/" 2>/dev/null || echo "No Redis backups found"
    echo ""
    echo "Available PostgreSQL backups:"
    ls -lh "$BACKUP_DIR/postgres/" 2>/dev/null || echo "No PostgreSQL backups found"
}

# Function to restore Redis
restore_redis() {
    local backup_file=$1
    
    if [ ! -f "$backup_file" ]; then
        echo "Error: Redis backup file not found: $backup_file"
        return 1
    fi
    
    echo "Restoring Redis from $backup_file..."
    
    # Stop Redis writes
    redis-cli -h $REDIS_HOST -p $REDIS_PORT CONFIG SET stop-writes-on-bgsave-error yes
    
    # Flush existing data (optional, uncomment if needed)
    # redis-cli -h $REDIS_HOST -p $REDIS_PORT FLUSHALL
    
    # Restore the backup
    cat "$backup_file" | redis-cli -h $REDIS_HOST -p $REDIS_PORT --pipe
    
    echo "Redis restore completed"
}

# Function to restore PostgreSQL
restore_postgres() {
    local backup_file=$1
    
    if [ ! -f "$backup_file" ]; then
        echo "Error: PostgreSQL backup file not found: $backup_file"
        return 1
    fi
    
    echo "Restoring PostgreSQL from $backup_file..."
    
    # Decompress if needed
    if [[ "$backup_file" == *.gz ]]; then
        echo "Decompressing backup..."
        gunzip -c "$backup_file" > /tmp/restore.sql
        backup_file="/tmp/restore.sql"
    fi
    
    # Restore the backup
    PGPASSWORD="${POSTGRES_PASSWORD:-chatbot123}" psql \
        -h $POSTGRES_HOST \
        -U $POSTGRES_USER \
        -d $POSTGRES_DB \
        -f "$backup_file"
    
    # Clean up temp file
    [ -f /tmp/restore.sql ] && rm /tmp/restore.sql
    
    echo "PostgreSQL restore completed"
}

# Main script
echo "Database Restore Utility"
echo "========================"

if [ $# -eq 0 ]; then
    echo "Usage: $0 [redis|postgres|all] [backup_file]"
    echo ""
    list_backups
    exit 1
fi

case "$1" in
    redis)
        if [ -z "$2" ]; then
            echo "Please specify a Redis backup file"
            list_backups
            exit 1
        fi
        restore_redis "$2"
        ;;
    
    postgres)
        if [ -z "$2" ]; then
            echo "Please specify a PostgreSQL backup file"
            list_backups
            exit 1
        fi
        restore_postgres "$2"
        ;;
    
    all)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "Please specify both Redis and PostgreSQL backup files"
            echo "Usage: $0 all redis_backup postgres_backup"
            list_backups
            exit 1
        fi
        restore_redis "$2"
        restore_postgres "$3"
        ;;
    
    list)
        list_backups
        ;;
    
    *)
        echo "Invalid option: $1"
        echo "Usage: $0 [redis|postgres|all|list] [backup_file]"
        exit 1
        ;;
esac

echo "Restore process completed at $(date)"