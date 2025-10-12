# Contributing Guide

Thank you for helping improve this project! Please read this guide before opening a PR.

## Project Overview

**Purpose:** Production-ready, multi-tenant AI chat system with provider orchestration, streaming, caching, and full observability. Built as a reusable template for multiple use cases.

**Core Values:**
- **Clarity** - Clear code and documentation
- **Reproducibility** - Consistent, reproducible builds and tests
- **Security** - No secrets in git
- **Evidence** - Data-backed claims and benchmarks
- **Reusability** - Template-first design for easy customization

## Prerequisites

- **Python** 3.12+
- **Poetry** ≥ 1.7
- **Node.js** 20 LTS (for frontend)
- **Docker** (optional, for Redis and local infrastructure)
- **Git** (for version control)

## Project Structure

```
├── src/chatbot_ai_system/      # Backend: FastAPI, providers, caching
│   └── config/                 # Configuration system (new!)
├── frontend/                   # Next.js TypeScript UI
│   └── config/                 # Frontend config extraction (new!)
├── use-cases/                  # Template configurations (new!)
│   └── customer-support/       # Example: Customer support template
├── tests/                      # Unit, integration, e2e, load tests
├── benchmarks/                 # Performance benchmarking
├── docs/                       # Documentation
└── scripts/                    # Automation and utilities
```

## Local Development Setup

### Backend + Frontend Setup

```bash
# 1. Clone and navigate
git clone https://github.com/cbratkovics/chatbot-ai-system.git
cd chatbot-ai-system

# 2. Install dependencies
poetry install

# 3. Set up environment
cp .env.example .env
# Add your API keys to .env

# 4. Install pre-commit hooks
poetry run pre-commit install

# 5. Start Redis (choose one)
docker compose up -d redis
# OR
docker run -p 6379:6379 redis:7-alpine

# 6. Start backend server
poetry run uvicorn chatbot_ai_system.server.main:app --reload

# 7. In another terminal, start frontend
cd frontend
cp .env.example .env.local
# Configure frontend URLs in .env.local
npm ci
npm run dev
```

Visit:
- **Frontend:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs

## Quality Gates

Run these checks before pushing any changes:

```bash
# Run all pre-commit hooks (formatters/linters)
poetry run pre-commit run -a

# Lint with ruff
poetry run ruff check .

# Type checking
poetry run mypy src/ --ignore-missing-imports

# Run tests
poetry run pytest tests/ -v

# Check test coverage
poetry run pytest --cov=src --cov-report=term
```

**All checks should pass before opening a PR.**

## Branching Strategy

Create short-lived branches using these naming conventions:

- `feat/<topic>` - New features
- `fix/<bug>` - Bug fixes
- `docs/<page>` - Documentation updates
- `refactor/<area>` - Code refactoring
- `test/<scope>` - Test additions/modifications
- `chore/<task>` - Maintenance tasks
- `template/<use-case>` - New use-case templates

**Examples:**
- `feat/add-gemini-provider`
- `fix/redis-connection-timeout`
- `docs/update-deployment-guide`
- `template/code-assistant`

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
- `template:` New or updated use-case template

**Examples:**
- `feat: add provider retry logic with exponential backoff`
- `fix: resolve WebSocket connection drops on idle`
- `docs: add configuration guide for use-case templates`
- `template: add education-tutor use case`

## Pull Request Guidelines

### PR Best Practices

- **Keep PRs focused** - Single concern per PR
- **Size limit** - Aim for under ~400 lines when possible
- **CI must pass** - All checks green before merge
- **Review required** - At least one approval needed
- **Unresolved conversations block merge**
- **Update docs** - If behavior changes, update relevant documentation

### PR Description Template

Your PR should include:

1. **Summary** - What changes were made (2-3 sentences)
2. **Rationale** - Why these changes are needed
3. **Testing** - How you tested the changes
4. **Evidence** - Screenshots (UI changes) or benchmark results (performance)
5. **Documentation** - List of docs updated or "N/A - no user-facing changes"
6. **Breaking Changes** - Note any breaking changes or "None"

**Example:**

```markdown
## Summary
Adds retry logic with exponential backoff for OpenAI provider to handle rate limits gracefully.

## Rationale
Current implementation fails immediately on 429 errors. This causes poor UX during high-traffic periods.

## Testing
- Added unit tests for retry logic
- Tested manually with rate-limited API key
- Load test shows 99% success rate vs 60% before

## Evidence
See benchmarks/results/retry-comparison.json

## Documentation
Updated docs/providers.md with retry configuration

## Breaking Changes
None - backward compatible, retry is opt-in via config
```

### Documentation Updates

Update these files when applicable:
- `README.md` - Major features or setup changes
- `docs/` - Detailed guides and architecture docs
- `.env.example` - New environment variables
- `frontend/.env.example` - New frontend configuration options

## Contributing Templates (New!)

We welcome new use-case templates! Each template should demonstrate a specific chatbot application.

### Creating a New Template

1. **Create directory structure:**
```bash
mkdir -p use-cases/your-use-case
cd use-cases/your-use-case
```

2. **Add required files:**
```
your-use-case/
├── .env.example           # Complete configuration
├── system-prompt.txt      # Customized system prompt
├── theme.config.ts        # (Optional) UI theme overrides
└── README.md             # Setup and customization guide
```

3. **Follow the pattern:**
- Study existing templates (e.g., `customer-support/`)
- Include clear setup instructions
- Document all customization points
- Add example interactions
- Include disclaimers if needed (e.g., medical, legal advice)

4. **Test thoroughly:**
```bash
# Test with the template configuration
cp use-cases/your-use-case/.env.example .env
# Add API keys
poetry run uvicorn chatbot_ai_system.server.main:app --reload
# Verify behavior matches intended use case
```

5. **Open PR with:**
- Template files
- Updated `docs/USE_CASES.md` (if exists)
- Screenshots or demo interactions

### Template Guidelines

- **System prompts** should be specific and actionable
- **Include safety guardrails** for sensitive use cases
- **Document limitations** clearly
- **Provide customization examples**
- **Use appropriate tone** for the use case

## Configuration System

This project uses environment-based configuration for flexibility.

### Backend Configuration
Located in `src/chatbot_ai_system/config/use_case_config.py`:

```python
from chatbot_ai_system.config import use_case_config

# Access configuration
print(use_case_config.USE_CASE_NAME)
print(use_case_config.ALLOWED_MODELS)
```

### Frontend Configuration
Located in `frontend/config/app.config.ts`:

```typescript
import { AppConfig } from '@/config/app.config';

// Use configuration
const apiUrl = AppConfig.api.baseURL;
const appName = AppConfig.branding.name;
```

When adding new configuration options:
1. Add to the appropriate config file
2. Update `.env.example` files
3. Document in `docs/CONFIGURATION.md` (if exists)
4. Provide sensible defaults

## Security

### Secrets Management

- **Never commit** API keys, tokens, or credentials
- **Use `.env.example`** for environment variable templates
- **Add secrets to `.gitignore`** (already configured)
- **Use GitHub Secrets** for CI/CD variables
- **Rotate compromised keys immediately**

### Security Incident Response

If you suspect a leaked credential:
1. **Rotate the key immediately** in your provider dashboard
2. **Open a private security advisory** on GitHub
3. **Notify maintainers** directly
4. **Document the incident** (without exposing the secret)

### Security Review Checklist

For security-related PRs:
- [ ] No secrets in code or config files
- [ ] Input validation on all user inputs
- [ ] Rate limiting for API endpoints
- [ ] Authentication/authorization checked
- [ ] Dependencies scanned for vulnerabilities
- [ ] Error messages don't leak sensitive info

## Performance Benchmarks

For performance-related PRs, include benchmark results:

```bash
# Run specific benchmarks
poetry run python benchmarks/run_all_benchmarks.py

# Results saved to benchmarks/results/*.json
# Include before/after comparison in PR description
```

**Performance PR Requirements:**
- Baseline metrics (before changes)
- New metrics (after changes)
- Percentage improvement or regression
- Resource usage (CPU, memory, if relevant)

## Testing

### Test Structure
- `tests/unit/` - Unit tests (fast, isolated)
- `tests/integration/` - Integration tests (with Redis, DB)
- `tests/e2e/` - End-to-end tests (full stack)
- `tests/load_testing/` - Performance/load tests
- `tests/contract/` - API contract tests

### Writing Tests

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/unit/test_providers.py

# Run with coverage
poetry run pytest --cov=src --cov-report=html

# Run only fast tests
poetry run pytest -m "not slow"
```

### Test Guidelines
- Write tests for all new features
- Maintain >80% code coverage
- Use fixtures for common setup
- Mock external API calls
- Add integration tests for critical paths

## Getting Help

### Reporting Issues

Use our issue templates for:
- **Bug Reports** - Include minimal reproducible example
- **Feature Requests** - Describe use case and benefits

When opening an issue, include:

- **Environment details** (OS, Python version, Node version)
- **Relevant logs** with error messages
- **Steps to reproduce**
- **Expected vs actual behavior**
- **Screenshots** (for UI issues)

### Contact

- **GitHub Issues** - Bug reports and feature requests
- **GitHub Discussions** - General questions and ideas
- **Security Issues** - Use private security advisories
- **Code of Conduct** - See CODE_OF_CONDUCT.md for community guidelines

## Development Tips

### Hot Reload
Both backend and frontend support hot reload:
- **Backend:** `uvicorn` with `--reload` flag
- **Frontend:** `npm run dev` (Next.js Fast Refresh)

### Debugging
```bash
# Backend debugging with breakpoints
poetry run python -m debugpy --listen 5678 --wait-for-client -m uvicorn chatbot_ai_system.server.main:app

# View logs
docker compose logs -f

# Check Redis
docker exec -it redis redis-cli
```

### Database Migrations
```bash
# Create migration
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Rollback
poetry run alembic downgrade -1
```

## Code Style

### Python
- Follow PEP 8
- Use type hints
- Docstrings for public APIs
- Max line length: 100 characters
- Use `ruff` for linting and formatting

### TypeScript
- Follow React/Next.js conventions
- Use TypeScript strict mode
- Functional components with hooks
- Props interfaces for all components
- Max line length: 100 characters

### General
- Descriptive variable names
- Comments for complex logic
- Keep functions small and focused
- DRY (Don't Repeat Yourself)

## Release Process

(For maintainers)

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create release branch: `release/v1.x.x`
4. Open PR to main
5. After merge, tag release: `git tag v1.x.x`
6. Push tag: `git push origin v1.x.x`
7. GitHub Actions will build and publish

---

## Recognition

Contributors are recognized in:
- Project README
- Release notes
- GitHub contributors page

Thank you for contributing! Your efforts help make this project better for everyone.
