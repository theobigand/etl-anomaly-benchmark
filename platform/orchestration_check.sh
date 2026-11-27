#!/usr/bin/env bash
# Start the orchestration and mlops profiles together, run the synthetic DAG through Airflow, shut down (#157, #158).
set -euo pipefail
cd "$(dirname "$0")"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -hex 12)}"
export GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-$(openssl rand -hex 12)}"
compose=(docker compose -f compose.yaml --profile orchestration --profile mlops)
trap '"${compose[@]}" down -v >/dev/null 2>&1 || true' EXIT
"${compose[@]}" up -d --wait --wait-timeout 300
python3 orchestration_check.py
