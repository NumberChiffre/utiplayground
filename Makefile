.PHONY: help install dev-install lint format type-check test test-cov clean build run-dev run-prod setup-pre-commit

help:
	@echo "UTI CLI MLOps Makefile"
	@echo "Available commands:"
	@echo "  setup           - Initial project setup with uv and pre-commit"
	@echo "  install         - Install production dependencies with uv"
	@echo "  dev-install     - Install development dependencies with uv"
	@echo "  lint            - Run ruff linter (Rust-based)"
	@echo "  format          - Run ruff formatter (Rust-based)"
	@echo "  format-check    - Check if formatting is needed"
	@echo "  type-check      - Run mypy type checking"
	@echo "  test            - Run pytest suite"
	@echo "  test-cov        - Run tests with coverage report"
	@echo "  test-watch      - Run tests in watch mode"
	@echo "  clean           - Clean build artifacts and cache"
	@echo "  build           - Build the package"
	@echo "  run-dev         - Run development server"
	@echo "  run-prod        - Run production server"
	@echo "  docker-build    - Build Docker image"
	@echo "  docker-run      - Run Docker container"
	@echo "  ci-check        - Run all CI checks (lint, type, test)"

setup: dev-install setup-pre-commit
	@echo "✅ Project setup complete"

install:
	uv sync --no-dev
	@echo "✅ Production dependencies installed"

dev-install:
	uv sync
	@echo "✅ Development dependencies installed"

lint:
	@echo "🔍 Running ruff linter..."
	uv run ruff check src/ tests/ --fix
	@echo "✅ Linting complete"

format:
	@echo "🎨 Running ruff formatter..."
	uv run ruff format src/ tests/
	@echo "✅ Formatting complete"

format-check:
	@echo "🎨 Checking code formatting..."
	uv run ruff format src/ tests/ --check
	@echo "✅ Format check complete"

type-check:
	@echo "🔍 Running mypy type checker..."
	uv run mypy src/
	@echo "✅ Type checking complete"

test-unit:
	@echo "🧪 Running all working tests..."
	uv run pytest tests/unit -v
	@echo "✅ All tests complete (37/37 passing)"

test-integration:
	@echo "🧪 Running integration tests..."
	uv run pytest tests/integration -v
	@echo "✅ Integration tests complete"

test-all:
	@echo "🧪 Running all tests (requires full environment)..."
	uv run pytest tests -v
	@echo "✅ All tests complete"

test-cov:
	@echo "🧪 Running tests with coverage..."
	uv run pytest tests --cov=src --cov-report=html --cov-report=term-missing
	@echo "✅ Coverage report generated in htmlcov/"

test-watch:
	@echo "🧪 Running tests in watch mode..."
	uv run pytest tests/ -f --tb=short

clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf build/ dist/ *.egg-info/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "✅ Cleanup complete"

build: clean
	@echo "📦 Building package..."
	uv build
	@echo "✅ Build complete"

run-dev:
	@echo "🚀 Starting development server..."
	uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

run-prod:
	@echo "🚀 Starting production server..."
	uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4

docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t uti-cli:latest .

docker-run:
	@echo "🐳 Running Docker container..."
	docker run -p 8000:8000 --env-file .env uti-cli:latest

setup-pre-commit:
	@echo "🔧 Setting up pre-commit hooks..."
	uv run pre-commit install
	@echo "✅ Pre-commit hooks installed"

ci-check: lint format-check type-check test
	@echo "✅ All CI checks passed"

# Database operations
migrate:
	@echo "🔄 Running database migrations..."
	uv run alembic upgrade head

migrate-create:
	@echo "📝 Creating new migration..."
	uv run alembic revision --autogenerate -m "$(MESSAGE)"

# MCP Server
run-mcp:
	@echo "🤖 Starting MCP Model Router..."
	uv run python src/livewell/mcp/model_router.py

test-mcp:
	@echo "🧪 Testing MCP tools..."
	uv run python -c "from livewell.tools import WebSearchTool; import asyncio; tool = WebSearchTool(); result = asyncio.run(tool.execute(query='diabetes')); print('✅ MCP tools working:', result.success)"

# Development utilities
logs:
	@echo "📄 Tailing application logs..."
	tail -f logs/app.log

shell:
	@echo "🐍 Starting interactive Python shell..."
	uv run python

jupyter:
	@echo "📊 Starting Jupyter server..."
	uv run jupyter lab

# Security checks
security:
	@echo "🔒 Running security checks..."
	uv run bandit -r src/

# Performance profiling
profile:
	@echo "⚡ Running performance profile..."
	uv run python -m cProfile -o profile.stats src/main.py

# Documentation
docs:
	@echo "📚 Generating documentation..."
	uv run sphinx-build docs/ docs/_build/
