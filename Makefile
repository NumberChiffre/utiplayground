.PHONY: help setup install lint format test clean build run ci

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
	@uv run uvicorn src.server:app --reload --host 0.0.0.0 --port 8000

ci: lint format test
	@echo "✅ All CI checks passed"

