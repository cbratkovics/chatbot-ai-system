#!/bin/bash

echo "================================"
echo "Demo CI/CD Verification Script"
echo "================================"

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check required files
echo -e "\n${YELLOW}Checking required files...${NC}"
required_files=(
    ".github/workflows/demo-ci.yml"
    ".github/workflows/demo-monitor.yml"
    "config/docker/dockerfiles/Dockerfile.demo"
    "frontend/Dockerfile.demo"
    "config/docker/compose/docker-compose.demo.yml"
    "scripts/setup/setup_demo.sh"
    "docs/guides/README_DEMO.md"
    "config/environments/.env.example"
)

all_present=true
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}[OK]${NC} $file"
    else
        echo -e "${RED}[MISSING]${NC} $file"
        all_present=false
    fi
done

if [ "$all_present" = true ]; then
    echo -e "${GREEN}All required files present${NC}"
else
    echo -e "${RED}Some files are missing${NC}"
    exit 1
fi

# Check Docker
echo -e "\n${YELLOW}Checking Docker...${NC}"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}[OK]${NC} Docker is installed"
    docker --version
else
    echo -e "${RED}[ERROR]${NC} Docker is not installed"
    exit 1
fi

# Check workflow syntax
echo -e "\n${YELLOW}Validating workflow files...${NC}"
for workflow in .github/workflows/demo-*.yml; do
    if [ -f "$workflow" ]; then
        # Basic YAML validation
        if python3 -c "import yaml; yaml.safe_load(open('$workflow'))" 2>/dev/null; then
            echo -e "${GREEN}[OK]${NC} $workflow is valid YAML"
        else
            echo -e "${YELLOW}[WARNING]${NC} Could not validate $workflow"
        fi
    fi
done

# Test Docker build
echo -e "\n${YELLOW}Testing Docker build (dry run)...${NC}"
if docker-compose -f docker-compose.demo.yml config > /dev/null 2>&1; then
    echo -e "${GREEN}[OK]${NC} docker-compose.demo.yml is valid"
else
    echo -e "${RED}[ERROR]${NC} docker-compose.demo.yml has errors"
    docker-compose -f docker-compose.demo.yml config
fi

# Check complexity metrics
echo -e "\n${YELLOW}Checking demo complexity...${NC}"
file_count=$(find . -type f -not -path "./.git/*" | wc -l)
echo "Total files: $file_count"
if [ $file_count -lt 200 ]; then
    echo -e "${GREEN}[OK]${NC} File count within target (<200)"
else
    echo -e "${YELLOW}[WARNING]${NC} File count exceeds target"
fi

# Summary
echo -e "\n================================"
echo -e "${GREEN}Verification Complete${NC}"
echo "================================"
echo ""
echo "Next steps:"
echo "1. Check GitHub Actions tab for CI/CD run status"
echo "2. Wait 2-3 minutes for workflow to complete"
echo "3. If successful, demo CI/CD is fixed!"
echo ""
echo "GitHub Actions URL:"
echo "https://github.com/cbratkovics/ai-chatbot-system/actions"