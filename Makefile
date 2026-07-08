CONDA_ENV := etl-benchmark

.PHONY: help env update test lint run clean

help:
	@echo "Available targets:"
	@echo "  make env      Create conda env from environment.yml"
	@echo "  make update   Update conda env"
	@echo "  make test     Run pytest"
	@echo "  make lint     Run ruff check + format"
	@echo "  make run      Run the ETL pipeline"
	@echo "  make clean    Remove generated artifacts"

env:
	conda env create -f environment.yml

update:
	conda env update -f environment.yml --prune

test:
	pytest

lint:
	ruff check .
	ruff format --check .

run:
	python -m etl_benchmark

clean:
	rm -rf experiments/results/*.csv
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
