#!/usr/bin/env bash
# Start one runtime profile alone, check that it works, restart it, and shut it down cleanly (#142).
# Usage: platform/smoke.sh core|elt|etl|aiops|analytics|relational|mlops|orchestration|observability [--keep]
# Credentials are generated for this run only and never written to disk.
set -euo pipefail
profile="${1:?profile}"; keep="${2:-}"
cd "$(dirname "$0")"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -hex 12)}"
export GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-$(openssl rand -hex 12)}"
compose=(docker compose -f compose.yaml --profile "$profile")
cleanup() { [ "$keep" = "--keep" ] || "${compose[@]}" down -v >/dev/null 2>&1 || true; }
trap cleanup EXIT

wait_http() { # url, seconds
  for _ in $(seq 1 "$2"); do curl -fsS -m 5 -o /dev/null "$1" 2>/dev/null && return 0; sleep 1; done
  echo "FAIL: $1 not ready after $2 s" >&2; return 1
}
ok() { echo "ok: $*"; }

case "$profile" in
core|elt|etl|aiops) ;; # one-shot tools: run by the checks below
*) "${compose[@]}" up -d --wait --wait-timeout 300 ;;
esac
"${compose[@]}" config --format json | python3 -c '
import json, sys
for name, svc in json.load(sys.stdin)["services"].items():
    for port in svc.get("ports", []):
        assert port.get("host_ip") == "127.0.0.1", f"{name}: port not bound to loopback: {port}"
    assert svc.get("mem_limit"), f"{name}: no memory limit"
'
ok "ports bound to 127.0.0.1 and memory limits set"

case "$profile" in
relational)
  psql() { "${compose[@]}" exec -T postgres psql -U etl -d etl -tA -c "$1"; }
  psql "create table if not exists smoke(v int); insert into smoke values (42);" >/dev/null
  [ "$(psql 'select v from smoke')" = 42 ] ; ok "insert and select"
  "${compose[@]}" restart postgres >/dev/null
  for _ in $(seq 1 30); do [ "$(psql 'select v from smoke' 2>/dev/null || true)" = 42 ] && break; sleep 1; done
  [ "$(psql 'select v from smoke')" = 42 ] ; ok "data survives a restart"
  if psql "select * from missing_table" >/dev/null 2>&1; then echo "FAIL: bad query succeeded" >&2; exit 1; fi
  ok "an invalid query fails"
  ;;
mlops)
  url="http://127.0.0.1:${MLFLOW_PORT:-55000}"
  wait_http "$url/health" 60
  curl -fsS -X POST "$url/api/2.0/mlflow/experiments/create" -H 'Content-Type: application/json' -d '{"name":"smoke"}' >/dev/null
  curl -fsS "$url/api/2.0/mlflow/experiments/get-by-name?experiment_name=smoke" | grep -q '"name": *"smoke"' ; ok "experiment created and read back"
  "${compose[@]}" restart mlflow >/dev/null
  wait_http "$url/health" 90
  curl -fsS "$url/api/2.0/mlflow/experiments/get-by-name?experiment_name=smoke" | grep -q '"name": *"smoke"' ; ok "experiment survives a restart"
  ;;
orchestration)
  url="http://127.0.0.1:${AIRFLOW_PORT:-58080}"
  wait_http "$url/api/v2/monitor/health" 120
  curl -fsS "$url/api/v2/monitor/health" | python3 -c '
import json, sys
h = json.load(sys.stdin)
assert h["metadatabase"]["status"] == "healthy" and h["scheduler"]["status"] == "healthy", h
' ; ok "metadata database and scheduler healthy"
  ;;
observability)
  wait_http "http://127.0.0.1:${LOKI_PORT:-53100}/ready" 90 ; ok "loki ready"
  wait_http "http://127.0.0.1:${TEMPO_PORT:-53200}/ready" 90 ; ok "tempo ready"
  wait_http "http://127.0.0.1:${ALLOY_PORT:-52345}/-/ready" 60 ; ok "alloy ready"
  wait_http "http://127.0.0.1:${PROMETHEUS_PORT:-59090}/-/ready" 60 ; ok "prometheus ready"
  wait_http "http://127.0.0.1:${GRAFANA_PORT:-53000}/api/health" 60 ; ok "grafana ready"
  marker="smoke-$(date +%s)"
  ts="$(python3 -c 'import time; print(int(time.time()*1e9))')"
  curl -fsS -X POST "http://127.0.0.1:${OTLP_HTTP_PORT:-54318}/v1/logs" -H 'Content-Type: application/json' -d "{\"resourceLogs\":[{\"resource\":{\"attributes\":[{\"key\":\"service.name\",\"value\":{\"stringValue\":\"smoke\"}}]},\"scopeLogs\":[{\"logRecords\":[{\"timeUnixNano\":\"$ts\",\"severityText\":\"INFO\",\"body\":{\"stringValue\":\"$marker\"}}]}]}]}" >/dev/null
  found=""
  for _ in $(seq 1 30); do
    found="$(curl -fsS -G "http://127.0.0.1:${LOKI_PORT:-53100}/loki/api/v1/query_range" --data-urlencode 'query={service_name="smoke"}' --data-urlencode "start=$((ts - 600000000000))" || true)"
    echo "$found" | grep -q "$marker" && break; sleep 2
  done
  echo "$found" | grep -q "$marker" ; ok "a log sent to Alloy over OTLP is stored in Loki"
  trace="$(openssl rand -hex 16)"; span="$(openssl rand -hex 8)"
  curl -fsS -X POST "http://127.0.0.1:${OTLP_HTTP_PORT:-54318}/v1/traces" -H 'Content-Type: application/json' -d "{\"resourceSpans\":[{\"resource\":{\"attributes\":[{\"key\":\"service.name\",\"value\":{\"stringValue\":\"smoke\"}}]},\"scopeSpans\":[{\"spans\":[{\"traceId\":\"$trace\",\"spanId\":\"$span\",\"name\":\"smoke-span\",\"kind\":1,\"startTimeUnixNano\":\"$ts\",\"endTimeUnixNano\":\"$((ts + 1000000))\"}]}]}]}" >/dev/null
  seen=""
  for _ in $(seq 1 30); do
    seen="$(curl -fsS "http://127.0.0.1:${TEMPO_PORT:-53200}/api/traces/$trace" 2>/dev/null || true)"
    echo "$seen" | grep -q "smoke-span" && break; sleep 2
  done
  echo "$seen" | grep -q "smoke-span" ; ok "a trace sent to Alloy over OTLP is found in Tempo"
  curl -fsS -X POST "http://127.0.0.1:${OTLP_HTTP_PORT:-54318}/v1/metrics" -H 'Content-Type: application/json' -d "{\"resourceMetrics\":[{\"resource\":{\"attributes\":[{\"key\":\"service.name\",\"value\":{\"stringValue\":\"smoke\"}}]},\"scopeMetrics\":[{\"metrics\":[{\"name\":\"smoke_jobs\",\"gauge\":{\"dataPoints\":[{\"timeUnixNano\":\"$ts\",\"asDouble\":7}]}}]}]}]}" >/dev/null
  value=""
  for _ in $(seq 1 30); do
    value="$(curl -fsS -G "http://127.0.0.1:${PROMETHEUS_PORT:-59090}/api/v1/query" --data-urlencode 'query=smoke_jobs' || true)"
    echo "$value" | grep -q '"7"' && break; sleep 2
  done
  echo "$value" | grep -q '"7"' ; ok "a metric sent to Alloy over OTLP is queryable in Prometheus"
  curl -fsS "http://127.0.0.1:${LOKI_PORT:-53100}/loki/api/v1/labels" | python3 -c '
import json, sys
labels = set(json.load(sys.stdin)["data"])
assert labels <= {"exporter", "job", "service_name", "level"}, f"unexpected Loki labels: {labels}"
' ; ok "Loki labels are low-cardinality (no run or trace identifier)"
  curl -fsS -u "admin:$GRAFANA_ADMIN_PASSWORD" "http://127.0.0.1:${GRAFANA_PORT:-53000}/api/datasources" | python3 -c '
import json, sys
names = sorted(d["name"] for d in json.load(sys.stdin))
assert names == ["Loki", "Prometheus", "Tempo"], names
' ; ok "grafana provisioned its three data sources"
  ;;
core)
  out="$("${compose[@]}" run --rm core 2>/dev/null | tail -1)"
  echo "$out" | grep -q '^Verified [0-9]* tasks$' ; ok "the research tooling runs with no platform service: $out"
  ;;
elt)
  "${compose[@]}" run --rm elt python -c '
import duckdb
duckdb.sql("copy (select 1 as a, 2 as b) to \"/tmp/t.parquet\" (format parquet)")
assert duckdb.sql("select a + b from \"/tmp/t.parquet\"").fetchall() == [(3,)]
' ; ok "duckdb reads and writes parquet"
  ;;
etl)
  "${compose[@]}" run --rm etl python -c '
from pyspark.sql import SparkSession
s = SparkSession.builder.master("local[1]").config("spark.ui.enabled", "false").config("spark.driver.memory", "1g").getOrCreate()
assert s.range(10).count() == 10
s.stop()
' ; ok "pyspark counts a dataframe in local mode"
  ;;
aiops)
  "${compose[@]}" run --rm aiops python -c '
from drain3 import TemplateMiner
m = TemplateMiner()
for line in ("user 1 logged in", "user 2 logged in", "user 3 logged in"):
    r = m.add_log_message(line)
assert r["template_mined"] == "user <*> logged in", r
' ; ok "drain3 mines a log template"
  ;;
analytics)
  wait_http "http://127.0.0.1:${STREAMLIT_PORT:-58501}/_stcore/health" 60 ; ok "streamlit serves"
  ;;
*) echo "unknown profile: $profile" >&2; exit 2 ;;
esac
echo "PASS: $profile"
