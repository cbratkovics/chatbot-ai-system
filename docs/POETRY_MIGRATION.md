# Poetry Migration Guide

## Overview

This guide documents the migration from `requirements.txt` to Poetry for dependency management in the AI Chatbot System. Poetry provides better dependency resolution, lock files, and environment management specifically optimized for AI/ML workloads.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Migration Process](#migration-process)
3. [Project Structure](#project-structure)
4. [Dependency Management](#dependency-management)
5. [GPU/CPU Optimization](#gpucpu-optimization)
6. [Docker Integration](#docker-integration)
7. [CI/CD Updates](#cicd-updates)
8. [Monitoring & Health](#monitoring--health)
9. [Troubleshooting](#troubleshooting)
10. [Rollback Procedure](#rollback-procedure)

## Prerequisites

### Required Tools

- Python 3.11+
- Poetry 1.7.1+
- Docker (for containerization)
- Git (for version control)

### Installation

```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 - --version 1.7.1

# Add to PATH
export PATH="$HOME/.local/bin:$PATH"

# Verify installation
poetry --version
```

## Migration Process

### Step 1: Backup Current Setup

```bash
# Run migration script with backup
python scripts/migrate_to_poetry.py

# Or manual backup
cp -r config/requirements config/requirements.backup
cp pyproject.toml pyproject.toml.backup 2>/dev/null || true
```

### Step 2: Initialize Poetry

```bash
# The migration script handles this automatically
# For manual setup:
poetry init --no-interaction
poetry add $(cat config/requirements/base.txt | grep -v '^#' | cut -d'=' -f1)
```

### Step 3: Configure Dependency Groups

Poetry uses dependency groups to organize packages:

```toml
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.109.0"
uvicorn = {extras = ["standard"], version = "^0.25.0"}

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.3"
black = "^23.11.0"
mypy = "^1.7.0"

[tool.poetry.group.ml-cpu]
optional = true

[tool.poetry.group.ml-cpu.dependencies]
torch = {version = "^2.1.0+cpu", source = "pytorch-cpu"}
tensorflow-cpu = "^2.15.0"

[tool.poetry.group.ml-gpu]
optional = true

[tool.poetry.group.ml-gpu.dependencies]
torch = {version = "^2.1.0+cu121", source = "pytorch-gpu"}
tensorflow = {extras = ["cuda"], version = "^2.15.0"}
```

### Step 4: Generate Lock File

```bash
# Generate poetry.lock
poetry lock

# Install dependencies
poetry install
```

### Step 5: Export Compatibility Files

```bash
# Generate backward-compatible requirements.txt files
./scripts/compatibility_bridge.sh

# This creates:
# - config/requirements/base.txt
# - config/requirements/dev.txt
# - config/requirements/prod.txt
```

## Project Structure

```
ai-chatbot-system/
├── pyproject.toml           # Poetry configuration
├── poetry.lock              # Lock file with exact versions
├── scripts/
│   ├── migrate_to_poetry.py      # Migration script
│   ├── dependency_manager.py     # Intelligent dependency management
│   ├── dependency_health_monitor.py  # Health monitoring
│   ├── dependency_visualizer.py  # Dependency graphs
│   └── compatibility_bridge.sh   # Backward compatibility
├── config/
│   ├── docker/
│   │   └── dockerfiles/
│   │       └── Dockerfile.poetry  # Multi-stage Docker build
│   ├── requirements/            # Backward compatibility
│   │   ├── base.txt
│   │   ├── dev.txt
│   │   └── prod.txt
│   └── dependencies/
│       └── constraints.txt      # Version constraints
└── .github/
    └── workflows/
        └── main-poetry.yml      # CI/CD with Poetry
```

## Dependency Management

### Installing Dependencies

```bash
# Install all dependencies
poetry install

# Install with specific groups
poetry install --with dev
poetry install --with ml-gpu

# Install only production dependencies
poetry install --only main

# Install in production (no dev dependencies)
poetry install --only main --no-root
```

### Adding New Dependencies

```bash
# Add to main dependencies
poetry add fastapi

# Add to dev group
poetry add --group dev pytest

# Add to optional ML group
poetry add --group ml-gpu torch

# Add with specific version
poetry add "numpy@^1.26.0"

# Add from specific source
poetry add --source pytorch-gpu torch
```

### Updating Dependencies

```bash
# Update all dependencies
poetry update

# Update specific package
poetry update numpy

# Update within constraints
poetry update --dry-run  # Preview changes

# Generate updated requirements.txt
./scripts/compatibility_bridge.sh
```

### Removing Dependencies

```bash
# Remove package
poetry remove requests

# Remove from specific group
poetry remove --group dev pytest-mock
```

## GPU/CPU Optimization

### Automatic Detection

```bash
# Detect compute environment and optimize
python scripts/dependency_manager.py optimize --environment auto

# Force specific environment
python scripts/dependency_manager.py optimize --environment cuda --profile production
```

### Manual Configuration

```bash
# For CPU-only environments
poetry install --with ml-cpu

# For CUDA GPU environments
poetry install --with ml-gpu

# For Apple Silicon (MPS)
poetry install --with ml-mps

# For edge deployment
poetry install --only main --with edge
```

### Environment Detection Logic

The system automatically detects:
- **CUDA**: NVIDIA GPUs with CUDA support
- **ROCm**: AMD GPUs with ROCm support
- **MPS**: Apple Silicon Metal Performance Shaders
- **CPU**: Fallback for CPU-only environments

## Docker Integration

### Multi-Stage Builds

```dockerfile
# Development
docker build --target development -t app:dev .

# Production
docker build --target production -t app:prod .

# ML with GPU
docker build --target ml-gpu -t app:ml-gpu .

# Edge deployment
docker build --target edge -t app:edge .
```

### Docker Compose

```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: config/docker/dockerfiles/Dockerfile.poetry
      target: ${BUILD_TARGET:-production}
    environment:
      - POETRY_VIRTUALENVS_CREATE=false
```

## CI/CD Updates

### GitHub Actions Workflow

The updated workflow (`main-poetry.yml`) includes:

1. **Dependency Caching**
   ```yaml
   - uses: actions/cache@v3
     with:
       path: |
         ~/.cache/pypoetry
         .venv
       key: poetry-${{ runner.os }}-${{ hashFiles('**/poetry.lock') }}
   ```

2. **Security Scanning**
   ```yaml
   - name: Security scan
     run: |
       poetry run pip-audit --format json > security-report.json
   ```

3. **Weekly Updates**
   ```yaml
   on:
     schedule:
       - cron: '0 0 * * 1'  # Weekly on Monday
   ```

## Monitoring & Health

### Health Check Commands

```bash
# Analyze dependency health
python scripts/dependency_health_monitor.py analyze

# Start continuous monitoring
python scripts/dependency_health_monitor.py monitor --interval 24

# Generate dependency graph
python scripts/dependency_visualizer.py visualize

# Check for circular dependencies
python scripts/dependency_visualizer.py check-cycles

# Check for security vulnerabilities
python scripts/dependency_manager.py check-security
```

### Automated Reports

Reports are generated in `dependency_reports/`:
- `latest_report.json` - Latest health report
- `graphs/dependency_graph.html` - Interactive visualization
- `graphs/dependency_analysis.md` - Analysis report

### Health Metrics

The system tracks:
- **Version Currency**: How outdated packages are
- **Security Score**: Known vulnerabilities
- **Maintenance Score**: Release frequency
- **Popularity Score**: Community adoption
- **Dependency Depth**: Maximum dependency chain

## Troubleshooting

### Common Issues

#### 1. Poetry Not Found

```bash
# Add Poetry to PATH
export PATH="$HOME/.local/bin:$PATH"

# Or use Python module
python3 -m poetry --version
```

#### 2. Dependency Conflicts

```bash
# Clear cache and retry
poetry cache clear pypi --all
poetry lock --no-update
poetry install
```

#### 3. Lock File Out of Sync

```bash
# Regenerate lock file
rm poetry.lock
poetry lock
```

#### 4. GPU Libraries Not Installing

```bash
# Add PyTorch source
poetry source add pytorch https://download.pytorch.org/whl/cu121

# Install with source
poetry add --source pytorch torch
```

#### 5. Slow Dependency Resolution

```bash
# Use experimental installer
poetry config experimental.new-installer true
poetry install
```

### Validation Commands

```bash
# Validate pyproject.toml
poetry check

# Verify installation
poetry show

# Check environment
poetry env info

# List available environments
poetry env list
```

## Rollback Procedure

If issues arise, rollback to requirements.txt:

### Automatic Rollback

```bash
# If migration script was used
.migration_backup/restore.sh
```

### Manual Rollback

```bash
# Restore requirements files
cp config/requirements.backup/* config/requirements/

# Remove Poetry files
rm poetry.lock pyproject.toml

# Install with pip
pip install -r config/requirements/base.txt
pip install -r config/requirements/dev.txt
```

### Gradual Migration

For zero-downtime migration:

1. **Maintain Both Systems**
   ```bash
   # Keep requirements.txt updated
   ./scripts/compatibility_bridge.sh watch
   ```

2. **Test Poetry in Parallel**
   ```bash
   # Create Poetry environment
   poetry install
   poetry shell
   # Test application
   ```

3. **Switch When Ready**
   - Update CI/CD to use Poetry
   - Update Docker builds
   - Update documentation

## Best Practices

### 1. Version Pinning

```toml
# Prefer caret for libraries
fastapi = "^0.109.0"  # >=0.109.0, <0.110.0

# Pin for applications
uvicorn = "0.25.0"  # Exact version

# Use tilde for patches
numpy = "~1.26.0"  # >=1.26.0, <1.27.0
```

### 2. Source Management

```toml
[[tool.poetry.source]]
name = "pytorch-gpu"
url = "https://download.pytorch.org/whl/cu121"
priority = "supplemental"
```

### 3. Lock File Management

- Always commit `poetry.lock`
- Update regularly but carefully
- Test after updates
- Use `--dry-run` first

### 4. Environment Isolation

```bash
# Create project-specific virtualenv
poetry config virtualenvs.in-project true

# Use Python version
poetry env use python3.11
```

### 5. Security Practices

- Run security scans weekly
- Monitor dependency health
- Update vulnerable packages immediately
- Use constraints for stability

## Performance Optimization

### 1. Parallel Installation

```bash
poetry config installer.parallel true
poetry install
```

### 2. Minimal Installs

```bash
# Production without dev tools
poetry install --only main --no-root

# Edge deployment with minimal deps
poetry install --only main --with edge --no-dev
```

### 3. Cache Optimization

```bash
# Pre-download packages
poetry export -f requirements.txt | pip download -d ./cache -r -

# Use in Docker
COPY cache /tmp/cache
RUN pip install --find-links /tmp/cache --no-index -r requirements.txt
```

## Support

For issues or questions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Run diagnostics: `poetry check && poetry env info`
3. Review logs in `dependency_reports/`
4. Check Poetry documentation: https://python-poetry.org/docs/

## Appendix

### Environment Variables

```bash
# Poetry configuration
export POETRY_HOME="/opt/poetry"
export POETRY_VIRTUALENVS_IN_PROJECT=true
export POETRY_NO_INTERACTION=1

# Python optimization
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1
```

### Useful Aliases

```bash
# Add to ~/.bashrc or ~/.zshrc
alias pi="poetry install"
alias pa="poetry add"
alias pr="poetry remove"
alias pu="poetry update"
alias ps="poetry show"
alias psh="poetry shell"
```

### Migration Checklist

- [ ] Backup current requirements
- [ ] Install Poetry
- [ ] Run migration script
- [ ] Validate Poetry configuration
- [ ] Generate lock file
- [ ] Test installation
- [ ] Update CI/CD
- [ ] Update Docker builds
- [ ] Update documentation
- [ ] Monitor dependency health
- [ ] Train team on Poetry usage

---

*Last Updated: 2024*
*Version: 1.0.0*