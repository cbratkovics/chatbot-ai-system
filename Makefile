.PHONY: help install test lint format clean docker-build docker-up docker-down

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies with Poetry
	poetry install --with dev

test:  ## Run tests with coverage
	poetry run pytest tests/ -v --cov=api --cov-report=term-missing

lint:  ## Run linting checks
	poetry run black --check api/ tests/
	poetry run isort --check-only api/ tests/
	poetry run flake8 api/ tests/
	poetry run mypy api/

format:  ## Format code
	poetry run black api/ tests/
	poetry run isort api/ tests/

security:  ## Run security checks
	poetry run bandit -r api/
	poetry run safety check

clean:  ## Clean up cache and temp files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage coverage.xml htmlcov/

docker-build:  ## Build Docker image
	docker build -t chatbot-platform:latest .

docker-up:  ## Start services with docker-compose
	docker-compose up -d

docker-down:  ## Stop services
	docker-compose down

migrate:  ## Run database migrations
	poetry run alembic upgrade head

serve:  ## Start development server
	poetry run python -m api.main

# Quick Demo Commands
.PHONY: demo demo-up demo-test demo-benchmark demo-clean

demo: demo-up demo-test demo-benchmark  ## Run complete demo (build, test, benchmark)
	@echo "Demo complete. See benchmarks/results/"

demo-up:  ## Start services for demo
	docker compose up -d --build
	@echo "Waiting for services..."
	@sleep 5
	@curl -fsS http://localhost:8000/health >/dev/null && echo "Health: OK" || echo "Health: FAIL"

demo-test:  ## Run provider failover tests
	docker compose exec backend pytest -q --maxfail=1 --disable-warnings || true
	docker compose exec backend pytest -q tests/test_provider_failover.py -v --tb=short --junitxml=benchmarks/results/junit_$${USER}.xml || true

demo-benchmark:  ## Run k6 load tests
	docker run --rm --network=host -v $(PWD)/benchmarks:/scripts grafana/k6 run /scripts/load/rest_api_load.js
	docker run --rm --network=host -v $(PWD)/benchmarks:/scripts grafana/k6 run /scripts/load/websocket_concurrency.js
	@echo "Results saved to benchmarks/results/"

demo-clean:  ## Clean up demo resources
	docker compose down -v
