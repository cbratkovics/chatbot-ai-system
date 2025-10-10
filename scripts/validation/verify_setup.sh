#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counter for failures
FAILURES=0

# Function to print colored output
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
        FAILURES=$((FAILURES + 1))
    fi
}

print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Header
echo -e "${YELLOW}╔══════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║     AI Chatbot System Setup Verifier     ║${NC}"
echo -e "${YELLOW}╚══════════════════════════════════════════╝${NC}"

# Check system tools
print_header "Checking System Tools"

# Python
python3 --version &>/dev/null
print_status $? "Python 3 installed"

# Check Python version is 3.11+
if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if (( $(echo "$PYTHON_VERSION >= 3.11" | bc -l) )); then
        print_status 0 "Python version $PYTHON_VERSION (>= 3.11)"
    else
        print_status 1 "Python version $PYTHON_VERSION (requires >= 3.11)"
    fi
fi

# Poetry
poetry --version &>/dev/null
print_status $? "Poetry installed"

# Docker
docker --version &>/dev/null
print_status $? "Docker installed"

# Docker Compose
docker-compose --version &>/dev/null
print_status $? "Docker Compose installed"

# Git
git --version &>/dev/null
print_status $? "Git installed"

# Make
make --version &>/dev/null
print_status $? "Make installed"

# Check Poetry setup
print_header "Checking Poetry Setup"

# Check if pyproject.toml exists
if [ -f "pyproject.toml" ]; then
    print_status 0 "pyproject.toml exists"
else
    print_status 1 "pyproject.toml not found"
fi

# Check if poetry.lock exists
if [ -f "poetry.lock" ]; then
    print_status 0 "poetry.lock exists"
else
    print_status 1 "poetry.lock not found"
fi

# Check Poetry environment
poetry env info &>/dev/null
print_status $? "Poetry environment configured"

# Check dependencies installed
poetry check &>/dev/null
print_status $? "Poetry dependencies valid"

# Check package installation
print_header "Checking Package Installation"

# Try to import the package
poetry run python -c "import chatbot_ai_system" &>/dev/null
print_status $? "Package importable"

# Check version
if poetry run python -c "import chatbot_ai_system" &>/dev/null; then
    VERSION=$(poetry run python -c "import chatbot_ai_system; print(chatbot_ai_system.__version__)" 2>/dev/null)
    if [ ! -z "$VERSION" ]; then
        print_status 0 "Package version: $VERSION"
    else
        print_status 1 "Could not determine package version"
    fi
fi

# Check CLI
print_header "Checking CLI Tool"

# Check if CLI is available
poetry run chatbotai version &>/dev/null
print_status $? "CLI tool available"

# Check CLI commands
poetry run chatbotai --help &>/dev/null
print_status $? "CLI help works"

# Check package imports
print_header "Checking Package Imports"

# Test core imports
poetry run python -c "from chatbot_ai_system import Settings, settings" &>/dev/null
print_status $? "Config imports work"

poetry run python -c "from chatbot_ai_system import ChatbotClient" &>/dev/null
print_status $? "SDK imports work"

poetry run python -c "from chatbot_ai_system import app, start_server" &>/dev/null
print_status $? "Server imports work"

poetry run python -c "from chatbot_ai_system.schemas import ChatRequest, ChatResponse" &>/dev/null
print_status $? "Schema imports work"

poetry run python -c "from chatbot_ai_system.exceptions import ChatbotException" &>/dev/null
print_status $? "Exception imports work"

# Check tests
print_header "Checking Tests"

# Check if tests directory exists
if [ -d "tests" ]; then
    print_status 0 "Tests directory exists"

    # Count test files
    TEST_COUNT=$(find tests -name "test_*.py" | wc -l)
    print_status 0 "Found $TEST_COUNT test files"
else
    print_status 1 "Tests directory not found"
fi

# Run tests (quick check)
poetry run pytest --collect-only &>/dev/null
print_status $? "Test collection works"

# Check Docker setup
print_header "Checking Docker Setup"

# Check Dockerfile
if [ -f "Dockerfile" ]; then
    print_status 0 "Dockerfile exists"

    # Validate Dockerfile syntax
    docker build --no-cache -f Dockerfile . --target builder --dry-run &>/dev/null
    print_status $? "Dockerfile syntax valid"
else
    print_status 1 "Dockerfile not found"
fi

# Check docker-compose.yml
if [ -f "docker-compose.yml" ]; then
    print_status 0 "docker-compose.yml exists"

    # Validate docker-compose syntax
    docker-compose config --quiet &>/dev/null
    print_status $? "docker-compose.yml syntax valid"
else
    print_status 1 "docker-compose.yml not found"
fi

# Check CI/CD
print_header "Checking CI/CD Setup"

# Check GitHub Actions workflows
if [ -d ".github/workflows" ]; then
    print_status 0 "GitHub workflows directory exists"

    WORKFLOW_COUNT=$(find .github/workflows -name "*.yml" -o -name "*.yaml" | wc -l)
    print_status 0 "Found $WORKFLOW_COUNT workflow files"
else
    print_status 1 "GitHub workflows directory not found"
fi

# Check Makefile
if [ -f "Makefile" ]; then
    print_status 0 "Makefile exists"

    # Check key Make targets
    make help &>/dev/null
    print_status $? "Make help target works"
else
    print_status 1 "Makefile not found"
fi

# Check documentation
print_header "Checking Documentation"

if [ -f "README.md" ]; then
    print_status 0 "README.md exists"
else
    print_status 1 "README.md not found"
fi

if [ -f "LICENSE" ]; then
    print_status 0 "LICENSE file exists"
else
    print_status 1 "LICENSE file not found"
fi

# Check environment files
print_header "Checking Environment Configuration"

if [ -f ".env.example" ]; then
    print_status 0 ".env.example exists"
else
    print_status 1 ".env.example not found"
fi

if [ -f ".gitignore" ]; then
    print_status 0 ".gitignore exists"

    # Check if .env is ignored
    grep -q "^\.env$" .gitignore
    print_status $? ".env is in .gitignore"
else
    print_status 1 ".gitignore not found"
fi

# Summary
print_header "Setup Verification Summary"

if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo -e "${GREEN}Your AI Chatbot System is properly set up.${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 0
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}✗ $FAILURES checks failed${NC}"
    echo -e "${RED}Please fix the issues above before proceeding.${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 1
fi
