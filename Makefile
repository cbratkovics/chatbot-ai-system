# chatbot-ai-system developer targets. `make` alone lists them.
.DEFAULT_GOAL := help
.PHONY: help install dev dev-frontend test test-cov lint format typecheck check build-frontend demo verify-static \
        up up-full down logs docker-build bench evidence evals clean

POETRY   := poetry
COMPOSE  := docker compose
DEV_COMPOSE  := docker-compose.yml
FULL_COMPOSE := docker/docker-compose.prod.yml

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ---- setup -------------------------------------------------------------------
install: ## Install backend (Poetry) and frontend (npm ci) dependencies
	$(POETRY) install
	cd frontend && npm ci

# ---- run ---------------------------------------------------------------------
dev: ## Run the API with hot reload on :8000 (no Redis or keys needed to boot)
	$(POETRY) run uvicorn chatbot_ai_system.server.main:app --reload --host 0.0.0.0 --port 8000 --timeout-keep-alive 65

dev-frontend: ## Preview the static project UI in development on :3000 (no backend)
	cd frontend && npm run dev

# ---- quality gates ----------------------------------
lint: ## ruff check
	$(POETRY) run ruff check .

format: ## ruff format (rewrites files)
	$(POETRY) run ruff format .

typecheck: ## mypy over src/
	$(POETRY) run mypy src/ --ignore-missing-imports

test: ## Offline pytest; live tests require ALLOW_LIVE_TESTS=1 plus their TEST_* target
	$(POETRY) run pytest tests/ -q

test-cov: ## pytest with line coverage (writes coverage.xml)
	$(POETRY) run pytest tests/ -q --cov=chatbot_ai_system --cov-report=term --cov-report=xml

build-frontend: ## Type-check and export the public static site
	cd frontend && npm run typecheck && npm run build

demo: build-frontend ## Build and serve out/ on :3000; no backend or model keys
	cd frontend && npm start

verify-static: ## Offline frontend release gates and browser audit of out/
	cd frontend && npm run lint && npm test && npm run typecheck && npm run build && npm run test:browser

check: lint typecheck test ## lint + typecheck + test

# ---- containers ----------------------------------------------------------------
up: ## Local dev stack (backend, frontend, redis, postgres) from docker-compose.yml
	$(COMPOSE) -f $(DEV_COMPOSE) up -d --build

up-full: ## Full-deployment stack (adds nginx, prometheus, grafana) from docker/docker-compose.prod.yml
	$(COMPOSE) -f $(FULL_COMPOSE) up -d --build

down: ## Stop whichever stack is running
	-$(COMPOSE) -f $(DEV_COMPOSE) down
	-$(COMPOSE) -f $(FULL_COMPOSE) down

logs: ## Tail dev-stack logs
	$(COMPOSE) -f $(DEV_COMPOSE) logs -f

docker-build: ## Optional local backend image build (no deploy)
	docker build -f docker/dockerfiles/Dockerfile -t chatbot-ai-system:dev .

# ---- evidence ------------------------------------------------------------------
bench: ## OPTIONAL provider calls; set BENCH_ARGS to an explicit local target (may cost money)
	@test -n "$(BENCH_ARGS)" || (echo "Supply explicit local --base-url via BENCH_ARGS; provider charges may apply."; exit 1)
	$(POETRY) run python scripts/bench_demo.py $(BENCH_ARGS)

evidence: ## Failover control-flow timing; writes the committed benchmarks/results/ files
	BENCHMARK_RESULTS_DIR=benchmarks/results $(POETRY) run pytest tests/test_provider_failover.py -q

EVALS_BASE_URL ?= http://localhost:8000
evals: ## OPTIONAL provider calls (may cost money); system evals -> evals/results/latest.{json,md}. Backend needs DEMO_GUARDRAILS_ENABLED=false RATE_LIMIT_ENABLED=false
	$(POETRY) run python -m evals.run --base-url $(EVALS_BASE_URL) $(EVALS_ARGS)

# ---- housekeeping ----------------------------------------------------------------
clean: ## Remove caches and build/coverage output
	rm -rf dist/ build/ *.egg-info htmlcov/ .coverage coverage.xml backups/ benchmarks/results/tmp/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/ frontend/.next
	find . -type d -name __pycache__ -not -path './.venv/*' -not -path '*/node_modules/*' -exec rm -rf {} +
