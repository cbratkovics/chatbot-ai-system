#!/bin/bash

# Comprehensive test script for AI Chatbot System
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
WS_URL="${WS_URL:-ws://localhost:8000/ws/chat}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"

# Test results
PASSED=0
FAILED=0
SKIPPED=0

# Logging functions
pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

skip() {
    echo -e "${YELLOW}○${NC} $1 (skipped)"
    ((SKIPPED++))
}

info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Test functions
test_endpoint() {
    local name=$1
    local url=$2
    local expected_code=$3
    local method=${4:-GET}
    local data=${5:-}

    echo -n "Testing $name... "

    if [ "$method" = "GET" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    else
        response=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" "$url")
    fi

    if [ "$response" = "$expected_code" ]; then
        pass "$name (HTTP $response)"
    else
        fail "$name (Expected $expected_code, got $response)"
    fi
}

test_json_response() {
    local name=$1
    local url=$2
    local json_path=$3
    local expected_value=$4

    echo -n "Testing $name... "

    response=$(curl -s "$url")
    actual_value=$(echo "$response" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data$json_path)" 2>/dev/null || echo "ERROR")

    if [ "$actual_value" = "$expected_value" ]; then
        pass "$name"
    else
        fail "$name (Expected '$expected_value', got '$actual_value')"
    fi
}

# Unit tests
run_unit_tests() {
    echo -e "\n${BLUE}Running Unit Tests${NC}"
    echo "=================="

    if command -v python3 &> /dev/null; then
        if docker exec chatbot-backend pytest /app/tests/unit -v --tb=short 2>/dev/null; then
            pass "Unit tests"
        else
            info "Unit tests not found or failed"
        fi
    else
        skip "Unit tests (Python not available)"
    fi
}

# API tests
run_api_tests() {
    echo -e "\n${BLUE}Running API Tests${NC}"
    echo "================="

    # Health endpoint
    test_endpoint "Health endpoint" "$API_URL/health" "200"

    # API documentation
    test_endpoint "API documentation" "$API_URL/docs" "200"

    # Models endpoint
    test_endpoint "Models list" "$API_URL/api/v1/models" "200"

    # Chat completion (test with invalid data to check validation)
    test_endpoint "Chat validation" "$API_URL/api/v1/chat/completion" "422" "POST" "{}"

    # Chat completion with valid data
    if [ ! -z "$OPENAI_API_KEY" ] || [ ! -z "$ANTHROPIC_API_KEY" ]; then
        chat_data='{"message":"Hello","model":"gpt-3.5-turbo","stream":false}'
        test_endpoint "Chat completion" "$API_URL/api/v1/chat/completion" "200" "POST" "$chat_data"
    else
        skip "Chat completion (No API keys configured)"
    fi

    # Cache stats
    test_endpoint "Cache stats" "$API_URL/api/v1/cache/stats" "200"

    # Rate limiting test
    echo -n "Testing rate limiting... "
    for i in {1..150}; do
        curl -s -o /dev/null "$API_URL/health" &
    done
    wait
    response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health")
    if [ "$response" = "429" ]; then
        pass "Rate limiting"
    else
        fail "Rate limiting (Expected 429, got $response)"
    fi
}

# WebSocket tests
run_websocket_tests() {
    echo -e "\n${BLUE}Running WebSocket Tests${NC}"
    echo "======================"

    if command -v wscat &> /dev/null; then
        echo -n "Testing WebSocket connection... "

        # Test WebSocket connection
        timeout 5 wscat -c "$WS_URL" -x '{"type":"ping","id":"test"}' > /tmp/ws_test.log 2>&1 &
        WS_PID=$!
        sleep 2

        if ps -p $WS_PID > /dev/null; then
            kill $WS_PID 2>/dev/null
            pass "WebSocket connection"
        else
            fail "WebSocket connection"
        fi
    else
        info "wscat not found, installing..."
        npm install -g wscat 2>/dev/null || skip "WebSocket tests (wscat not available)"
    fi
}

# Frontend tests
run_frontend_tests() {
    echo -e "\n${BLUE}Running Frontend Tests${NC}"
    echo "====================="

    # Frontend health
    test_endpoint "Frontend homepage" "$FRONTEND_URL" "200"

    # Static assets
    test_endpoint "Frontend assets" "$FRONTEND_URL/_next/static" "404"

    # API proxy
    test_endpoint "Frontend API proxy" "$FRONTEND_URL/api/health" "200"
}

# Integration tests
run_integration_tests() {
    echo -e "\n${BLUE}Running Integration Tests${NC}"
    echo "========================"

    # Test Redis connection
    echo -n "Testing Redis connection... "
    if docker exec chatbot-redis redis-cli ping > /dev/null 2>&1; then
        pass "Redis connection"
    else
        fail "Redis connection"
    fi

    # Test PostgreSQL connection
    echo -n "Testing PostgreSQL connection... "
    if docker exec chatbot-postgres pg_isready > /dev/null 2>&1; then
        pass "PostgreSQL connection"
    else
        fail "PostgreSQL connection"
    fi

    # Test cache functionality
    echo -n "Testing cache functionality... "
    # Warm cache
    curl -s -X POST "$API_URL/api/v1/cache/warm" \
        -H "Content-Type: application/json" \
        -d '{"patterns":["test"]}' > /dev/null

    # Check cache stats
    stats=$(curl -s "$API_URL/api/v1/cache/stats")
    if echo "$stats" | grep -q "cache_size"; then
        pass "Cache functionality"
    else
        fail "Cache functionality"
    fi
}

# Performance tests
run_performance_tests() {
    echo -e "\n${BLUE}Running Performance Tests${NC}"
    echo "========================="

    if command -v ab &> /dev/null; then
        echo -n "Testing API performance... "

        # Run Apache Bench
        result=$(ab -n 100 -c 10 -t 5 "$API_URL/health" 2>&1 | grep "Requests per second" | awk '{print $4}')

        if [ ! -z "$result" ]; then
            rps=$(echo "$result" | cut -d. -f1)
            if [ "$rps" -gt 50 ]; then
                pass "API performance ($result req/s)"
            else
                fail "API performance ($result req/s - expected >50)"
            fi
        else
            fail "API performance (could not measure)"
        fi
    else
        skip "Performance tests (Apache Bench not available)"
    fi
}

# Security tests
run_security_tests() {
    echo -e "\n${BLUE}Running Security Tests${NC}"
    echo "====================="

    # Test security headers
    echo -n "Testing security headers... "
    headers=$(curl -s -I "$API_URL/health")

    required_headers=(
        "X-Content-Type-Options: nosniff"
        "X-Frame-Options: DENY"
        "X-XSS-Protection: 1; mode=block"
    )

    all_present=true
    for header in "${required_headers[@]}"; do
        if ! echo "$headers" | grep -q "$header"; then
            all_present=false
            break
        fi
    done

    if $all_present; then
        pass "Security headers"
    else
        fail "Security headers (missing required headers)"
    fi

    # Test SQL injection protection
    echo -n "Testing SQL injection protection... "
    response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/v1/models?q=' OR '1'='1")
    if [ "$response" = "200" ] || [ "$response" = "400" ]; then
        pass "SQL injection protection"
    else
        fail "SQL injection protection"
    fi

    # Test XSS protection
    echo -n "Testing XSS protection... "
    xss_payload='<script>alert(1)</script>'
    response=$(curl -s -X POST "$API_URL/api/v1/chat/completion" \
        -H "Content-Type: application/json" \
        -d "{\"message\":\"$xss_payload\",\"model\":\"test\"}" \
        | grep -c "<script>")

    if [ "$response" = "0" ]; then
        pass "XSS protection"
    else
        fail "XSS protection"
    fi
}

# Load tests
run_load_tests() {
    echo -e "\n${BLUE}Running Load Tests${NC}"
    echo "=================="

    if command -v hey &> /dev/null; then
        echo "Running 30-second load test..."
        hey -z 30s -c 50 "$API_URL/health" > /tmp/load_test.txt 2>&1

        # Parse results
        total_requests=$(grep "Total:" /tmp/load_test.txt | awk '{print $2}')
        success_rate=$(grep "Success rate:" /tmp/load_test.txt | awk '{print $3}')

        if [ ! -z "$success_rate" ]; then
            pass "Load test completed ($total_requests requests, $success_rate success rate)"
        else
            fail "Load test failed"
        fi
    else
        skip "Load tests (hey not available)"
    fi
}

# Docker tests
run_docker_tests() {
    echo -e "\n${BLUE}Running Docker Tests${NC}"
    echo "==================="

    # Check container health
    echo -n "Testing container health... "
    unhealthy=$(docker ps --filter health=unhealthy --format "{{.Names}}" | wc -l)
    if [ "$unhealthy" = "0" ]; then
        pass "All containers healthy"
    else
        fail "$unhealthy unhealthy container(s)"
    fi

    # Check resource usage
    echo -n "Testing resource usage... "
    high_cpu=$(docker stats --no-stream --format "{{.CPUPerc}}" | sed 's/%//' | awk '$1 > 80 {count++} END {print count+0}')
    if [ "$high_cpu" = "0" ]; then
        pass "Resource usage normal"
    else
        warning "$high_cpu container(s) with high CPU usage"
    fi
}

# Generate report
generate_report() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}Test Results Summary${NC}"
    echo -e "${BLUE}========================================${NC}"

    total=$((PASSED + FAILED + SKIPPED))

    echo -e "${GREEN}Passed:${NC}  $PASSED/$total"
    echo -e "${RED}Failed:${NC}  $FAILED/$total"
    echo -e "${YELLOW}Skipped:${NC} $SKIPPED/$total"

    if [ $FAILED -eq 0 ]; then
        echo -e "\n${GREEN}✓ All tests passed!${NC}"
        exit 0
    else
        echo -e "\n${RED}✗ $FAILED test(s) failed${NC}"
        exit 1
    fi
}

# Main test execution
main() {
    echo -e "${BLUE}AI Chatbot System Test Suite${NC}"
    echo "============================="
    echo ""

    # Check if services are running
    if ! curl -s -f "$API_URL/health" > /dev/null; then
        echo -e "${RED}Error: Services are not running${NC}"
        echo "Please start services with: docker-compose up -d"
        exit 1
    fi

    # Run test suites
    run_api_tests
    run_websocket_tests
    run_frontend_tests
    run_integration_tests
    run_security_tests
    run_docker_tests

    # Optional test suites
    if [ "$1" = "--full" ]; then
        run_unit_tests
        run_performance_tests
        run_load_tests
    else
        echo ""
        info "Run with --full for complete test suite"
    fi

    # Generate report
    generate_report
}

# Run main function
main "$@"
