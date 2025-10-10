# Poetry Setup Guide

This project uses Poetry for dependency management. Poetry provides deterministic builds, lock file support, and virtual environment management.

## Installation

### Prerequisites
- Python 3.11+
- Poetry 2.0+

### Install Poetry
```bash
# Using the official installer (recommended)
curl -sSL https://install.python-poetry.org | python3 -

# Or using pip
pip install poetry
```

## Project Setup

### 1. Install Dependencies
```bash
# Install all dependencies (including dev)
poetry install

# Install only production dependencies
poetry install --only main

# Sync with lock file (recommended for CI/CD)
poetry sync
```

### 2. Virtual Environment

Poetry automatically creates and manages a virtual environment:

```bash
# Activate the virtual environment
poetry shell

# Run commands within the environment
poetry run python api/main.py

# Show environment info
poetry env info
```

## Common Commands

### Dependency Management
```bash
# Add a new dependency
poetry add package-name

# Add a dev dependency
poetry add --group dev package-name

# Update dependencies
poetry update

# Show dependency tree
poetry show --tree

# Export requirements.txt (for compatibility)
poetry export -f requirements.txt --output requirements.txt
```

### Running the Application
```bash
# Using Poetry run
poetry run uvicorn api.main:app --host 0.0.0.0 --port 8000

# Or use the Makefile targets
make run          # Runs with Poetry
make dev-run      # Runs with hot reload
make test         # Runs tests with Poetry
```

### Scripts

The project defines several Poetry scripts in `pyproject.toml`:

```bash
# Run the API
poetry run rag-api

# Run document ingestion
poetry run rag-ingest

# Run RAGAS evaluation
poetry run rag-eval
```

## Makefile Integration

All Makefile targets are configured to use Poetry:

```bash
make setup        # Poetry install with sync
make install      # Install dependencies
make update       # Update dependencies
make lock         # Regenerate lock file
make show-deps    # Show dependency tree
```

## Troubleshooting

### Platform-Specific Issues

Some dependencies (like ChromaDB) may have platform-specific build requirements:

**macOS (Apple Silicon)**:
```bash
# If you encounter build errors with chroma-hnswlib
export HNSWLIB_NO_NATIVE=1
poetry install
```

**Linux**:
```bash
# Install build dependencies
sudo apt-get install python3-dev build-essential
poetry install
```

**Windows**:
```bash
# Use WSL2 or install Visual Studio Build Tools
poetry install
```

### Lock File Conflicts

If you encounter lock file issues:

```bash
# Regenerate the lock file
poetry lock --no-cache

# Force reinstall
poetry install --sync --no-cache
```

### Virtual Environment Issues

```bash
# Remove existing environment
poetry env remove python

# Create new environment
poetry env use python3.11

# Reinstall
poetry install
```

## CI/CD Integration

For CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Install Poetry
  uses: snok/install-poetry@v1
  with:
    version: 2.1.4
    
- name: Install dependencies
  run: poetry install --sync

- name: Run tests
  run: poetry run pytest
```

## Benefits of Poetry

1. **Deterministic Builds**: `poetry.lock` ensures everyone gets the same dependencies
2. **Virtual Environment Management**: Automatic isolation of project dependencies
3. **Dependency Resolution**: Intelligent conflict resolution
4. **Scripts**: Define custom commands in pyproject.toml
5. **Publishing**: Easy package publishing to PyPI
6. **Groups**: Separate dev, test, and production dependencies

## Additional Resources

- [Poetry Documentation](https://python-poetry.org/docs/)
- [Poetry CLI Reference](https://python-poetry.org/docs/cli/)
- [Managing Dependencies](https://python-poetry.org/docs/dependency-specification/)
- [pyproject.toml Specification](https://python-poetry.org/docs/pyproject/)