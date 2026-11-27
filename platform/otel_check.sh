#!/usr/bin/env bash
# Run obs_tracing against the real OpenTelemetry SDK in a throwaway container (#161).
# The SDK is an optional dependency (ADR-0009) and is installed only in the container.
set -euo pipefail
cd "$(dirname "$0")/.."
docker run --rm --memory 512m --security-opt no-new-privileges \
  -v "$PWD/research:/work/research:ro" -v "$PWD/platform/tests:/work/platform/tests:ro" \
  -w /work python:3.13-slim sh -c '
    pip install -q --no-cache-dir --disable-pip-version-check \
      opentelemetry-sdk==1.45.2 opentelemetry-exporter-otlp-proto-http==1.45.2 pytest >/dev/null &&
    python -m pytest -q -p no:cacheprovider platform/tests/test_tracing_otel.py'
