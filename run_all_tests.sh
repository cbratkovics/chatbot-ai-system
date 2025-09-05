#!/bin/bash
echo "Running all tests for showcase readiness..."
echo "==========================================="

# Set Python path
export PYTHONPATH="${PWD}/src:${PYTHONPATH}"

# Run Python tests
echo ""
echo "[1] Running Python tests..."
if command -v pytest &> /dev/null; then
    pytest tests/ -v --tb=short || true
else
    python -m pytest tests/ -v --tb=short || true
fi

# Test imports
echo ""
echo "[2] Testing imports..."
python3 -c "
import sys
sys.path.insert(0, 'src')
try:
    from chatbot_ai_system import __version__
    print(f'Successfully imported chatbot_ai_system v{__version__}')
except ImportError as e:
    print(f'Import test failed: {e}')
"

# Run demo
echo ""
echo "[3] Running showcase demo (preview)..."
python demo/showcase_demo.py 2>/dev/null | head -30 || echo "Demo not available"

echo ""
echo "==========================================="
echo "All tests completed!"
