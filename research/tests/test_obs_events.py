"""Event schema v1, correlation identifiers and their propagation (#157)."""

import io
import json
import logging
import subprocess
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import obs_events as oe  # noqa: E402
import obs_logging as ol  # noqa: E402

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"


@pytest.fixture(autouse=True)
def clean_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    for handler in [h for h in root.handlers if h not in handlers]:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(level)


def _json_logger(**env):
    stream = io.StringIO()
    ol.configure({"ETL_LOG_FORMAT": "json", **env}, stream=stream)
    oe.attach()
    return logging.getLogger("etl.events"), stream


def test_no_identifier_is_invented_when_none_is_bound():
    assert oe.current() == {}
    body = oe.build("run.started", {})
    assert body == {"schema_version": 1, "event": "run.started"}


def test_bound_identifiers_are_added_and_restored_on_exit():
    with oe.bind(scientific_run_id="run-7", trace_id=TRACE):
        with oe.bind(artifact_id="sha256:ab12", trace_id=None):
            assert oe.current() == {
                "scientific_run_id": "run-7",
                "trace_id": TRACE,
                "artifact_id": "sha256:ab12",
            }
        assert "artifact_id" not in oe.current()
    assert oe.current() == {}


def test_an_inner_binding_overrides_and_the_outer_value_returns():
    with oe.bind(pipeline_run_id="outer"):
        with oe.bind(pipeline_run_id="inner"):
            assert oe.current()["pipeline_run_id"] == "inner"
        assert oe.current()["pipeline_run_id"] == "outer"


@pytest.mark.parametrize(
    ("ids", "message"),
    [
        ({"run_id": "x"}, "unknown correlation identifier 'run_id'"),
        ({"dag_run_id": ""}, "dag_run_id"),
        ({"dag_run_id": "a b"}, "dag_run_id"),
        ({"dag_run_id": "x" * 129}, "dag_run_id"),
        ({"dag_run_id": 12}, "dag_run_id"),
        ({"trace_id": TRACE.upper()}, "trace_id"),
        ({"trace_id": "0" * 32}, "trace_id"),
        ({"trace_id": TRACE[:-1]}, "trace_id"),
    ],
)
def test_an_invalid_identifier_is_refused_by_name(ids, message):
    with pytest.raises(ValueError, match=message), oe.bind(**ids):
        pass
    assert oe.current() == {}


def test_an_airflow_style_run_id_is_accepted():
    run_id = "manual__2026-11-26T10:00:00+00:00"
    with oe.bind(dag_run_id=run_id):
        assert oe.current()["dag_run_id"] == run_id


def test_event_names_are_a_registered_stable_vocabulary():
    assert "run.started" in oe.EVENTS and "run.failed" in oe.EVENTS
    for name, (level, description) in oe.EVENTS.items():
        assert oe.NAME.fullmatch(name) and level in ol.LEVELS and description
    with pytest.raises(ValueError, match="unregistered event 'run.unknown'"):
        oe.build("run.unknown", {})


def test_a_field_cannot_overwrite_a_reserved_key():
    for key in ("event", "schema_version", "trace_id", "level", "timestamp", "message"):
        with pytest.raises(ValueError, match=f"reserved field '{key}'"):
            oe.build("run.started", {key: "x"})


def test_emit_writes_one_json_line_with_schema_event_ids_and_fields():
    log, stream = _json_logger()
    with oe.bind(scientific_run_id="run-7", trace_id=TRACE):
        oe.emit(log, "stage.completed", stage="load", rows=12)
    (line,) = stream.getvalue().splitlines()
    record = json.loads(line)
    assert record["schema_version"] == 1 and record["event"] == "stage.completed"
    assert record["message"] == "stage.completed" and record["level"] == "INFO"
    assert (record["stage"], record["rows"]) == ("load", 12)
    assert record["scientific_run_id"] == "run-7" and record["trace_id"] == TRACE
    assert record["timestamp"].endswith("Z")


def test_the_default_level_follows_the_registry_and_can_be_overridden():
    log, stream = _json_logger()
    oe.emit(log, "run.failed")
    oe.emit(log, "run.failed", level=logging.WARNING)
    first, second = (json.loads(line) for line in stream.getvalue().splitlines())
    assert (first["level"], second["level"]) == ("ERROR", "WARNING")


def test_a_failure_event_carries_the_structured_exception():
    log, stream = _json_logger()
    try:
        raise KeyError("missing")
    except KeyError:
        oe.emit(log, "stage.failed", stage="load", exc_info=True)
    record = json.loads(stream.getvalue())
    assert record["exception"]["type"] == "KeyError" and record["event"] == "stage.failed"


def test_plain_log_calls_also_carry_the_bound_identifiers():
    log, stream = _json_logger()
    with oe.bind(pipeline_run_id="p-1"):
        log.info("free text")
    log.info("outside")
    inside, outside = (json.loads(line) for line in stream.getvalue().splitlines())
    assert inside["pipeline_run_id"] == "p-1" and "pipeline_run_id" not in outside


def test_an_explicit_record_value_is_not_replaced_by_the_context():
    log, stream = _json_logger()
    with oe.bind(pipeline_run_id="ctx"):
        log.info("x", extra={"pipeline_run_id": "explicit"})
    assert json.loads(stream.getvalue())["pipeline_run_id"] == "explicit"


def test_attach_is_idempotent_and_leaves_foreign_handlers_alone():
    root = logging.getLogger()
    foreign = logging.NullHandler()
    root.addHandler(foreign)
    try:
        ol.configure({}, stream=io.StringIO())
        for _ in range(3):
            oe.attach()
        (ours,) = [h for h in root.handlers if getattr(h, ol.MARK, False)]
        assert sum(isinstance(f, oe.CorrelationFilter) for f in ours.filters) == 1
        assert foreign.filters == []
    finally:
        root.removeHandler(foreign)


def test_environ_exports_only_bound_identifiers_and_keeps_the_base():
    assert oe.environ({"A": "1"}) == {"A": "1"}
    with oe.bind(mlflow_run_id="abc123", trace_id=TRACE):
        env = oe.environ({"A": "1"})
    assert env == {"A": "1", "ETL_CORR_MLFLOW_RUN_ID": "abc123", "ETL_CORR_TRACE_ID": TRACE}


def test_from_environ_reads_the_etl_variables_and_refuses_invalid_ones():
    env = {"ETL_CORR_DAG_RUN_ID": "r1", "ETL_CORR_TELEMETRY_DATASET_ID": "t1", "PATH": "/bin"}
    assert oe.from_environ(env) == {"dag_run_id": "r1", "telemetry_dataset_id": "t1"}
    with pytest.raises(ValueError, match="ETL_CORR_TRACE_ID"):
        oe.from_environ({"ETL_CORR_TRACE_ID": "nope"})
    with pytest.raises(ValueError, match="unknown correlation identifier"):
        oe.from_environ({"ETL_CORR_FOO": "x"})


def test_native_variables_of_other_systems_are_adapted_and_etl_values_win():
    env = {
        "TRACEPARENT": f"00-{TRACE}-00f067aa0ba902b7-01",
        "MLFLOW_RUN_ID": "ml-9",
        "AIRFLOW_CTX_DAG_RUN_ID": "scheduled__x",
    }
    assert oe.from_environ(env) == {
        "trace_id": TRACE,
        "mlflow_run_id": "ml-9",
        "dag_run_id": "scheduled__x",
    }
    env["ETL_CORR_MLFLOW_RUN_ID"] = "explicit"
    assert oe.from_environ(env)["mlflow_run_id"] == "explicit"


@pytest.mark.parametrize(
    "value", ["", "00-short-00f067aa0ba902b7-01", f"00-{'0' * 32}-00f067aa0ba902b7-01", "x"]
)
def test_a_malformed_foreign_traceparent_is_ignored_not_fatal(value):
    assert oe.from_environ({"TRACEPARENT": value}) == {}


def test_adopt_binds_the_inherited_identifiers_in_the_process():
    ids = oe.adopt({"ETL_CORR_SCIENTIFIC_RUN_ID": "run-7"})
    try:
        assert ids == {"scientific_run_id": "run-7"}
        assert oe.current() == ids
    finally:
        oe.reset()
    assert oe.current() == {}


def test_identifiers_cross_a_subprocess_boundary_into_its_json_log():
    code = (
        "import logging, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import obs_events as oe, obs_logging as ol\n"
        "ol.configure({'ETL_LOG_FORMAT': 'json', 'ETL_LOG_DEST': 'stdout'})\n"
        "oe.attach(); oe.adopt()\n"
        "oe.emit(logging.getLogger('etl.child'), 'subprocess.completed', code=0)\n"
    )
    with oe.bind(scientific_run_id="run-7", trace_id=TRACE):
        env = oe.environ({"PATH": ""})
    out = subprocess.run(
        [sys.executable, "-c", code, str(Path(oe.__file__).parent)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    record = json.loads(out)
    assert record["scientific_run_id"] == "run-7" and record["trace_id"] == TRACE
    assert record["event"] == "subprocess.completed" and record["code"] == 0


def test_the_structlog_processor_validates_the_event_and_adds_schema_and_ids():
    with oe.bind(artifact_id="a-1"):
        out = oe.structlog_processor(None, "info", {"event": "artifact.written", "path": "x"})
    assert out == {
        "event": "artifact.written",
        "path": "x",
        "schema_version": 1,
        "artifact_id": "a-1",
    }
    with pytest.raises(ValueError, match="unregistered event"):
        oe.structlog_processor(None, "info", {"event": "free text"})
    with pytest.raises(ValueError, match="reserved field 'trace_id'"):
        oe.structlog_processor(None, "info", {"event": "run.started", "trace_id": TRACE})


def test_the_module_imports_without_structlog_and_configuring_it_says_how_to_install(monkeypatch):
    monkeypatch.setitem(sys.modules, "structlog", None)
    message = (
        "^structlog is not installed; install the optional group: "
        r"pip install --group observability \(see \[dependency-groups\] in pyproject.toml\)$"
    )
    with pytest.raises(RuntimeError, match=message):
        oe.configure_structlog()


def test_structlog_events_reach_the_json_log_through_the_same_schema():
    structlog = pytest.importorskip("structlog")
    _, stream = _json_logger()
    oe.configure_structlog()
    try:
        with oe.bind(pipeline_run_id="p-1"):
            structlog.get_logger("etl.struct").bind(stage="load").info("stage.started", rows=3)
    finally:
        structlog.reset_defaults()
    record = json.loads(stream.getvalue())
    assert record["event"] == "stage.started" and record["schema_version"] == 1
    assert (record["stage"], record["rows"], record["pipeline_run_id"]) == ("load", 3, "p-1")
    assert record["level"] == "INFO" and record["message"] == "stage.started"


def test_a_field_named_like_a_log_record_attribute_is_refused_not_a_logging_error():
    with pytest.raises(ValueError, match="reserved field 'name'"):
        oe.build("run.started", {"name": "x"})


def test_a_structlog_failure_event_carries_the_structured_exception():
    structlog = pytest.importorskip("structlog")
    _, stream = _json_logger()
    oe.configure_structlog()
    try:
        try:
            raise KeyError("missing")
        except KeyError:
            structlog.get_logger("etl.struct").exception("stage.failed", stage="load")
    finally:
        structlog.reset_defaults()
    record = json.loads(stream.getvalue())
    assert record["event"] == "stage.failed" and record["level"] == "ERROR"
    assert record["exception"]["type"] == "KeyError"


def test_adopt_reads_the_process_environment_by_default(monkeypatch):
    monkeypatch.setenv("ETL_CORR_PIPELINE_RUN_ID", "p-9")
    try:
        assert oe.adopt() == {"pipeline_run_id": "p-9"}
        assert oe.current() == {"pipeline_run_id": "p-9"}
    finally:
        oe.reset()


def test_adopt_adds_to_what_is_already_bound():
    with oe.bind(artifact_id="a-1"):
        oe.adopt({"ETL_CORR_PIPELINE_RUN_ID": "p-9"})
        assert oe.current() == {"artifact_id": "a-1", "pipeline_run_id": "p-9"}


def test_the_processor_passes_exc_info_through_without_treating_it_as_a_field():
    out = oe.structlog_processor(None, "error", {"event": "stage.failed", "exc_info": True})
    assert out == {"schema_version": 1, "event": "stage.failed", "exc_info": True}
    assert "exc_info" not in oe.structlog_processor(None, "info", {"event": "run.started"})


def test_the_last_processor_makes_the_event_the_message_and_a_field():
    event = {"event": "stage.started", "schema_version": 1, "rows": 3, "exc_info": True}
    assert oe._to_log_kwargs(None, "info", event) == {
        "msg": "stage.started",
        "exc_info": True,
        "extra": {"event": "stage.started", "schema_version": 1, "rows": 3},
    }
    assert oe._to_log_kwargs(None, "info", {"event": "run.started"}) == {
        "msg": "run.started",
        "extra": {"event": "run.started"},
    }


def test_configure_structlog_installs_the_schema_processors_on_the_stdlib(monkeypatch):
    seen = {}
    stdlib = types.SimpleNamespace(LoggerFactory=lambda: "factory", BoundLogger="bound")
    fake = types.SimpleNamespace(stdlib=stdlib, configure=lambda **kw: seen.update(kw))
    monkeypatch.setitem(sys.modules, "structlog", fake)
    oe.configure_structlog()
    assert seen == {
        "processors": [oe.structlog_processor, oe._to_log_kwargs],
        "logger_factory": "factory",
        "wrapper_class": "bound",
        "cache_logger_on_first_use": False,
    }
