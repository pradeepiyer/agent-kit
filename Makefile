.PHONY: test install clean lint sync-deps help wc build build-wheel build-sdist build-all package-info lock-deps check-deps ci console

# Default target
help:
	@echo "Available targets:"
	@echo ""
	@echo "General:"
	@echo "  test         - Run test suite with coverage (excludes integration)"
	@echo "  test-integration - Run integration tests (requires API keys)"
	@echo "  install      - Install agent-kit in development mode"
	@echo "  clean        - Remove build artifacts and cache files"
	@echo "  lint         - Run linter and fix issues with ruff and mypy"
	@echo "  sync-deps    - Sync uv dependencies and lock file"
	@echo "  console      - Run hello agent example (interactive chat)"
	@echo "  help         - Show this help message"
	@echo ""
	@echo "Package Distribution:"
	@echo "  build        - Build wheel package (default)"
	@echo "  build-wheel  - Build wheel package only"
	@echo "  build-sdist  - Build source distribution only"
	@echo "  build-all    - Build both wheel and source distribution"
	@echo "  package-info - Show package information and files"
	@echo ""
	@echo "Dependency Management:"
	@echo "  lock-deps    - Update dependency lock file"
	@echo "  check-deps   - Check if dependencies are up to date"
	@echo "  ci           - Run the same checks as GitHub CI (lint, format check, pyright, tests)"

# Run test suite with coverage (excludes integration tests)
test:
	uv run pytest tests/ -v

# Run integration tests (requires API keys)
test-integration:
	uv run pytest tests/ -v -m integration

# Install agent-kit in development mode
install:
	uv pip install -e .

# Clean build artifacts and cache files
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .pyright/
	rm -rf .ruff_cache/

# Run linter and fix issues
lint:
	uv run ruff check --fix .
	uv run ruff format .
	uv run pyright

# Mirror the GitHub Actions CI locally
ci:
	uv sync --group dev
	uv run ruff check
	uv run ruff format --check
	uv run pyright
	uv run python -m pytest

# Sync uv dependencies
sync-deps:
	uv sync

# Run hello agent example
console:
	@echo "💬 Starting hello agent example..."
	uv run python -m agent_kit.agents.hello

# Count lines of code in the repository
wc:
	@echo "Line count by file type:"
	@echo ""
	@echo "Python files by component:"
	@echo "  agent_kit/ components (dynamically detected):"
	@for dir in $$(find ./agent_kit -type d -mindepth 1 | sort); do \
		if [ -n "$$(find $$dir -maxdepth 1 -name "*.py" -type f)" ]; then \
			component=$$(echo $$dir | sed 's|^\./agent_kit/||'); \
			count=$$(find $$dir -maxdepth 1 -name "*.py" -type f | xargs wc -l 2>/dev/null | tail -1 | awk '{print $$1}'); \
			[ "$$count" != "0" ] && echo "    $$component/: $$count lines"; \
		fi \
	done
	@echo ""
	@echo "  agent_kit/ total:"
	@find ./agent_kit -name "*.py" -type f | xargs wc -l | tail -1 | awk '{print "   " $$1 " lines"}'
	@echo ""
	@echo "  tests/ (test framework):"
	@if [ -d "./tests" ]; then \
		find ./tests -name "*.py" -type f | xargs wc -l 2>/dev/null | tail -1 | awk '{print "   " $$1 " lines"}'; \
	else \
		echo "   0 lines (tests/ not created yet)"; \
	fi
	@echo ""
	@echo "Total Python files:"
	@find . -name "*.py" -type f -not -path "./.venv/*" -not -path "./build/*" -not -path "./dist/*" -not -path "./.mypy_cache/*" -not -path "./.pytest_cache/*" -not -path "./.ruff_cache/*" | xargs wc -l 2>/dev/null | tail -1 | awk '{print " " $$1 " lines"}'
	@echo ""
	@echo "YAML files:"
	@find . -name "*.yaml" -o -name "*.yml" -type f -not -path "./.venv/*" -not -path "./build/*" -not -path "./dist/*" | xargs wc -l 2>/dev/null | tail -1 | awk '{print " " $$1 " lines"}'
	@echo ""

# Package Distribution Commands

# Build wheel package (default)
build: build-wheel

# Build wheel package only
build-wheel:
	@echo "📦 Building wheel package..."
	uv build --wheel
	@echo "✅ Wheel package created in dist/"

# Build source distribution only
build-sdist:
	@echo "📦 Building source distribution..."
	uv build --sdist
	@echo "✅ Source distribution created in dist/"

# Build both wheel and source distribution
build-all:
	@echo "📦 Building wheel and source distribution..."
	uv build
	@echo "✅ Both packages created in dist/"

# Show package information
package-info:
	@echo "📋 Package Information:"
	@echo "  Name: agent-kit"
	@echo "  Version: $$(grep '^version' pyproject.toml | cut -d'"' -f2)"
	@echo "  Type: Pure library (no entry points)"
	@echo ""
	@echo "📁 Package structure:"
	@echo "  agent_kit/              - Main package"
	@echo "  agent_kit/data/         - Package data (config, prompts)"
	@echo "  agent_kit/agents/hello/ - Example agent implementation"
	@echo ""
	@echo "🚀 Run hello agent example:"
	@echo "  uv run python -m agent_kit.agents.hello"
	@echo ""
	@if [ -d "dist" ]; then \
		echo "📦 Built packages:"; \
		ls -la dist/ | grep -E '\.(whl|tar\.gz)$$' | awk '{print "  " $$9 " (" $$5 " bytes)"}'; \
	else \
		echo "📦 No packages built yet. Run 'make build' to create packages."; \
	fi

# Dependency Management Commands

# Update dependency lock file
lock-deps:
	@echo "🔒 Updating dependency lock file..."
	uv lock
	@echo "✅ Lock file updated (uv.lock)"

# Check if dependencies are up to date
check-deps:
	@echo "🔍 Checking dependency status..."
	@if uv lock --check > /dev/null 2>&1; then \
		echo "✅ Dependencies are up to date"; \
	else \
		echo "⚠️  Dependencies need updating. Run 'make lock-deps'"; \
	fi
