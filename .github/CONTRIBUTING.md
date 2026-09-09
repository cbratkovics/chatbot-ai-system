# Contributing Guide

Thank you for helping improve this project! Please read this guide before opening a PR.

## Project Overview

**Purpose:** A multi-provider AI chat service whose engineering is visible on screen: provider failover, an optional cache, SSE streaming, demo guardrails, and per-message telemetry. The public demo runs on Render + Vercel for ~$0/month; the repository also carries a larger full-deployment surface that the demo does not exercise.

**Core Values:**
- **Clarity** - Clear code and documentation
- **Reproducibility** - Consistent, reproducible builds and tests
- **Security** - No secrets in git
- **Evidence** - Every number in the README comes from a committed artifact

## Prerequisites

- **Python** 3.12+
- **Poetry** ≥ 2.0
- **Node.js** 20 LTS (for frontend)
- **Docker** (optional: only for `make up`; the API boots with no Redis or database)
- **Git** (for version control)

## Project Structure

```
├── src/chatbot_ai_system/   # backend package; demo path is api/, providers/, cache/, config/, server/
├── frontend/                # Next.js 15 UI
├── tests/                   # unit, integration, contract, e2e, load_testing
├── docs/                    # ADRs (docs/adr/), diagnosis, test triage, demo script, audits
├── docker/                  # backend Dockerfiles, docker-compose.prod.yml, nginx/ and redis/ configs
├── infrastructure/          # Terraform, Helm/k8s, monitoring: full deployment only
├── benchmarks/              # harnesses + committed results
├── scripts/                 # bench_demo.py
├── docker-compose.yml       # local dev stack (make up)
├── render.yaml              # Render blueprint for the demo backend
└── Makefile                 # make help lists every target
```

The README's "Project structure" section describes `src/chatbot_ai_system/` one level deeper.

## Local Development Setup

### Backend + Frontend Setup

```bash
git clone https://github.com/cbratkovics/chatbot-ai-system.git
cd chatbot-ai-system

make install                      # poetry install + (cd frontend && npm ci)
cp .env.example .env              # add OPENAI_API_KEY; GROQ_API_KEY enables failover
cp frontend/.env.example frontend/.env.local
poetry run pre-commit install     # optional

make dev                          # API on http://localhost:8000 (hot reload)
make dev-frontend                 # UI on http://localhost:3000, in a second terminal
```

Redis is optional. Without `REDIS_URL` the API uses its in-process cache and `/health` says
`cache: memory`. `make up` starts the full local stack in Docker if you want Redis and Postgres.

Visit:
- **Frontend:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs

## Quality Gates

Run these checks before pushing any changes:

```bash
make check            # ruff check + mypy src/ + pytest tests/  (what CI runs)
make build-frontend   # tsc --noEmit + next build
make test-cov         # pytest with coverage
make format           # ruff format
```

Tests that need a live service carry `@pytest.mark.live("<ENV_VAR>")` and skip unless
`TEST_BASE_URL`, `TEST_REDIS_URL`, or `TEST_DATABASE_URL` is set. Unit tests never touch Redis:
`tests/conftest.py` gives every test a fresh in-process cache.

**All checks should pass before opening a PR.**

## Branching Strategy

Create short-lived branches using these naming conventions:

- `feat/<topic>` - New features
- `fix/<bug>` - Bug fixes
- `docs/<page>` - Documentation updates
- `refactor/<area>` - Code refactoring
- `test/<scope>` - Test additions/modifications
- `chore/<task>` - Maintenance tasks

**Examples:**
- `feat/add-gemini-provider`
- `fix/redis-connection-timeout`
- `docs/update-deployment-guide`

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

**Examples:**
- `feat: add provider retry logic with exponential backoff`
- `fix: resolve WebSocket connection drops on idle`
- `docs: add ADR for provider failover policy`

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


## Configuration

Everything is an environment variable with a safe default, read by
`src/chatbot_ai_system/config/settings.py` (pydantic-settings). Env aliases are upper-case
(`DEFAULT_MODEL`); `.env` and real environment variables win over keyword arguments, so tests
construct `Settings(_env_file=None, DEFAULT_MODEL=...)` when they need an explicit value.

When adding an option:
1. Add the field with an env alias and a default that keeps the demo working without it.
2. Document it in `.env.example` (and `frontend/.env.example` for `NEXT_PUBLIC_*`).
3. Add it to `render.yaml` only if the demo needs a non-default value.
4. If it changes behaviour worth explaining in an interview, write an ADR in `docs/adr/`.

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
make evidence   # failover control-flow timing -> benchmarks/results/ (the committed artifact)
make bench      # 20 requests against the live demo -> benchmarks/results/bench_demo_latest.json
```

Plain test runs write to the gitignored `benchmarks/results/tmp/`; only these targets and
explicit scripts write to the committed files.

**Performance PR Requirements:**
- Baseline metrics (before changes)
- New metrics (after changes)
- Percentage improvement or regression
- Resource usage (CPU, memory, if relevant)

## Testing

### Test Structure
- `tests/unit/` - Unit tests (fast, hermetic; fake provider and in-process cache)
- `tests/integration/` - In-process integration tests; live-service ones are marked `live`
- `tests/e2e/` - End-to-end tests (full stack)
- `tests/load_testing/` - Performance/load tests
- `tests/contract/` - API contract tests

How the integration suite was triaged, and which known gaps are encoded as strict `xfail`s,
is in `docs/TEST_TRIAGE.md`.

### Writing Tests

```bash
make test                                        # everything
poetry run pytest tests/unit/test_provider_chain.py -q   # one file
make test-cov                                    # with coverage
TEST_BASE_URL=http://localhost:8000 poetry run pytest tests/integration/test_websocket_flow.py
```

### Test Guidelines
- Write tests for all new features
- Cover the demo path fully; measured line coverage for the whole package is reported in the README, not promised
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

# View logs from the local stack
make logs

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
