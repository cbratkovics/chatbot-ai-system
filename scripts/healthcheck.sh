#!/bin/bash

# Comprehensive health check script for all services

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-chatbot}"
POSTGRES_DB="${POSTGRES_DB:-chatbot}"

# Exit codes
EXIT_SUCCESS=0
EXIT_WARNING=1
EXIT_CRITICAL=2

# Track overall health
OVERALL_STATUS=$EXIT_SUCCESS

# Function to check service health
check_service() {
    local service_name=$1
    local check_command=$2
    local critical=${3:-false}
    
    echo -n "Checking $service_name... "
    
    if eval $check_command > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Healthy${NC}"
        return 0
    else
        if [ "$critical" = true ]; then
            echo -e "${RED}✗ Critical${NC}"
            OVERALL_STATUS=$EXIT_CRITICAL
        else
            echo -e "${YELLOW}⚠ Warning${NC}"
            if [ $OVERALL_STATUS -ne $EXIT_CRITICAL ]; then
                OVERALL_STATUS=$EXIT_WARNING
            fi
        fi
        return 1
    fi
}

# Function to get metrics
get_metrics() {
    local url=$1
    local metric=$2
    
    curl -s "$url" | grep -o "\"$metric\":[^,}]*" | cut -d':' -f2 | tr -d ' "'
}

echo "========================================="
echo "AI Chatbot System Health Check"
echo "========================================="
echo ""

# Check Backend API
echo "Backend Services:"
echo "-----------------"

check_service "API Health Endpoint" \
    "curl -f -s -o /dev/null -w '%{http_code}' $BACKEND_URL/health | grep -q '200'" \
    true

if [ $? -eq 0 ]; then
    # Get backend health details
    health_data=$(curl -s $BACKEND_URL/health)
    
    # Check specific providers
    openai_configured=$(echo $health_data | grep -o '"openai":[^,}]*' | cut -d':' -f2 | tr -d ' "')
    anthropic_configured=$(echo $health_data | grep -o '"anthropic":[^,}]*' | cut -d':' -f2 | tr -d ' "')
    
    echo "  - OpenAI Provider: $([ "$openai_configured" = "true" ] && echo -e "${GREEN}Configured${NC}" || echo -e "${YELLOW}Not configured${NC}")"
    echo "  - Anthropic Provider: $([ "$anthropic_configured" = "true" ] && echo -e "${GREEN}Configured${NC}" || echo -e "${YELLOW}Not configured${NC}")"
fi

check_service "WebSocket Endpoint" \
    "curl -f -s -o /dev/null -w '%{http_code}' -H 'Upgrade: websocket' -H 'Connection: Upgrade' $BACKEND_URL/ws/chat | grep -q '426'"

check_service "Models Endpoint" \
    "curl -f -s $BACKEND_URL/api/v1/models | grep -q 'gpt'"

echo ""

# Check Frontend
echo "Frontend Services:"
echo "------------------"

check_service "Frontend Health" \
    "curl -f -s -o /dev/null -w '%{http_code}' $FRONTEND_URL | grep -q '200'" \
    true

echo ""

# Check Redis
echo "Cache Services:"
echo "---------------"

check_service "Redis Connection" \
    "redis-cli -h $REDIS_HOST -p $REDIS_PORT ping | grep -q 'PONG'"

if [ $? -eq 0 ]; then
    # Get Redis stats
    used_memory=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT INFO memory | grep used_memory_human | cut -d':' -f2 | tr -d '\r')
    connected_clients=$(redis-cli -h $REDIS_HOST -p $REDIS_PORT INFO clients | grep connected_clients | cut -d':' -f2 | tr -d '\r')
    
    echo "  - Memory Used: $used_memory"
    echo "  - Connected Clients: $connected_clients"
    
    # Check cache stats from backend
    cache_stats=$(curl -s $BACKEND_URL/api/v1/cache/stats 2>/dev/null || echo "{}")
    if [ "$cache_stats" != "{}" ]; then
        hits=$(echo $cache_stats | grep -o '"hits":[^,}]*' | cut -d':' -f2 | tr -d ' "')
        misses=$(echo $cache_stats | grep -o '"misses":[^,}]*' | cut -d':' -f2 | tr -d ' "')
        
        if [ -n "$hits" ] && [ -n "$misses" ] && [ $((hits + misses)) -gt 0 ]; then
            hit_rate=$(echo "scale=2; $hits * 100 / ($hits + $misses)" | bc)
            echo "  - Cache Hit Rate: ${hit_rate}%"
        fi
    fi
fi

echo ""

# Check PostgreSQL
echo "Database Services:"
echo "------------------"

check_service "PostgreSQL Connection" \
    "PGPASSWORD=${POSTGRES_PASSWORD:-chatbot123} psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c 'SELECT 1' 2>/dev/null | grep -q '1'"

if [ $? -eq 0 ]; then
    # Get connection count
    conn_count=$(PGPASSWORD=${POSTGRES_PASSWORD:-chatbot123} psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname='$POSTGRES_DB'" 2>/dev/null | tr -d ' ')
    
    if [ -n "$conn_count" ]; then
        echo "  - Active Connections: $conn_count"
    fi
fi

echo ""

# Performance checks
echo "Performance Metrics:"
echo "-------------------"

# Test API response time
start_time=$(date +%s%N)
curl -s -o /dev/null $BACKEND_URL/health 2>/dev/null
end_time=$(date +%s%N)
response_time=$(echo "scale=2; ($end_time - $start_time) / 1000000" | bc)
echo "  - API Response Time: ${response_time}ms"

# Check system resources
if command -v docker &> /dev/null; then
    echo ""
    echo "Container Resources:"
    echo "-------------------"
    
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep chatbot || true
fi

echo ""
echo "========================================="

# Summary
case $OVERALL_STATUS in
    $EXIT_SUCCESS)
        echo -e "${GREEN}✓ All systems operational${NC}"
        ;;
    $EXIT_WARNING)
        echo -e "${YELLOW}⚠ Some services degraded${NC}"
        ;;
    $EXIT_CRITICAL)
        echo -e "${RED}✗ Critical services down${NC}"
        ;;
esac

echo "========================================="

exit $OVERALL_STATUS