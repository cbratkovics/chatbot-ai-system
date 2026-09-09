# chatbot-ai-system developer targets. `make` alone lists them.
.DEFAULT_GOAL := help
.PHONY: help install dev dev-frontend test test-cov lint format typecheck check build-frontend \
        up up-full down logs docker-build bench evidence clean

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
	$(POETRY) run uvicorn chatbot_ai_system.server.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Run the Next.js dev server on :3000
	cd frontend && npm run dev

# ---- quality gates (the same four CI runs) ----------------------------------
lint: ## ruff check
	$(POETRY) run ruff check .

format: ## ruff format (rewrites files)
	$(POETRY) run ruff format .

typecheck: ## mypy over src/
	$(POETRY) run mypy src/ --ignore-missing-imports

test: ## pytest (live-service tests skip unless TEST_BASE_URL / TEST_REDIS_URL / TEST_DATABASE_URL are set)
	$(POETRY) run pytest tests/ -q

test-cov: ## pytest with line coverage (writes coverage.xml)
	$(POETRY) run pytest tests/ -q --cov=chatbot_ai_system --cov-report=term --cov-report=xml

build-frontend: ## Type-check and build the frontend
	cd frontend && npx tsc --noEmit && npm run build

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

docker-build: ## Build the backend image CI builds
	docker build -f docker/dockerfiles/Dockerfile -t chatbot-ai-system:dev .

# ---- evidence ------------------------------------------------------------------
bench: ## Hit the live demo 20x and write benchmarks/results/bench_demo_latest.json
	$(POETRY) run python scripts/bench_demo.py $(BENCH_ARGS)

evidence: ## Failover control-flow timing; writes the committed benchmarks/results/ files
	BENCHMARK_RESULTS_DIR=benchmarks/results $(POETRY) run pytest tests/test_provider_failover.py -q

# ---- housekeeping ----------------------------------------------------------------
clean: ## Remove caches and build/coverage output
	rm -rf dist/ build/ *.egg-info htmlcov/ .coverage coverage.xml backups/ benchmarks/results/tmp/
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/ frontend/.next
	find . -type d -name __pycache__ -not -path './.venv/*' -not -path '*/node_modules/*' -exec rm -rf {} +
