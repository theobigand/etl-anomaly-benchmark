CONDA_ENV := etl-benchmark
# any Chromium-family binary that supports --print-to-pdf (chrome, chromium, chrome-headless-shell)
CHROME ?= chromium

.PHONY: help env update test lint verify-fast verify-deep verify-real verify-all pipeline benchmark benchmark-water benchmark-cardio synthetic heatmap severity curves slides run clean

help:
	@echo "Available targets:"
	@echo "  make env        Create conda env from environment.yml"
	@echo "  make update     Update conda env"
	@echo "  make test       Run pytest"
	@echo "  make lint       Run ruff check + format"
	@echo "  make verify-fast  Lint, test, measure exact line/branch coverage, write evidence"
	@echo "  make verify-deep  Run the focused mutation pilot and enforce 95%"
	@echo "  make verify-real  Inspect available full datasets and record provenance"
	@echo "  make verify-all   Run all three verification profiles"
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

verify-fast: lint
	@mkdir -p experiments/results
	@set +e; pytest -m 'not real' --cov=src/etl_benchmark --cov=experiments --cov-branch \
		--cov-report=term-missing:skip-covered --cov-report=json:coverage.json \
		--junitxml=experiments/results/pytest.xml; tests_status=$$?; \
		python experiments/verification_report.py --coverage coverage.json \
		--junit experiments/results/pytest.xml --output experiments/results/verification_fast.json; \
		report_status=$$?; test $$tests_status -eq 0 -a $$report_status -eq 0

verify-deep:
	mutmut run
	mutmut export-cicd-stats
	python experiments/check_mutation.py mutants/mutmut-cicd-stats.json

verify-real:
	pytest -m real
	python experiments/verify_real.py --output experiments/results/real_verification.json

verify-all:
	@set +e; $(MAKE) verify-fast; fast=$$?; $(MAKE) verify-deep; deep=$$?; \
		$(MAKE) verify-real; real=$$?; test $$fast -eq 0 -a $$deep -eq 0 -a $$real -eq 0

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
