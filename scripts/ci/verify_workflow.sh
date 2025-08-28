#!/bin/bash
set -e

echo "========================================="
echo "Verifying CI/CD workflow configuration..."
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check required files exist
echo -e "\n${YELLOW}Checking required files...${NC}"
FILES=(
  "config/docker/dockerfiles/Dockerfile.multistage"
  "config/docker/compose/docker-compose.yml"
  "config/requirements/base.txt"
  "config/requirements/dev.txt"
  ".github/workflows/main.yml"
)

MISSING_FILES=0
for file in "${FILES[@]}"; do
  if [ ! -f "$file" ]; then
    echo -e "${RED}✗ Missing: $file${NC}"
    MISSING_FILES=$((MISSING_FILES + 1))
  else
    echo -e "${GREEN}✓ Found: $file${NC}"
  fi
done

if [ $MISSING_FILES -gt 0 ]; then
  echo -e "\n${RED}ERROR: $MISSING_FILES required file(s) missing${NC}"
  exit 1
fi

echo -e "${GREEN}✅ All required files present${NC}"

# Validate YAML syntax
echo -e "\n${YELLOW}Validating workflow YAML syntax...${NC}"
if command -v python3 &> /dev/null; then
  python3 -c "
import yaml
import sys
try:
    with open('.github/workflows/main.yml', 'r') as f:
        yaml.safe_load(f)
    print('✅ Workflow YAML is valid')
except yaml.YAMLError as e:
    print(f'❌ YAML syntax error: {e}')
    sys.exit(1)
" || exit 1
else
  echo -e "${YELLOW}⚠️  Python3 not found, skipping YAML validation${NC}"
fi

# Check Docker availability
echo -e "\n${YELLOW}Checking Docker environment...${NC}"
if command -v docker &> /dev/null; then
  docker version > /dev/null 2>&1
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Docker is available${NC}"
    
    # Test Docker build (dry run)
    echo -e "\n${YELLOW}Testing Docker build (dry run)...${NC}"
    docker build --no-cache --progress=plain -f config/docker/dockerfiles/Dockerfile.multistage -t test-build:ci-verify . --target=builder > /dev/null 2>&1
    if [ $? -eq 0 ]; then
      echo -e "${GREEN}✅ Docker build test successful${NC}"
      docker rmi test-build:ci-verify > /dev/null 2>&1
    else
      echo -e "${YELLOW}⚠️  Docker build test failed (non-critical)${NC}"
    fi
  else
    echo -e "${YELLOW}⚠️  Docker daemon not running${NC}"
  fi
else
  echo -e "${YELLOW}⚠️  Docker not installed${NC}"
fi

# Check for common issues
echo -e "\n${YELLOW}Checking for common issues...${NC}"

# Check if old workflow files still exist
OLD_WORKFLOWS=(
  ".github/workflows/ci.yml"
  ".github/workflows/ci-cd.yml"
  ".github/workflows/deploy.yml"
)

OLD_FILES_FOUND=0
for file in "${OLD_WORKFLOWS[@]}"; do
  if [ -f "$file" ]; then
    echo -e "${YELLOW}⚠️  Old workflow file still exists: $file${NC}"
    OLD_FILES_FOUND=$((OLD_FILES_FOUND + 1))
  fi
done

if [ $OLD_FILES_FOUND -gt 0 ]; then
  echo -e "${YELLOW}Consider removing $OLD_FILES_FOUND old workflow file(s)${NC}"
fi

# Check Python requirements
echo -e "\n${YELLOW}Checking Python requirements...${NC}"
if [ -f "config/requirements/base.txt" ]; then
  line_count=$(wc -l < config/requirements/base.txt)
  echo -e "${GREEN}✓ base.txt has $line_count lines${NC}"
fi

if [ -f "config/requirements/dev.txt" ]; then
  line_count=$(wc -l < config/requirements/dev.txt)
  echo -e "${GREEN}✓ dev.txt has $line_count lines${NC}"
fi

# Summary
echo -e "\n========================================="
echo -e "${GREEN}CI/CD workflow verification complete!${NC}"
echo -e "========================================="
echo ""
echo "Next steps:"
echo "1. Remove old workflow files if they exist"
echo "2. Commit and push changes"
echo "3. Monitor GitHub Actions for the workflow run"
echo ""
echo "To test locally with act (if installed):"
echo "  act -l                    # List workflows"
echo "  act push --dry-run        # Dry run"
echo ""