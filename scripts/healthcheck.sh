#!/bin/sh
# Health check script for Docker container

set -e

# Check if the API is responding
if [ -z "${HEALTH_CHECK_URL}" ]; then
    HEALTH_CHECK_URL="http://localhost:8000/health"
fi

# Perform health check with timeout
response=$(curl -sf --max-time 5 "${HEALTH_CHECK_URL}" || echo "failed")

if [ "$response" = "failed" ]; then
    echo "Health check failed: API not responding"
    exit 1
fi

# Check if response contains expected status
if echo "$response" | grep -q '"status":"healthy"'; then
    echo "Health check passed"
    exit 0
else
    echo "Health check failed: Unhealthy status"
    exit 1
fi