#!/bin/bash

echo "=== CI/CD Setup Verification ==="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python
echo "Checking Python..."
if python3 --version > /dev/null 2>&1; then
  echo -e "${GREEN}✓${NC} Python installed: $(python3 --version)"
else
  echo -e "${RED}✗${NC} Python not found"
fi

# Check required files
echo ""
echo "Checking required files..."
FILES=(
  "config/requirements/base.txt"
  "config/requirements/dev.txt"
  ".github/workflows/main.yml"
  "app/__init__.py"
  "tests/test_basic.py"
)

for file in "${FILES[@]}"; do
  if [ -f "$file" ]; then
    echo -e "${GREEN}✓${NC} $file exists"
  else
    echo -e "${RED}✗${NC} $file missing"
  fi
done

# Check Docker
echo ""
echo "Checking Docker..."
if docker --version > /dev/null 2>&1; then
  echo -e "${GREEN}✓${NC} Docker installed: $(docker --version)"
  
  # Check if Docker daemon is running
  if docker info > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Docker daemon is running"
  else
    echo -e "${YELLOW}⚠${NC} Docker daemon is not running"
  fi
else
  echo -e "${RED}✗${NC} Docker not found"
fi

# Test Python imports
echo ""
echo "Testing Python environment..."
python3 -c "import sys; print(f'Python path: {sys.executable}')"

# Check if we can import required packages
echo ""
echo "Checking Python packages..."
python3 -c "
import sys
packages = ['fastapi', 'uvicorn', 'pytest', 'black', 'flake8']
for pkg in packages:
    try:
        __import__(pkg)
        print(f'✓ {pkg} installed')
    except ImportError:
        print(f'✗ {pkg} not installed')
" 2>/dev/null || echo "Some packages may not be installed yet"

# Check GitHub workflows
echo ""
echo "Checking GitHub workflows..."
for workflow in .github/workflows/*.yml; do
  if [ -f "$workflow" ]; then
    echo -e "${GREEN}✓${NC} Found workflow: $(basename $workflow)"
    # Basic YAML syntax check
    python3 -c "import yaml; yaml.safe_load(open('$workflow'))" 2>/dev/null && \
      echo "  └─ Valid YAML syntax" || \
      echo -e "  └─ ${YELLOW}Warning: Check YAML syntax${NC}"
  fi
done

echo ""
echo "=== Verification Complete ==="
echo ""
echo "Next steps:"
echo "1. Review any missing items above"
echo "2. Run: pip install -r config/requirements/dev.txt"
echo "3. Commit and push changes"
echo "4. Monitor GitHub Actions"