# Logging configuration (#156)

`research/obs_logging.py` is the single configuration of the platform tooling's operational logs. It uses the
standard library only, needs no infrastructure, and sits outside `src/` and the top-level `experiments/` scripts:
those files are in the scientific fingerprint, so adopting it there is a separate decision with a replay of the
archived experiments (ADR-0001, `docs/architecture/`). The event schema and correlation identifiers (#157) build
on this module and are described [below](#event-schema-v1-and-correlation-identifiers-157).

```python
import obs_logging

obs_logging.configure()  # reads ETL_LOG_*; replaces only its own handler
```

| Variable | Values | Default |
|---|---|---|
| `ETL_LOG_LEVEL` | DEBUG, INFO, WARNING, ERROR, CRITICAL | INFO |
| `ETL_LOG_FORMAT` | `console` (readable, UTC), `json` (one object per line) | console |
| `ETL_LOG_DEST` | `stderr`, `stdout`, `file` (needs `ETL_LOG_FILE`) | stderr |
| `ETL_LOG_MAX_BYTES` | size at which a file log rotates (integer of at least 1) | 10485760 (10 MiB) |
| `ETL_LOG_BACKUPS` | numbered backups kept, `app.log.1`... (integer of at least 0) | 5 |
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

## Event schema v1 and correlation identifiers (#157)

`research/obs_events.py` adds a versioned event schema, correlation identifiers and a structlog layer. It uses the
standard library; structlog is optional (`pip install --group observability`, ADR-0017) and only
`configure_structlog()` needs it. It is outside the scientific fingerprint like `obs_logging`.

```python
import logging, obs_events, obs_logging

obs_logging.configure()
obs_events.attach()  # every record now carries the bound identifiers
with obs_events.bind(scientific_run_id="run-7", pipeline_run_id="p-1"):
    obs_events.emit(logging.getLogger("etl.load"), "stage.completed", stage="load", rows=12)
```

**Record layout.** `obs_logging` writes `timestamp` (UTC), `level`, `logger`, `message` (the event name) and, for a
failure, `exception`. The event adds `schema_version` (1), `event`, the bound identifiers and the caller's fields.
Identifiers appear only when known: nothing is generated or invented, and no new trace identifier is created at a
component boundary. A caller field may not reuse `schema_version`, `event`, an identifier name, or a `LogRecord`
attribute; an unregistered event name is refused. Event names are `domain.action`, lower case, and stable once
published; add a name to `EVENTS` rather than renaming one. Registered in v1: `run.started|completed|failed`,
`stage.started|completed|failed`, `artifact.written`, `subprocess.started|completed`. Failures are logged with
`exc_info=True`, which produces the structured `exception` object. The level follows the registry
(`*.failed` is ERROR) unless the caller passes one.

| Identifier | Meaning | Format |
|---|---|---|
| `scientific_run_id` | the archived scientific run the work belongs to | `[A-Za-z0-9._:+=-]{1,128}` |
| `mlflow_run_id` | MLflow run | same |
| `pipeline_run_id` | ETL pipeline run | same |
| `dag_run_id` | orchestrator DAG run | same (an Airflow run id such as `manual__2026-11-26T10:00:00+00:00` fits) |
| `trace_id` | distributed trace | 32 lower-case hex digits, not all zero |
| `artifact_id` | artifact (digest or registered name) | `[A-Za-z0-9._:+=-]{1,128}` |
| `telemetry_dataset_id` | telemetry dataset | same |

**Propagation.** Identifiers live in a `contextvars` variable, so they follow the calling thread, copied contexts
and asyncio tasks. A child process inherits them through `environ(base)` (variables `ETL_CORR_<NAME>`) and
`adopt()` at its start; an invalid `ETL_CORR_*` value or an unknown name raises `ValueError` naming the variable.
`tests/test_obs_events.py` runs a real subprocess and reads its JSON log.

| System | Propagation | Status |
|---|---|---|
| This tooling (subprocess) | native: `ETL_CORR_*` through `environ` and `adopt` | tested with a real subprocess |
| W3C trace context | adapter: `TRACEPARENT` provides `trace_id` (a malformed value is ignored) | tested on the variable only |
| MLflow | adapter: `MLFLOW_RUN_ID` provides `mlflow_run_id` | tested on the variable only |
| Airflow | adapter: `AIRFLOW_CTX_DAG_RUN_ID` provides `dag_run_id` | tested on the variable only |

The three adapters read documented environment variables of those systems. They are tested on the variables, and
end to end through the local Airflow and MLflow of the runtime profiles (`platform/orchestration_check.sh`, 2026-11-27;
see [RUNTIME.md](RUNTIME.md)): a BashOperator task of a real DAG run logs the `dag_run_id` that Airflow exported
(`AIRFLOW_CTX_DAG_RUN_ID`), a task that creates a run on the MLflow server logs that run's `mlflow_run_id` together with the
`dag_run_id`, and a subprocess started with `oe.environ()` logs the identifiers its parent bound (`ETL_CORR_*`), including a
`trace_id`. The `TRACEPARENT` adapter is tested on the variable only; no tracing service sends it yet (#167). `ETL_CORR_*` values override the adapted ones.

**structlog.** `configure_structlog()` installs two processors and routes structlog through the standard library, so
`obs_logging` still formats and writes every record: `structlog_processor` validates the event name and adds the schema
and identifiers, and a last processor makes the event name the message while keeping it as a field. Call
`structlog.get_logger().info("stage.started", rows=3)`. Without the package the call raises a `RuntimeError` giving
the install command; the rest of the module is unaffected.

## Redaction and ground-truth isolation (#159)

`research/obs_redaction.py` cleans every record before any formatter, file, export or dashboard sees it. Install it
after `obs_logging.configure()` with `obs_redaction.attach()`; it runs after the correlation filter whatever the call
order.

- **Allowlist first.** Only the names in `obs_redaction.ALLOWED` (schema keys, correlation identifiers, `stage`,
  `rows`, `code`, `attempt`, `max_attempts`, `retry`, `duration_ms`, `failure_class`, `final_status`) with scalar values
  survive. Any other field, and any list, mapping or bytes value, is removed and counted in `dropped_fields`, so a raw row,
  a held-out label or an unknown attribute cannot be logged by accident. Text is cut at 500 characters. To log a new
  field, add its name to `ALLOWED` in a reviewed change.
- **Secrets.** `password=`, `token=`, `api_key=`, `authorization:` and similar assignments, bearer credentials,
  credentials inside URLs, AWS access keys and GitHub tokens become `[REDACTED]` in the message, string fields, exception
  message and stack. The exception type and the stack frames stay.
- **Ground truth.** The words `ground_truth`, `y_true`, `is_anomaly`, `anomaly_label`, `fault_mask`, `injected`,
  `injection`, `held-out`, `holdout` and `label(s)` are replaced by `[REDACTED]` in the same text and in paths, so
  telemetry that a detector can read cannot name the injected fault. Whole-word matching leaves `labelled` and
  `labeler` alone. The cost is that a legitimate log line about labels is blurred; scientific records, not logs, carry
  that information.
- **Leakage audit.** `obs_redaction.audit(record)` returns the findings in the names, text values, paths and ids of one
  record and `audit_vocabulary()` checks the registered event names and identifier names; both are tested. Dashboards,
  exports and embeddings must be built from records that passed the filter; those consumers do not exist yet (#161 and
  later), so only the log path is covered here.

Limits: the filter cannot recognise a secret that has no keyword or known prefix, and it does not inspect values inside
non-scalar fields because it removes them. The scientific runners still use their own logging until a separate, replayed
decision adopts this layer.

## Failure handling and bounded retries (#158)

`research/obs_failures.py` classifies failures, retries only what is safe to retry, and keeps failures visible.

| Class | Exit code | Meaning | Retried |
|---|---|---|---|
| `infrastructure` | 75 | storage, network, memory or service failure | only when transient |
| `processing` | 1 | a pipeline step failed on valid input | no |
| `data_quality` | 65 | the input violates a declared expectation | no |
| `detector` | 2 | a detector failed to fit or score | no |
| `inapplicability` | 3 | a protocol or unit does not apply | no |
| `injected` | 4 | a fault injected on purpose for a test | no |
| `unexpected` | 70 | an error nobody classified | no |

- **Classification is explicit.** Raise `InfrastructureFailure` (transient by default), `ProcessingFailure`,
  `DataQualityFailure`, `DetectorFailure`, `InapplicableFailure` or `InjectedFailure`, chaining the cause with
  `raise ... from error`. `ConnectionError`, `TimeoutError` and `InterruptedError` are transient infrastructure failures,
  other `OSError` and `MemoryError` permanent ones, and everything else is `unexpected`: an unclassified exception is never
  reported as a data anomaly.
- **Bounded retries.** `run_with_retries(call, stage=..., policy=..., idempotent=True, logger=...)` retries a transient
  failure of a call declared idempotent, at most `ETL_RETRY_MAX_ATTEMPTS` times (default 3), with a delay of
  `ETL_RETRY_BASE_DELAY_S` (0.5) doubling up to `ETL_RETRY_MAX_DELAY_S` (30), no jitter, and within the optional total
  `ETL_RETRY_DEADLINE_S`. Permanent failures, non-idempotent calls and `KeyboardInterrupt` are never retried. A call that
  hangs needs its own timeout; this helper does not interrupt it.
- **Events.** Each retry logs `stage.retrying` (WARNING) with `stage`, `attempt`, `max_attempts`, `failure_class`,
  `transient`, `retry` and `delay_s`; a retry that eventually succeeds logs `stage.completed` with `final_status`
  `recovered`; the terminal failure logs one `stage.failed` (ERROR) with the structured exception and `final_status`
  `failed`, `exhausted` or `deadline`. Correlation identifiers ride on every event. The original exception is re-raised
  with a note, so its type and chain are intact; nothing is converted into a success.
- **No duplicate logging.** `log_failure` marks an exception as reported; the layers above can call it or `run_guarded`
  without producing a second record.
- **Visible in orchestration.** `run_guarded(main, stage=..., logger=...)` returns the exit code of the failure class, so a
  scheduler sees a non-zero status, and logs `run.failed` unless a lower layer already reported the failure. Through
  the local Airflow (`platform/orchestration_check.sh`, synthetic tasks, no dataset): a transient failure retried twice
  ends `success` with two `stage.retrying` events and a `recovered` completion; retries stopped at the limit end `failed`
  with an `exhausted` failure of class `infrastructure`; a data-quality failure ends `failed` with exit code 65, no retry
  and a `run.failed` event of class `data_quality`; the task downstream of it is `upstream_failed`, and the DAG run is
  `failed`. Every event carries the `dag_run_id`.
- **Not changed.** The archived runners keep their recorded-outcome handling: the audit lists the `except Exception`
  blocks that turn a failure into scientific data (disclosed errors, ineligibility reasons) as "keep". This module does not
  replace them.

## Log lifecycle (#160)

Rotation is `obs_logging` (a file destination uses a size-rotating handler; stream destinations have none). Everything
else is `research/obs_lifecycle.py`, which works on one log file and its numbered backups `<log>.N` and on nothing else.

| Variable | Meaning | Default |
|---|---|---|
| `ETL_LOG_RETENTION_DAYS` | a backup older than this is removed | 14 |
| `ETL_LOG_BUDGET_BYTES` | active file plus backups; the oldest backups are removed until it is met, the active file never | 104857600 (100 MiB) |
| `ETL_LOG_PROTECTED` | extra protected paths relative to the repository root, `os.pathsep` separated | none |

```python
import datetime, pathlib, obs_lifecycle as lc

lc.install_shutdown()  # SIGTERM flushes the log and exits with code 143
chosen = lc.settings(os.environ)
lc.prune(
    log_file,
    now=datetime.datetime.now(datetime.UTC),
    root=repo_root,
    retention_days=chosen["retention_days"],
    budget_bytes=chosen["budget_bytes"],
    protected=chosen["protected"],
)
```

- **Evidence is out of reach.** `docs/thesis-remediation/evidence`, `verification/evidence` and `experiments/results`
  (plus `ETL_LOG_PROTECTED`) are protected: if the log folder is inside one, contains one, or resolves into one through a
  symbolic link, `prune` and `export_sanitized` raise before deleting anything. Scientific evidence retention is not
  decided by this module and no cleanup of it exists.
- **Sanitized exports are separate.** `export_sanitized(log_file, folder, now=..., root=...)` writes the JSON lines that
  pass `obs_redaction.audit`, backups first, to `<folder>/<log>-<YYYYMMDD>.jsonl` with a `.sha256` sidecar. It counts
  the lines it skipped (not JSON, a secret, ground-truth vocabulary), never overwrites, refuses the log folder, and
  `prune` never touches an export, so selected exports live independently of the rotation.
- **Shutdown.** Handlers flush after every record; `shutdown()` flushes and closes the `obs_logging` handler and leaves
  foreign handlers alone, and `install_shutdown()` does it on SIGTERM and exits with `128 + signal`. SIGKILL cannot be
  caught.
- Nothing schedules `prune`: a caller (a run wrapper, or a scheduler profile of #142) invokes it.

## Not in this change

OpenTelemetry (#161), and the adoption of the schema by the scientific runners (a separate
replayed decision). The existing `src/etl_benchmark/logging_setup.py` and the runners are unchanged.
