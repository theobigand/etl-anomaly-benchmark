CONDA_ENV := etl-benchmark
# any Chromium-family binary that supports --print-to-pdf (chrome, chromium, chrome-headless-shell)
CHROME ?= chromium

.PHONY: help env update test lint verify-fast verify-deep verify-faults verify-real verify-scale lock verify-types verify-tools verify-reproduce verify-release verify-all pipeline benchmark benchmark-water benchmark-cardio synthetic heatmap severity curves slides run clean

help:
	@echo "Available targets:"
	@echo "  make env        Create conda env from environment.yml"
	@echo "  make update     Update conda env"
	@echo "  make test       Run pytest"
	@echo "  make lint       Run ruff check + format"
	@echo "  make verify-fast  Lint, test, measure exact line/branch coverage, write evidence"
	@echo "  make verify-deep  Mutation campaign on src/etl_benchmark and experiments, enforce 95%"
	@echo "  make verify-faults Apply deliberate scientific defects to a temporary copy and require a failure"
	@echo "  make verify-real  Inspect available full datasets and record provenance"
	@echo "  make verify-scale Measure bounded detector growth outside FAST"
	@echo "  make lock       Record the exact conda and pip packages of the active environment"
	@echo "  make verify-types mypy: verification/ clean, scientific code may not add errors"
	@echo "  make verify-tools Measure line/branch coverage of the verifier code in verification/ (separate from FAST)"
	@echo "  make verify-reproduce Controlled cardio reproduction (archive, same and locked environment), write evidence"
	@echo "  make verify-release Certify the evidence required by verification/release_policy.json for the current clean revision"
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

EVIDENCE := experiments/results/evidence

verify-fast: lint
	@mkdir -p experiments/results $(EVIDENCE)
	@rm -f experiments/results/verification_fast.json $(EVIDENCE)/fast.json
	@set +e; pytest -m 'not real and not fault' --cov=src/etl_benchmark --cov=experiments --cov-branch \
		--cov-report=term-missing:skip-covered --cov-report=json:coverage.json \
		--junitxml=experiments/results/pytest.xml; tests_status=$$?; \
		python verification/refresh_profile.py --coverage coverage.json \
		--template verification/profile.template.json --output verification/profile.json; \
		profile_status=$$?; \
		python experiments/verification_report.py --coverage coverage.json \
		--junit experiments/results/pytest.xml --output experiments/results/verification_fast.json; \
		report_status=$$?; \
		python -m verification.evidence_schema fast --coverage coverage.json \
		--junit experiments/results/pytest.xml --output $(EVIDENCE)/fast.json; \
		evidence_status=$$?; \
		test $$tests_status -eq 0 -a $$profile_status -eq 0 -a $$report_status -eq 0 \
		-a $$evidence_status -eq 0

verify-deep:
	@mkdir -p $(EVIDENCE)
	@rm -f $(EVIDENCE)/deep.json mutants/mutmut-cicd-stats.json
	mutmut run
	mutmut export-cicd-stats
	mutmut results --all true > mutants/results.txt
	@set +e; python experiments/check_mutation.py mutants/mutmut-cicd-stats.json; gate=$$?; \
		python -m verification.evidence_schema deep --stats mutants/mutmut-cicd-stats.json \
		--results mutants/results.txt --output $(EVIDENCE)/deep.json; evidence_status=$$?; \
		test $$gate -eq 0 -a $$evidence_status -eq 0

verify-faults:
	@mkdir -p $(EVIDENCE)
	@rm -f $(EVIDENCE)/faults.json experiments/results/fault_matrix.json
	@set +e; pytest -m fault tests/test_fault_matrix.py; tests_status=$$?; \
		python -m verification.evidence_schema faults \
		--matrix experiments/results/fault_matrix.json --output $(EVIDENCE)/faults.json; \
		evidence_status=$$?; test $$tests_status -eq 0 -a $$evidence_status -eq 0

verify-real:
	@mkdir -p $(EVIDENCE)
	@rm -f $(EVIDENCE)/real.json experiments/results/real_verification.json
	pytest -m real
	@set +e; python experiments/verify_real.py --output experiments/results/real_verification.json; \
		gate=$$?; python -m verification.evidence_schema real \
		--report experiments/results/real_verification.json \
		$(if $(REAL_ACQUISITION),--acquisition $(REAL_ACQUISITION)) --output $(EVIDENCE)/real.json; \
		evidence_status=$$?; test $$gate -eq 0 -a $$evidence_status -eq 0

lock:
	python verification/lock_environment.py

verify-types:
	@mkdir -p $(EVIDENCE) experiments/results
	@rm -f $(EVIDENCE)/types.json experiments/results/types_report.json
	@set +e; python verification/check_types.py --output experiments/results/types_report.json; \
		gate=$$?; python -m verification.evidence_schema types \
		--report experiments/results/types_report.json --output $(EVIDENCE)/types.json; \
		evidence_status=$$?; test $$gate -eq 0 -a $$evidence_status -eq 0

verify-tools:
	@mkdir -p $(EVIDENCE) experiments/results
	@rm -f $(EVIDENCE)/tools.json experiments/results/verifier_coverage.json
	@set +e; pytest -m 'not real and not fault' -q --cov=verification --cov-branch --cov-fail-under=100 \
		--cov-report=term-missing:skip-covered --cov-report=json:experiments/results/verifier_coverage.json; \
		tests_status=$$?; python -m verification.evidence_schema tools \
		--coverage experiments/results/verifier_coverage.json --output $(EVIDENCE)/tools.json; \
		evidence_status=$$?; test $$tests_status -eq 0 -a $$evidence_status -eq 0

verify-reproduce:
	@mkdir -p $(EVIDENCE) experiments/results
	@rm -f $(EVIDENCE)/reproduction.json experiments/results/reproducibility.json
	@set +e; python -m verification.reproduce --levels archive same_environment locked_environment \
		version_sensitivity --output experiments/results/reproducibility.json; gate=$$?; \
		python -m verification.evidence_schema reproduction \
		--report experiments/results/reproducibility.json --output $(EVIDENCE)/reproduction.json; \
		evidence_status=$$?; test $$gate -eq 0 -a $$evidence_status -eq 0

verify-release:
	python -m verification.release

verify-scale:
	python verification/scaling.py

verify-all:
	@set +e; $(MAKE) verify-fast; fast=$$?; $(MAKE) verify-deep; deep=$$?; \
		$(MAKE) verify-faults; faults=$$?; $(MAKE) verify-real; real=$$?; \
		test $$fast -eq 0 -a $$deep -eq 0 -a $$faults -eq 0 -a $$real -eq 0

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
