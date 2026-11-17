.PHONY: install dev test lint format clean help cli-link doctor

# Default target
all: install

# Install dependencies
install:
	pip install -e ".[dev]"

# Development mode
dev:
	pip install -e ".[dev]"
	pre-commit install

# Run tests
test:
	pytest tests/ -v --cov=agent_sync --cov-report=term-missing

# Run tests with coverage
coverage:
	pytest tests/ -v --cov=agent_sync --cov-report=html
	open htmlcov/index.html

# Lint code
lint:
	ruff check src/ tests/
	black --check src/ tests/

# Format code
format:
	black src/ tests/
	ruff check --fix src/ tests/

# Type checking (if using mypy)
typecheck:
	mypy src/

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Build distribution
build:
	python -m build

# Publish to PyPI (requires twine)
publish: build
	twine upload dist/*

# Run CLI locally
run:
	python -m agent_sync.cli --help

# Wire the `agent-sync` command to this checkout (~/.local/bin, pip-safe)
cli-link:
	./scripts/cli-link.sh

# Verify the CLI on PATH is this checkout and the metadata matches the tag
doctor:
	./scripts/cli-link.sh --check

# Help
help:
	@echo "agent-sync Development"
	@echo ""
	@echo "Available targets:"
	@echo "  install     - Install package in development mode"
	@echo "  dev         - Install with pre-commit hooks"
	@echo "  test        - Run tests with coverage"
	@echo "  coverage    - Run tests and open coverage report"
	@echo "  lint        - Check code style"
	@echo "  format      - Format code with black"
	@echo "  clean       - Remove build artifacts"
	@echo "  build       - Build distribution packages"
	@echo "  publish     - Upload to PyPI"
	@echo "  run         - Run CLI locally"
	@echo "  cli-link    - Wire/repair the agent-sync command on PATH"
	@echo "  doctor      - Verify the CLI on PATH points at this checkout"
	@echo ""
