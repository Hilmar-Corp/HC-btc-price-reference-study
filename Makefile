PYTHON ?= python

.PHONY: install format lint test verify coverage assurance

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-ci.txt
	$(PYTHON) -m pip check

format:
	$(PYTHON) -m ruff format scripts tests

lint:
	$(PYTHON) -m ruff format --check scripts tests
	$(PYTHON) -m ruff check scripts tests
	$(PYTHON) -m compileall -q scripts tests

test:
	$(PYTHON) -m pytest -q

verify:
	$(PYTHON) -m scripts.research.verify_repository

coverage:
	mkdir -p artifacts/ci_assurance
	$(PYTHON) -m coverage erase
	$(PYTHON) -m coverage run --branch --source=scripts.research.price_reference_core -m pytest -q tests/test_price_reference_core.py
	$(PYTHON) -m coverage json -o artifacts/ci_assurance/core_coverage.json
	$(PYTHON) -m scripts.research.ci_core_coverage_gate artifacts/ci_assurance/core_coverage.json

assurance: lint test verify coverage
