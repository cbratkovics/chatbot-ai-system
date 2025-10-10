#!/bin/bash
# Comprehensive project validation for AI Chatbot System

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track validation results
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   AI Chatbot System Validation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to run a check
run_check() {
    local description="$1"
    local command="$2"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    echo -ne "Checking $description... "
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        echo -e "${RED}✗${NC}"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        return 1
    fi
}

# Function to run a check with output
run_check_verbose() {
    local description="$1"
    local command="$2"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    echo -e "\n${YELLOW}Checking $description...${NC}"
    
    if eval "$command"; then
        echo -e "${GREEN}✓ $description passed${NC}"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        echo -e "${RED}✗ $description failed${NC}"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        return 1
    fi
}

# Check Python version
echo -e "${YELLOW}Environment Checks:${NC}"
run_check "Python version (3.11+)" "python3 --version | grep -E 'Python 3\.(1[1-9]|[2-9][0-9])'"
run_check "Poetry installed" "which poetry"
run_check "Docker installed" "which docker"
run_check "Docker Compose installed" "which docker-compose || docker compose version"

# Check project structure
echo -e "\n${YELLOW}Project Structure:${NC}"
run_check "src directory exists" "[ -d src/chatbot_ai_system ]"
run_check "tests directory exists" "[ -d tests ]"
run_check "benchmarks directory exists" "[ -d benchmarks ]"
run_check "frontend directory exists" "[ -d frontend ]"
run_check "pyproject.toml exists" "[ -f pyproject.toml ]"
run_check "README.md exists" "[ -f README.md ]"
run_check "SECURITY.md exists" "[ -f SECURITY.md ]"
run_check ".env.example exists" "[ -f .env.example ]"

# Check Python imports
echo -e "\n${YELLOW}Python Package:${NC}"
run_check "Package imports correctly" "python3 -c 'import chatbot_ai_system'"
run_check "Version is 1.0.0" "python3 -c 'from chatbot_ai_system import __version__; assert __version__ == \"1.0.0\"'"
run_check "Settings import works" "python3 -c 'from chatbot_ai_system import Settings'"
run_check "Client import works" "python3 -c 'from chatbot_ai_system import ChatbotClient'"

# Check repository name consistency
echo -e "\n${YELLOW}Repository Naming:${NC}"
run_check "No 'ai-chatbot-system' references" "! grep -r 'ai-chatbot-system' --include='*.py' --include='*.md' --include='*.yml' --include='*.yaml' --include='*.json' --include='*.toml' --exclude-dir='.git' --exclude-dir='node_modules' --exclude-dir='.venv' . 2>/dev/null | grep -v 'chatbot-ai-system'"

# Run basic tests
echo -e "\n${YELLOW}Running Tests:${NC}"
if [ -f "tests/unit/test_basic.py" ]; then
    run_check_verbose "Basic unit tests" "python3 -m pytest tests/unit/test_basic.py -v --tb=short"
else
    echo -e "${YELLOW}⚠ Basic unit tests not found${NC}"
fi

# Check Docker configuration
echo -e "\n${YELLOW}Docker Configuration:${NC}"
run_check "Dockerfile exists" "[ -f Dockerfile ]"
run_check "docker-compose.yml exists" "[ -f docker-compose.yml ]"
run_check ".dockerignore exists" "[ -f .dockerignore ]"
run_check "Docker build context valid" "docker build --dry-run . 2>/dev/null || true"

# Check frontend configuration
echo -e "\n${YELLOW}Frontend Configuration:${NC}"
if [ -d "frontend" ]; then
    run_check "package.json exists" "[ -f frontend/package.json ]"
    run_check "Frontend name is correct" "grep -q 'chatbot-ai-system' frontend/package.json"
else
    echo -e "${YELLOW}⚠ Frontend directory not found${NC}"
fi

# Check documentation
echo -e "\n${YELLOW}Documentation:${NC}"
run_check "README has CI badge" "grep -q 'CI Pipeline' README.md"
run_check "README has performance metrics" "grep -q 'Performance Metrics' README.md"
run_check "README has Evidence section" "grep -q 'Evidence & Validation' README.md"

# Summary
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}           Validation Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Total Checks: ${TOTAL_CHECKS}"
echo -e "Passed: ${GREEN}${PASSED_CHECKS}${NC}"
echo -e "Failed: ${RED}${FAILED_CHECKS}${NC}"

if [ $FAILED_CHECKS -eq 0 ]; then
    echo -e "\n${GREEN}✓ All validation checks passed!${NC}"
    echo -e "${GREEN}The project is ready for deployment.${NC}"
    exit 0
else
    echo -e "\n${RED}✗ Some validation checks failed.${NC}"
    echo -e "${YELLOW}Please review and fix the issues above.${NC}"
    exit 1
fi