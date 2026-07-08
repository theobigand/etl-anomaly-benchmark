CONDA_ENV := etl-benchmark

.PHONY: help env update test lint pipeline benchmark run clean

help:
	@echo "Available targets:"
	@echo "  make env        Create conda env from environment.yml"
	@echo "  make update     Update conda env"
	@echo "  make test       Run pytest"
	@echo "  make lint       Run ruff check + format"
	@echo "  make pipeline   Run the ETL pipeline demo (sorts data with one detector)"
	@echo "  make benchmark  Compare all detectors and print/save the metrics"
	@echo "  make run        Run everything (pipeline then benchmark)"
	@echo "  make clean      Remove generated artifacts"

env:
	conda env create -f environment.yml

update:
	conda env update -f environment.yml --prune

test:
	pytest

lint:
	ruff check .
	ruff format --check .

pipeline:
	python -m etl_benchmark

benchmark:
	python experiments/run_benchmark.py

run: pipeline benchmark

clean:
	rm -rf experiments/results/*.csv experiments/results/*.md
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
