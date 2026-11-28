#!/usr/bin/env bash
# End-to-end signal path of the synthetic ELT and dbt pipeline (#164): run it in a container against the
# real mlops and observability services and read its traces, logs and MLflow run back from their backends.
# Needs Docker; starts MLflow, Prometheus, Loki, Tempo and Alloy (not Grafana), builds one small image, and
# removes everything, volumes included, when it ends.
set -euo pipefail
cd "$(dirname "$0")"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -hex 12)}"
export GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-$(openssl rand -hex 12)}"
compose=(docker compose -f compose.yaml --profile observability --profile mlops)
trap '"${compose[@]}" down -v >/dev/null 2>&1 || true' EXIT
docker build -q -f tools.Dockerfile -t etl-e2e-pipeline \
  --build-arg 'PACKAGES=duckdb==2.0.1 pyarrow==25.0.0 dbt-core==1.12.7 dbt-duckdb==1.11.1 opentelemetry-distro==0.66b2 opentelemetry-sdk==1.45.2 opentelemetry-exporter-otlp-proto-http==1.45.2' . >/dev/null
"${compose[@]}" up -d --wait --wait-timeout 300 mlflow prometheus loki tempo alloy
python3 e2e_check.py
