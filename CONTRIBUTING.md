# Contributing Guide

Thank you for helping improve this project! Please read this guide before opening a PR.

## Project Overview

**Purpose:** Production-ready, multi-tenant AI chat system with provider orchestration, streaming, caching, and full observability.

**Core Values:**
- **Clarity** - Clear code and documentation
- **Reproducibility** - Consistent, reproducible builds and tests
- **Security** - No secrets in git
- **Evidence** - Data-backed claims and benchmarks

## Prerequisites

- **Python** 3.11+
- **Poetry** ≥ 1.7
- **Node.js** 18 LTS (for frontend)
- **Docker** (optional, for Redis and local infrastructure)

## Local Development Setup

### Backend + Frontend Setup

```bash
# Install dependencies
poetry install
pre-commit install

# Start Redis (choose one option)
docker compose up -d redis
# OR
docker run -p 6379:6379 redis:7-alpine

# Start backend server
poetry run uvicorn chatbot_ai_system.server.main:app --reload

# In another terminal, start frontend
cd frontend
npm ci
npm run dev
```

## Quality Gates

Run these checks before pushing any changes:

```bash
# Run all pre-commit hooks (formatters/linters)
pre-commit run -a

# Style checking
poetry run flake8

# Type checking (informational)
poetry run mypy src/ --ignore-missing-imports

# Run tests
poetry run pytest -q
```

## Branching Strategy

Create short-lived branches using these naming conventions:

- `feat/<topic>` - New features
- `fix/<bug>` - Bug fixes
- `docs/<page>` - Documentation updates
- `refactor/<area>` - Code refactoring
- `test/<scope>` - Test additions/modifications
- `chore/<task>` - Maintenance tasks

## Commit Conventions

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Test additions/modifications
- `chore:` Maintenance tasks
- `ci:` CI/CD changes
- `perf:` Performance improvements

**Example:** `feat: add provider retry logic with exponential backoff`

## Pull Request Guidelines

### PR Best Practices

- **Keep PRs focused** - Single concern per PR
- **Size limit** - Aim for under ~400 lines when possible
- **CI must pass** - All checks green before merge
- **Review required** - Unresolved conversations block merge

### PR Description Template

Your PR should include:

1. **Summary** - What changes were made
2. **Rationale** - Why these changes are needed
3. **Evidence** - Screenshots (UI changes) or benchmark results
4. **Documentation** - Update relevant docs if behavior changes

### Documentation Updates

Update these files when applicable:
- `README.md` - Major features or setup changes
- `docs/*` - Detailed documentation changes

## Security

### Secrets Management

- **Never commit** API keys, tokens, or credentials
- **Use `.env.example`** for environment variable templates
- **Use GitHub Secrets** for CI/CD variables

### Security Incident Response

If you suspect a leaked credential:
1. **Rotate the key immediately**
2. **Open a security disclosure** via private issue
3. **Notify maintainers** directly

## Performance Benchmarks

For performance-related PRs, include benchmark results:

```bash
# Run all benchmarks
poetry run python benchmarks/run_all_benchmarks.py

# Results saved to benchmarks/results/*.json
# Reference these in your PR description
```

## Getting Help

### Reporting Issues

When opening an issue, include:

- **Minimal reproducible example**
- **Environment details** (OS, Python version, etc.)
- **Relevant logs** with error messages
- **Steps to reproduce**
- **Expected vs actual behavior**

### Contact

- **GitHub Issues** - Bug reports and feature requests
- **Discussions** - General questions and ideas
- **Security Issues** - Use private disclosure for vulnerabilities

---

Thank you for contributing! Your efforts help make this project better for everyone.
