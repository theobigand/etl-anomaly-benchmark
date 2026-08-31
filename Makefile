CONDA_ENV := etl-benchmark
# any Chromium-family binary that supports --print-to-pdf (chrome, chromium, chrome-headless-shell)
CHROME ?= chromium

.PHONY: help env update test lint pipeline benchmark benchmark-water benchmark-cardio synthetic heatmap severity curves slides run clean

help:
	@echo "Available targets:"
	@echo "  make env        Create conda env from environment.yml"
	@echo "  make update     Update conda env"
	@echo "  make test       Run pytest"
	@echo "  make lint       Run ruff check + format"
	@echo "  make pipeline   Run the ETL pipeline demo (sorts data with one detector)"
	@echo "  make benchmark       Benchmark on Credit Card Fraud (5 seeds, stratified split)"
	@echo "  make benchmark-water Benchmark on the Water Quality dataset"
	@echo "  make benchmark-cardio Fetch the Cardio dataset and benchmark on it"
	@echo "  make synthetic       Generate the per-anomaly-type dataset (data/synthetic.csv)"
	@echo "  make heatmap         Multi-seed method-by-anomaly-type benchmark, render the heatmap"
	@echo "  make severity        Detection-rate versus injection-severity curves"
	@echo "  make curves          Precision-recall curves + contamination sweep"
	@echo "  make slides          Render slides/thesis_progress.pdf from the HTML deck"
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
	python experiments/run_benchmark.py --dataset credit_card

benchmark-water:
	python experiments/run_benchmark.py --dataset water_quality

benchmark-cardio:
	python experiments/fetch_cardio.py
	python experiments/run_benchmark.py --dataset cardio

synthetic:
	python experiments/generate_synthetic.py

heatmap: synthetic
	python experiments/run_synthetic_benchmark.py

severity:
	python experiments/run_severity.py

slides:
	$(CHROME) --headless --no-pdf-header-footer \
	  --print-to-pdf=slides/thesis_progress.pdf \
	  "file://$(CURDIR)/slides/thesis_progress.html"

curves:
	python experiments/run_curves.py

run: pipeline benchmark

clean:
	rm -rf experiments/results/*.csv experiments/results/*.md experiments/results/*.png
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
