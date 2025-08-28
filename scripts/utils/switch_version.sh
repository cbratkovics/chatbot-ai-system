#!/bin/bash

# Script to switch between main and demo versions

echo "🔄 AI Chatbot Version Switcher"
echo "=============================="
echo ""

# Check current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"
echo ""

# Show options
echo "Available versions:"
echo "1) main - Full enterprise system"
echo "2) demo - Streamlined demo version"
echo "3) Exit"
echo ""

read -p "Select version (1-3): " choice

case $choice in
    1)
        echo "Switching to main branch (full system)..."
        git checkout main
        echo ""
        echo "✅ Switched to main branch"
        echo "This version includes:"
        echo "- Full enterprise features"
        echo "- Complete test suites"
        echo "- Kubernetes configurations"
        echo "- FinOps dashboards"
        echo "- Benchmarking tools"
        ;;
    2)
        echo "Switching to demo branch (streamlined)..."
        git checkout demo
        echo ""
        echo "✅ Switched to demo branch"
        echo "This version includes:"
        echo "- Simplified setup (5 minutes)"
        echo "- One-command deployment"
        echo "- Essential features only"
        echo "- Optimized for sharing"
        echo ""
        echo "To deploy: ./setup_demo.sh"
        ;;
    3)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "To see differences between versions:"
echo "  git diff main..demo --stat"