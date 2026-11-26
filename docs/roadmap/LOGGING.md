# Logging configuration (#156)

`research/obs_logging.py` is the single configuration of the platform tooling's operational logs. It uses the
standard library only, needs no infrastructure, and sits outside `src/` and the top-level `experiments/` scripts:
those files are in the scientific fingerprint, so adopting it there is a separate decision with a replay of the
archived experiments (ADR-0001, `docs/architecture/`). The structlog layer (event schema, correlation identifiers) is
the scope of #157 and builds on this module.

```python
import obs_logging

obs_logging.configure()  # reads ETL_LOG_*; replaces only its own handler
```

| Variable | Values | Default |
|---|---|---|
| `ETL_LOG_LEVEL` | DEBUG, INFO, WARNING, ERROR, CRITICAL | INFO |
| `ETL_LOG_FORMAT` | `console` (readable, UTC), `json` (one object per line) | console |
| `ETL_LOG_DEST` | `stderr`, `stdout`, `file` (needs `ETL_LOG_FILE`) | stderr |
| `ETL_LOG_THIRD_PARTY_LEVEL` | level of great_expectations, matplotlib, urllib3, numba, PIL | WARNING |
| `ETL_LOG_CAPTURE_WARNINGS` | `1` routes `warnings.warn` to the `py.warnings` logger, `0` leaves it | 1 |

An invalid value raises `ValueError` naming the variable; it is never ignored. JSON records carry
`timestamp` (UTC, milliseconds, `Z`), `level`, `logger`, `message`, any `extra` fields, and a structured
`exception` (`type`, `message`, `stack`).

## Level policy

A level states how important an operational event is for the reader of the log. It never stands for the
severity of an anomaly or a fault, which belongs to the scientific record. DEBUG: diagnosis. INFO: stages of a run.
WARNING: a recoverable deviation. ERROR: a failed unit of work. CRITICAL: a run that cannot continue. No per-row or
per-scored-unit logging: the data is serialised in the scientific artifacts, not in logs.

## Not in this change

Rotation and retention (#160), redaction (#159), event schema and correlation identifiers (#157), OpenTelemetry
(#161), and the structlog processors. The existing `src/etl_benchmark/logging_setup.py` and the runners are unchanged.
