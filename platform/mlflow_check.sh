#!/usr/bin/env bash
# Start the mlops profile, check the MLflow linkage on synthetic runs, shut down (#168).
set -euo pipefail
cd "$(dirname "$0")"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -hex 12)}"
export GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-$(openssl rand -hex 12)}"
compose=(docker compose -f compose.yaml --profile mlops)
trap '"${compose[@]}" down -v >/dev/null 2>&1 || true' EXIT
"${compose[@]}" up -d --wait --wait-timeout 180
python3 mlflow_check.py
