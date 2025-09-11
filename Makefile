.PHONY: help setup install lint format test clean build run ci

REDIS_NAME=utiplayground-redis

help:
	@echo "UTI Assessment Tool - Makefile"
	@echo "Available commands:"
	@echo "  setup      - Initial project setup with dependencies"
	@echo "  install    - Install dependencies"
	@echo "  lint       - Run code linting"
	@echo "  format     - Format code"
	@echo "  test       - Run tests"
	@echo "  clean      - Clean build artifacts"
	@echo "  build      - Build the package"
	@echo "  run        - Run development server"
	@echo "  ci         - Run all CI checks (lint, format, test)"

setup: install
	@echo "🔧 Setting up pre-commit hooks..."
	@uv run pre-commit install 2>/dev/null || true
	@echo "✅ Project setup complete"

install:
	@echo "📦 Installing dependencies..."
	@uv sync
	@echo "✅ Dependencies installed"

lint:
	@echo "🔍 Running linter..."
	@uv run ruff check src/ tests/ --fix
	@echo "✅ Linting complete"

format:
	@echo "🎨 Formatting code..."
	@uv run ruff format src/ tests/
	@echo "✅ Formatting complete"

test:
	@echo "🧪 Running tests..."
	@uv run pytest tests/ -v
	@echo "✅ Tests complete"

clean:
	@echo "🧹 Cleaning build artifacts..."
	@rm -rf build/ dist/ *.egg-info/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleanup complete"

build: clean
	@echo "📦 Building package..."
	@uv build
	@echo "✅ Build complete"

run:
	@echo "🚀 Starting server..."
	@$(MAKE) redis-up
	@uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

ci: lint format test
	@echo "✅ All CI checks passed"

redis-up:
	@echo "📦 Ensuring Redis is running..."
	@if command -v docker >/dev/null 2>&1; then \
		if [ $$(docker ps -q -f name=$(REDIS_NAME)) ]; then \
			echo "✅ Redis container already running"; \
		elif [ $$(docker ps -aq -f name=$(REDIS_NAME)) ]; then \
			echo "🔄 Starting existing Redis container..."; \
			docker start $(REDIS_NAME) >/dev/null; \
			echo "✅ Redis started"; \
		else \
			echo "🚀 Launching new Redis container (redis:7-alpine)..."; \
			docker run -d --name $(REDIS_NAME) -p 6379:6379 redis:7-alpine >/dev/null; \
			echo "✅ Redis launched"; \
		fi; \
	else \
		echo "⚠️  Docker not found. Install Docker or run 'redis-server' locally on port 6379."; \
	fi

redis-down:
	@echo "🛑 Stopping and removing Redis container (if exists)..."
	@if command -v docker >/dev/null 2>&1; then \
		if [ $$(docker ps -aq -f name=$(REDIS_NAME)) ]; then \
			docker rm -f $(REDIS_NAME) >/dev/null || true; \
			echo "✅ Redis container removed"; \
		else \
			echo "ℹ️  No Redis container found"; \
		fi; \
	else \
		echo "⚠️  Docker not found. Nothing to stop."; \
	fi

redis-logs:
	@echo "📜 Tailing Redis logs... (Ctrl+C to exit)"
	@docker logs -f $(REDIS_NAME) | cat

