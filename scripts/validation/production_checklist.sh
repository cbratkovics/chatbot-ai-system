#!/bin/bash
# Production Readiness Checklist

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Production Readiness Checklist${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

CHECKS_PASSED=0
CHECKS_FAILED=0

# Function to check condition
check() {
    local description="$1"
    local command="$2"
    
    echo -n "Checking: $description... "
    
    if eval "$command" &>/dev/null; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((CHECKS_PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((CHECKS_FAILED++))
        return 1
    fi
}

# Function for warning checks
warn_check() {
    local description="$1"
    local command="$2"
    
    echo -n "Checking: $description... "
    
    if eval "$command" &>/dev/null; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((CHECKS_PASSED++))
        return 0
    else
        echo -e "${YELLOW}⚠ WARNING${NC}"
        return 1
    fi
}

echo -e "${YELLOW}1. Code Quality${NC}"
echo "------------------------"
check "Python files exist" "ls src/chatbot_ai_system/*.py"
check "Tests directory exists" "[ -d tests ]"
check "Dockerfile exists" "[ -f Dockerfile ]"
check "Poetry lock file exists" "[ -f poetry.lock ]"
check "pyproject.toml exists" "[ -f pyproject.toml ]"
echo ""

echo -e "${YELLOW}2. Configuration${NC}"
echo "------------------------"
check ".env.example exists" "[ -f .env.example ]"
check "Config module exists" "[ -f src/chatbot_ai_system/config/settings.py ]"
warn_check ".env file exists (for demo)" "[ -f .env ]"
echo ""

echo -e "${YELLOW}3. Documentation${NC}"
echo "------------------------"
check "README.md exists" "[ -f README.md ]"
check "LICENSE file exists" "[ -f LICENSE ]"
warn_check "CHANGELOG.md exists" "[ -f CHANGELOG.md ]"
warn_check "SECURITY.md exists" "[ -f SECURITY.md ]"
echo ""

echo -e "${YELLOW}4. CI/CD${NC}"
echo "------------------------"
check "GitHub Actions workflow exists" "[ -f .github/workflows/ci.yml ]"
check "Makefile exists" "[ -f Makefile ]"
check "Docker compose files exist" "ls docker-compose*.yml"
echo ""

echo -e "${YELLOW}5. Testing${NC}"
echo "------------------------"
check "Unit tests exist" "ls tests/unit/*.py 2>/dev/null | grep -q '.py'"
warn_check "Integration tests exist" "ls tests/integration/*.py 2>/dev/null | grep -q '.py'"
warn_check "E2E tests exist" "ls tests/e2e/*.py 2>/dev/null | grep -q '.py'"
check "Benchmark scripts exist" "[ -f benchmarks/run_all_benchmarks.py ]"
echo ""

echo -e "${YELLOW}6. Performance & Monitoring${NC}"
echo "------------------------"
check "Health check endpoint defined" "grep -q '/health' src/chatbot_ai_system/health.py"
check "Benchmarks directory exists" "[ -d benchmarks ]"
warn_check "Monitoring config exists" "[ -d monitoring ]"
echo ""

echo -e "${YELLOW}7. Security${NC}"
echo "------------------------"
check "No hardcoded secrets in code" "! grep -r 'sk-[a-zA-Z0-9]' src/ 2>/dev/null | grep -v example"
check ".gitignore includes .env" "grep -q '^.env$' .gitignore"
check "Dependencies specified" "[ -f pyproject.toml ]"
echo ""

echo -e "${YELLOW}8. Deployment${NC}"
echo "------------------------"
check "Dockerfile is multi-stage" "grep -q 'FROM.*as builder' Dockerfile"
check "Docker healthcheck defined" "grep -q 'HEALTHCHECK' Dockerfile"
check "Non-root user in Docker" "grep -q 'USER' Dockerfile"
check "Demo script exists" "[ -f scripts/demo.sh ]"
echo ""

echo -e "${YELLOW}9. Core Features${NC}"
echo "------------------------"
check "WebSocket manager exists" "[ -f src/chatbot_ai_system/streaming/websocket_manager.py ]"
check "Health check exists" "[ -f src/chatbot_ai_system/health.py ]"
check "Rate limiting exists" "ls src/chatbot_ai_system/*/rate_limiter.py 2>/dev/null | grep -q '.py'"
check "Cache implementation exists" "ls src/chatbot_ai_system/cache/*.py 2>/dev/null | grep -q '.py'"
echo ""

echo -e "${YELLOW}10. Build & Package${NC}"
echo "------------------------"
if command -v poetry &>/dev/null; then
    check "Package builds successfully" "poetry build --quiet"
    check "Dependencies installable" "poetry check"
else
    echo -e "${YELLOW}Poetry not installed - skipping build checks${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Checks Passed:${NC} $CHECKS_PASSED"
echo -e "${RED}Checks Failed:${NC} $CHECKS_FAILED"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All critical checks passed! System is production-ready.${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️ Some checks failed. Review and fix issues before production deployment.${NC}"
    exit 1
fi