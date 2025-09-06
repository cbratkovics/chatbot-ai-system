# Contributing Guide

Thanks for helping improve this project. Please read this quick guide before opening a PR.

## 1) Project expectations
- Purpose: production-ready, multi-tenant AI chat system with provider orchestration, streaming, caching, and full observability.
- Values: clarity, reproducibility, security (no secrets in git), and evidence-backed claims.

## 2) Prerequisites
- Python 3.11, Poetry >= 1.7
- Node 18 LTS (for `frontend/`)
- Docker (optional, for Redis and local infra)

## 3) Local setup (backend + frontend)
```bash
poetry install
pre-commit install
docker compose up -d redis         # or: docker run -p 6379:6379 redis:7-alpine
poetry run uvicorn chatbot_ai_system.server.main:app --reload
# in another terminal
cd frontend && npm ci && npm run dev
4) Quality gates (run before pushing)
bash
Copy code
pre-commit run -a                  # formatters/linters configured in repo
poetry run flake8                  # style
poetry run mypy src/ --ignore-missing-imports   # types (informational)
poetry run pytest -q               # tests
5) Branching and commits
Create short-lived branches: feat/<topic>, fix/<bug>, docs/<page>, chore/<task>.

Use Conventional Commits:

feat: …, fix: …, docs: …, refactor: …, test: …, chore: …, ci: …, perf: ….

6) Pull requests
Keep PRs focused and under ~400 lines when possible.

Include: summary, rationale, screenshots (UI) or links to evidence (benchmarks/results JSON).

Update docs if behavior, config, or claims change (README.md, docs/*).

Ensure CI passes; unresolved conversations block merge.

7) Security and secrets
Never commit API keys or credentials. Use .env.example for variables and GitHub Actions secrets for CI.

If you suspect a leak, rotate the key and open a security disclosure via a private issue.

8) Reproducible benchmarks (optional for feature PRs)
bash
Copy code
poetry run python benchmarks/run_all_benchmarks.py
# results written to benchmarks/results/*.json – reference them in the PR
9) Getting help
Open a GitHub Issue with a minimal reproducible example (logs, steps, expected vs actual).
