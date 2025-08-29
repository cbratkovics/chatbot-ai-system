#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Checklist items status
declare -A CHECKLIST

# Function to print section header
print_section() {
    echo -e "\n${CYAN}═══════════════════════════════════════════${NC}"
    echo -e "${CYAN}▶ $1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════${NC}"
}

# Function to check item
check_item() {
    local key=$1
    local description=$2
    local command=$3
    
    if eval "$command" &>/dev/null; then
        CHECKLIST[$key]="✓"
        echo -e "  ${GREEN}✓${NC} $description"
        return 0
    else
        CHECKLIST[$key]="✗"
        echo -e "  ${RED}✗${NC} $description"
        return 1
    fi
}

# Function to check with warning
check_warn() {
    local description=$1
    local command=$2
    
    if eval "$command" &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $description"
    else
        echo -e "  ${YELLOW}⚠${NC} $description ${YELLOW}(recommended)${NC}"
    fi
}

# Header
echo -e "${MAGENTA}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║      AI Chatbot System Production Checklist      ║${NC}"
echo -e "${MAGENTA}╚══════════════════════════════════════════════════╝${NC}"

TOTAL_CHECKS=0
PASSED_CHECKS=0

# Code Quality
print_section "1. CODE QUALITY"

check_item "format" "Code formatting (black)" "poetry run black --check src tests"
check_item "imports" "Import sorting (isort)" "poetry run isort --check-only src tests"
check_item "lint_ruff" "Linting (ruff)" "poetry run ruff check src tests"
check_item "lint_flake8" "Linting (flake8)" "poetry run flake8 src tests"
check_item "type" "Type checking (mypy)" "poetry run mypy src"
((TOTAL_CHECKS+=5))

# Security
print_section "2. SECURITY"

check_item "bandit" "Security scan (bandit)" "poetry run bandit -r src"
check_item "safety" "Dependency vulnerabilities (safety)" "poetry export -f requirements.txt | poetry run safety check --stdin"
check_warn "Secrets scanning" "git secrets --scan"
check_warn "SAST tools configured" "test -f .github/workflows/security.yml"

# Check for sensitive files
if grep -r "OPENAI_API_KEY\|ANTHROPIC_API_KEY\|JWT_SECRET" --include="*.py" src/ &>/dev/null; then
    echo -e "  ${RED}✗${NC} Hardcoded secrets found in code"
else
    echo -e "  ${GREEN}✓${NC} No hardcoded secrets in code"
    ((PASSED_CHECKS++))
fi
((TOTAL_CHECKS+=3))

# Testing
print_section "3. TESTING"

check_item "tests_unit" "Unit tests pass" "poetry run pytest -m unit --quiet"
check_item "tests_integration" "Integration tests configured" "test -f tests/integration/test_api_integration.py"

# Check test coverage
COVERAGE=$(poetry run pytest --cov=src/chatbot_ai_system --cov-report=term --quiet 2>/dev/null | grep TOTAL | awk '{print $4}' | sed 's/%//')
if [ ! -z "$COVERAGE" ]; then
    if (( $(echo "$COVERAGE >= 80" | bc -l) )); then
        echo -e "  ${GREEN}✓${NC} Test coverage: ${COVERAGE}% (>= 80%)"
        ((PASSED_CHECKS++))
    elif (( $(echo "$COVERAGE >= 60" | bc -l) )); then
        echo -e "  ${YELLOW}⚠${NC} Test coverage: ${COVERAGE}% (recommended >= 80%)"
    else
        echo -e "  ${RED}✗${NC} Test coverage: ${COVERAGE}% (minimum 60%)"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} Could not determine test coverage"
fi
((TOTAL_CHECKS+=3))

# Documentation
print_section "4. DOCUMENTATION"

check_item "readme" "README.md exists" "test -f README.md"
check_item "license" "LICENSE file exists" "test -f LICENSE"
check_item "changelog" "CHANGELOG.md exists" "test -f CHANGELOG.md"
check_item "contributing" "CONTRIBUTING.md exists" "test -f CONTRIBUTING.md"
check_warn "API documentation" "test -d docs/api"
check_warn "Architecture docs" "test -f docs/ARCHITECTURE.md"
((TOTAL_CHECKS+=4))

# Dependencies
print_section "5. DEPENDENCIES"

check_item "lock" "Lock file up to date" "poetry lock --check"
check_item "outdated" "Check outdated packages" "poetry show --outdated | wc -l | xargs test 0 -eq"

# Check for direct dependencies count
DEP_COUNT=$(poetry show --tree --no-dev | grep -E "^[a-z]" | wc -l)
echo -e "  ℹ️  Direct dependencies: $DEP_COUNT"

# Configuration
print_section "6. CONFIGURATION"

check_item "env_example" ".env.example exists" "test -f .env.example"
check_item "env_ignored" ".env in .gitignore" "grep -q '^\.env$' .gitignore"
check_item "config_valid" "Configuration schema valid" "python3 -c 'from chatbot_ai_system.config import Settings'"

# Check for environment-specific configs
check_warn "Production config" "test -f config/production.yml"
check_warn "Staging config" "test -f config/staging.yml"
((TOTAL_CHECKS+=3))

# Docker
print_section "7. DOCKER & DEPLOYMENT"

check_item "dockerfile" "Dockerfile exists" "test -f Dockerfile"
check_item "docker_build" "Docker image builds" "docker build -t test-build . --target builder --quiet"
check_item "compose" "docker-compose.yml valid" "docker-compose config --quiet"
check_item "healthcheck" "Health check endpoint" "grep -q HEALTHCHECK Dockerfile"
check_item "nonroot" "Non-root user in Docker" "grep -q 'USER chatbot' Dockerfile"
((TOTAL_CHECKS+=5))

# CI/CD
print_section "8. CI/CD PIPELINE"

check_item "ci_workflow" "CI workflow exists" "test -f .github/workflows/ci.yml"
check_item "release_workflow" "Release workflow exists" "test -f .github/workflows/release.yml"
check_item "pr_checks" "PR checks configured" "test -f .github/workflows/pr-checks.yml"
check_item "dependabot" "Dependabot configured" "test -f .github/dependabot.yml"
check_warn "Branch protection" "gh api repos/$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/branches/main/protection 2>/dev/null"
((TOTAL_CHECKS+=4))

# Performance
print_section "9. PERFORMANCE & MONITORING"

check_warn "Metrics endpoint" "grep -q '/metrics' src/chatbot_ai_system/server/main.py"
check_warn "Logging configured" "grep -q 'import logging' src/chatbot_ai_system/__init__.py"
check_warn "APM integration" "test -f config/apm.yml"
check_warn "Rate limiting" "grep -q 'slowapi\|ratelimit' pyproject.toml"

# Error Handling
print_section "10. ERROR HANDLING"

check_item "exceptions" "Custom exceptions defined" "test -f src/chatbot_ai_system/exceptions.py"
check_warn "Error middleware" "grep -q 'exception_handler' src/chatbot_ai_system/server/main.py"
check_warn "Validation errors" "grep -q 'ValidationError' src/chatbot_ai_system/schemas.py"
((TOTAL_CHECKS+=1))

# Database & Migrations
print_section "11. DATABASE (if applicable)"

if grep -q "sqlalchemy\|alembic\|prisma" pyproject.toml &>/dev/null; then
    check_warn "Migration tool configured" "test -d alembic || test -d migrations"
    check_warn "Database backups" "test -f scripts/backup_db.sh"
    check_warn "Connection pooling" "grep -q 'pool_size\|max_overflow' src/"
fi

# API Design
print_section "12. API DESIGN"

check_item "openapi" "OpenAPI/Swagger available" "python3 -c 'from chatbot_ai_system.server.main import app; print(app.openapi())' &>/dev/null"
check_warn "API versioning" "grep -q '/api/v1' src/chatbot_ai_system/server/main.py"
check_warn "CORS configured" "grep -q 'CORSMiddleware' src/chatbot_ai_system/server/main.py"
((TOTAL_CHECKS+=1))

# Legal & Compliance
print_section "13. LEGAL & COMPLIANCE"

check_item "license_type" "License specified" "grep -q 'license' pyproject.toml"
check_warn "Privacy policy" "test -f PRIVACY.md"
check_warn "Terms of service" "test -f TERMS.md"
check_warn "Security policy" "test -f SECURITY.md"
((TOTAL_CHECKS+=1))

# Production Readiness Score
print_section "PRODUCTION READINESS SCORE"

# Count passed checks
for key in "${!CHECKLIST[@]}"; do
    if [ "${CHECKLIST[$key]}" == "✓" ]; then
        ((PASSED_CHECKS++))
    fi
done

SCORE=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Total Checks: $TOTAL_CHECKS${NC}"
echo -e "${BLUE}Passed: $PASSED_CHECKS${NC}"
echo -e "${BLUE}Failed: $((TOTAL_CHECKS - PASSED_CHECKS))${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ $SCORE -ge 90 ]; then
    echo -e "${GREEN}▶ Production Readiness: ${SCORE}% - EXCELLENT${NC}"
    echo -e "${GREEN}Your application is production-ready!${NC}"
elif [ $SCORE -ge 75 ]; then
    echo -e "${GREEN}▶ Production Readiness: ${SCORE}% - GOOD${NC}"
    echo -e "${GREEN}Your application is nearly production-ready.${NC}"
elif [ $SCORE -ge 60 ]; then
    echo -e "${YELLOW}▶ Production Readiness: ${SCORE}% - FAIR${NC}"
    echo -e "${YELLOW}Address the failed checks before deploying to production.${NC}"
else
    echo -e "${RED}▶ Production Readiness: ${SCORE}% - NEEDS WORK${NC}"
    echo -e "${RED}Significant improvements needed before production deployment.${NC}"
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Recommendations
if [ $((TOTAL_CHECKS - PASSED_CHECKS)) -gt 0 ]; then
    echo -e "\n${YELLOW}📋 Priority Recommendations:${NC}"
    
    [ "${CHECKLIST[format]}" != "✓" ] && echo -e "  • Run: ${CYAN}make format${NC}"
    [ "${CHECKLIST[lint_ruff]}" != "✓" ] && echo -e "  • Run: ${CYAN}make lint${NC}"
    [ "${CHECKLIST[type]}" != "✓" ] && echo -e "  • Run: ${CYAN}make type-check${NC}"
    [ "${CHECKLIST[bandit]}" != "✓" ] && echo -e "  • Run: ${CYAN}make security${NC}"
    [ "${CHECKLIST[tests_unit]}" != "✓" ] && echo -e "  • Fix failing tests: ${CYAN}make test${NC}"
    [ "${CHECKLIST[docker_build]}" != "✓" ] && echo -e "  • Fix Docker build: ${CYAN}make docker-build${NC}"
fi

exit $((TOTAL_CHECKS - PASSED_CHECKS))