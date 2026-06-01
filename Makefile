.PHONY: install test lint clean run help

# Default target
help:
	@echo "AIChatRouter-CLI Makefile"
	@echo "========================="
	@echo ""
	@echo "Available targets:"
	@echo "  install  - Install package in editable mode"
	@echo "  test     - Run all unit tests"
	@echo "  lint     - Basic syntax check on Python files"
	@echo "  clean    - Remove build artifacts and cache"
	@echo "  run      - Start interactive chat session"
	@echo "  help     - Show this help message"

install:
	pip install -e .

test:
	python -m pytest tests/ -v

lint:
	python -m py_compile main.py
	python -m py_compile aichatrouter/__init__.py
	@echo "Lint passed."

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .coverage htmlcov/
	@echo "Clean done."

run:
	python main.py chat
