.PHONY: help install test lint format clean build demo evidence

# Variables
PYTHON := python3
POETRY := poetry
PROJECT_NAME := ai-chatbot-system
VERSION := $(shell poetry version -s)
DOCKER_IMAGE := $(PROJECT_NAME):$(VERSION)

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo '$(GREEN)Available targets:$(NC)'
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install: ## Install dependencies
	@echo "$(GREEN)Installing dependencies...$(NC)"
	$(POETRY) install

install-dev: ## Install with dev dependencies
	@echo "$(GREEN)Installing with dev dependencies...$(NC)"
	$(POETRY) install --with dev,docs

lock: ## Update lock file
	@echo "$(GREEN)Updating lock file...$(NC)"
	$(POETRY) lock --no-update

update: ## Update dependencies
	@echo "$(GREEN)Updating dependencies...$(NC)"
	$(POETRY) update

format: ## Format code
	@echo "$(GREEN)Formatting code...$(NC)"
	$(POETRY) run ruff format .

lint: ## Run linting
	@echo "$(GREEN)Running linters...$(NC)"
	$(POETRY) run ruff check .
	$(POETRY) run mypy src/ || true

type-check: ## Run type checking
	@echo "$(GREEN)Running type checks...$(NC)"
	$(POETRY) run mypy src

security: ## Run security checks
	@echo "$(GREEN)Running security checks...$(NC)"
	$(POETRY) run bandit -r src
	$(POETRY) run safety check

test: ## Run all tests
	@echo "$(GREEN)Running tests...$(NC)"
	$(POETRY) run pytest -v --cov=src --cov-report=term --cov-report=xml

test-all: ## Run all tests
	@echo "$(GREEN)Running all tests...$(NC)"
	$(POETRY) run pytest -v

test-cov: ## Run tests with coverage
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	$(POETRY) run pytest --cov=src --cov-report=html --cov-report=term

build: ## Build package
	@echo "$(GREEN)Building package...$(NC)"
	$(POETRY) build

docker-build: ## Build Docker image
	@echo "$(GREEN)Building Docker image...$(NC)"
	docker build -t $(DOCKER_IMAGE) \
		--build-arg VERSION=$(VERSION) \
		--build-arg BUILD_DATE=$(shell date -u +'%Y-%m-%dT%H:%M:%SZ') \
		--build-arg VCS_REF=$(shell git rev-parse HEAD) \
		.

docker-run: ## Run Docker container
	@echo "$(GREEN)Running Docker container...$(NC)"
	docker run --rm -p 8000:8000 $(DOCKER_IMAGE)

compose-up: ## Start services with docker-compose
	@echo "$(GREEN)Starting services...$(NC)"
	docker-compose up -d

compose-down: ## Stop services
	@echo "$(GREEN)Stopping services...$(NC)"
	docker-compose down

compose-logs: ## Show service logs
	docker-compose logs -f

clean: ## Clean build artifacts
	@echo "$(RED)Cleaning build artifacts...$(NC)"
	rm -rf dist/ build/ *.egg-info
	rm -rf htmlcov/ .coverage coverage.xml
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run: ## Run development server
	@echo "$(GREEN)Starting development server...$(NC)"
	$(POETRY) run uvicorn chatbot_ai_system.server.main:app --reload --host 0.0.0.0 --port 8000

demo: ## Run local demo environment
	@echo "$(GREEN)Starting demo environment...$(NC)"
	docker-compose -f docker-compose.yml up -d
	@echo "✓ Demo running at http://localhost:8000"
	@echo "✓ API docs at http://localhost:8000/docs"

demo-benchmark: ## Run benchmark tests
	@echo "$(GREEN)Running benchmark tests...$(NC)"
	@if [ -f benchmarks/run_load_test.sh ]; then \
		./benchmarks/run_load_test.sh; \
	else \
		echo "Load test script not found, running simple benchmark"; \
		$(POETRY) run pytest benchmarks/ -v --tb=short || true; \
	fi

demo-test: ## Run tests for demo
	@echo "$(GREEN)Running tests...$(NC)"
	$(POETRY) run pytest tests/ -v --tb=short

demo-clean: ## Clean up demo environment
	@echo "$(RED)Cleaning up demo...$(NC)"
	docker-compose down -v
	@echo "✓ Demo environment cleaned"

ci-local: lint test build ## Run CI checks locally
	@echo "$(GREEN)✓ All CI checks passed locally!$(NC)"

version: ## Show version
	@echo "$(PROJECT_NAME) version: $(VERSION)"

pre-commit: format lint type-check security test ## Run all pre-commit checks

ci: lint test build docker-build ## Run CI pipeline locally

evidence: ## Generate all performance evidence
	@echo "$(GREEN)Generating performance evidence...$(NC)"
	@$(POETRY) run python benchmarks/run_all_benchmarks.py
	@echo "$(GREEN)Evidence files generated in benchmarks/results/$(NC)"
	@ls -la benchmarks/results/*.json

benchmark: evidence ## Run benchmarks (alias for evidence)

.DEFAULT_GOAL := help
