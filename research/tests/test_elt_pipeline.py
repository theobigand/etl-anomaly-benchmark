"""The tracked ELT and dbt pipeline with stand-in stages and the MLflow REST fake (#143, #146)."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import elt_pipeline as ep  # noqa: E402
import mlflow_link as ml  # noqa: E402
import obs_events as oe  # noqa: E402
import obs_failures as of  # noqa: E402
from test_mlflow_link import server  # noqa: E402,F401  (the MLflow REST fake)

FAST = {
    "ETL_RETRY_MAX_ATTEMPTS": "3",
    "ETL_RETRY_BASE_DELAY_S": "0.001",
    "ETL_RETRY_MAX_DELAY_S": "0.001",
}


@pytest.fixture
def stages(monkeypatch):
    """Stand-ins that write the two manifests the pipeline digests; calls are recorded."""
    calls = {"elt": 0, "dbt": 0}

    def run_elt(out, seed, rows):
        calls["elt"] += 1
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        manifest = {"run_id": f"elt-{seed}", "rows": rows}
        (out / "manifest.json").write_text(json.dumps(manifest))
        return manifest

    def run_dbt(out, dbt):
        calls["dbt"] += 1
        record = {"invocation_id": "inv-1", "nodes": {"model.a": "success", "test.b": "pass"}}
        (Path(out) / "dbt").mkdir(exist_ok=True)
        (Path(out) / "dbt" / "dbt_run.json").write_text(json.dumps(record))
        return record

    monkeypatch.setattr(ep.elt_duckdb, "run_elt", run_elt)
    monkeypatch.setattr(ep.dbt_runner, "run_dbt", run_dbt)
    return calls


@pytest.fixture
def logging_setup(monkeypatch):
    """The command line configures the process's logging; record that and keep tests isolated."""
    calls = []
    monkeypatch.setattr(ep.obs_logging, "configure", lambda *a, **k: calls.append("configure"))
    monkeypatch.setattr(ep.obs_events, "attach", lambda: calls.append("events"))
    monkeypatch.setattr(ep.obs_redaction, "attach", lambda: calls.append("redaction"))
    return calls


def _events(caplog):
    return [(r.getMessage(), getattr(r, "stage", None)) for r in caplog.records]


def test_a_run_without_mlflow_stores_an_untracked_link_with_the_digests(stages, tmp_path, caplog):
    caplog.set_level("INFO", logger="etl.elt_pipeline")
    summary = ep.run_pipeline(
        tmp_path / "out", 3, 50, link_db=tmp_path / "links.sqlite", dag_run_id="dag-9", env=FAST
    )
    assert summary == {
        "pipeline_run_id": "elt-3-50",
        "dag_run_id": "dag-9",
        "elt_run_id": "elt-3",
        "dbt_invocation_id": "inv-1",
        "mlflow_run_id": None,
        "trace_id": None,
    }
    (row,) = ml.LinkTable(tmp_path / "links.sqlite").rows()
    assert (row["kind"], row["status"]) == ("integration", "UNTRACKED")
    assert (row["pipeline_run_id"], row["dag_run_id"]) == ("elt-3-50", "dag-9")
    assert row["artifact_digests"] == {
        "dbt_run": ml.sha256_file(tmp_path / "out" / "dbt" / "dbt_run.json"),
        "elt_manifest": ml.sha256_file(tmp_path / "out" / "manifest.json"),
    }
    assert _events(caplog) == [
        ("run.started", None),
        ("stage.started", "elt"),
        ("stage.completed", "elt"),
        ("stage.started", "dbt"),
        ("stage.completed", "dbt"),
        ("artifact.written", None),
        ("artifact.written", None),
        ("run.completed", None),
    ]
    assert all(r.pipeline_run_id == "elt-3-50" and r.dag_run_id == "dag-9" for r in caplog.records)
    assert oe.current() == {}


def test_an_mlflow_run_carries_the_identifiers_metrics_and_digests(stages, tmp_path, server):  # noqa: F811
    url = f"http://127.0.0.1:{server.server_port}"
    summary = ep.run_pipeline(
        tmp_path / "out", 1, 10, link_db=tmp_path / "l.sqlite", mlflow_url=url, env=FAST
    )
    assert summary["mlflow_run_id"] == "run1"
    run = server.state["runs"]["run1"]
    assert run["status"] == "FINISHED"
    assert run["tags"]["etl.kind"] == "integration"
    assert run["tags"]["etl.pipeline_run_id"] == "elt-1-10"
    assert run["params"]["seed"] == "1" and run["params"]["rows"] == "10"
    assert set(run["params"]) == {"seed", "rows", "digest.elt_manifest", "digest.dbt_run"}
    assert set(run["metrics"]) == {"elt_duration_s", "dbt_duration_s", "dbt_nodes"}
    assert run["metrics"]["dbt_nodes"] == 2.0
    (row,) = ml.LinkTable(tmp_path / "l.sqlite").rows()
    assert ml.verify(ml.MlflowRest(url), row) == []


def test_an_unreachable_mlflow_server_does_not_stop_the_pipeline(stages, tmp_path):
    summary = ep.run_pipeline(
        tmp_path / "out",
        1,
        10,
        link_db=tmp_path / "l.sqlite",
        mlflow_url="http://127.0.0.1:9",
        env=FAST,
    )
    assert summary["mlflow_run_id"] is None
    (row,) = ml.LinkTable(tmp_path / "l.sqlite").rows()
    assert row["status"] == "UNTRACKED"
    assert set(row["artifact_digests"]) == {"elt_manifest", "dbt_run"}


def test_a_transient_failure_is_retried_and_the_run_still_succeeds(
    stages, tmp_path, monkeypatch, caplog
):
    caplog.set_level("INFO", logger="etl.elt_pipeline")
    real = ep.dbt_runner.run_dbt
    state = {"n": 0}

    def flaky(out, dbt):
        state["n"] += 1
        if state["n"] < 3:
            raise of.InfrastructureFailure("dbt timed out", transient=True)
        return real(out, dbt)

    monkeypatch.setattr(ep.dbt_runner, "run_dbt", flaky)
    ep.run_pipeline(tmp_path / "out", 1, 5, link_db=tmp_path / "l.sqlite", env=FAST)
    retries = [r for r in caplog.records if r.getMessage() == "stage.retrying"]
    assert [r.attempt for r in retries] == [1, 2]
    assert stages["dbt"] == 1  # the real stand-in ran once, after two transient failures
    assert caplog.records[-1].getMessage() == "run.completed"


def test_a_permanent_failure_fails_the_run_once_and_is_not_retried(
    stages, tmp_path, monkeypatch, caplog
):
    caplog.set_level("INFO", logger="etl.elt_pipeline")

    def failing(out, dbt):
        raise of.DataQualityFailure("a data test failed")

    monkeypatch.setattr(ep.dbt_runner, "run_dbt", failing)
    with pytest.raises(of.DataQualityFailure):
        ep.run_pipeline(tmp_path / "out", 1, 5, link_db=tmp_path / "l.sqlite", env=FAST)
    names = [r.getMessage() for r in caplog.records]
    assert "stage.retrying" not in names and "run.completed" not in names
    assert names.count("stage.failed") == 1 and names[-1] == "run.failed"
    failed = caplog.records[-1]
    assert (failed.failure_class, failed.transient) == ("data_quality", False)
    (row,) = ml.LinkTable(tmp_path / "l.sqlite").rows()
    assert row["status"] == "FAILED" and row["artifact_digests"] == {}
    assert oe.current() == {}


def test_exhausted_retries_fail_the_run_and_the_mlflow_run(stages, tmp_path, monkeypatch, server):  # noqa: F811
    def always(out, seed, rows):
        raise of.InfrastructureFailure("disk busy", transient=True)

    monkeypatch.setattr(ep.elt_duckdb, "run_elt", always)
    url = f"http://127.0.0.1:{server.server_port}"
    with pytest.raises(of.InfrastructureFailure):
        ep.run_pipeline(
            tmp_path / "o", 1, 5, link_db=tmp_path / "l.sqlite", mlflow_url=url, env=FAST
        )
    assert server.state["runs"]["run1"]["status"] == "FAILED"
    assert stages["dbt"] == 0  # a failed ELT never reaches dbt
    (row,) = ml.LinkTable(tmp_path / "l.sqlite").rows()
    assert row["status"] == "FAILED"


def test_the_default_run_id_names_the_seed_and_rows():
    assert ep.default_run_id(4, 7) == "elt-4-7"


def test_the_command_line_prints_the_summary_and_returns_the_failure_exit_code(
    stages, tmp_path, capsys, monkeypatch, logging_setup
):
    argv = ["--out", str(tmp_path / "o"), "--link-db", str(tmp_path / "l.sqlite"), "--rows", "5"]
    assert ep.main(argv) == 0
    printed = capsys.readouterr().out
    assert printed == json.dumps(json.loads(printed), indent=1, sort_keys=True) + "\n"
    assert json.loads(printed)["pipeline_run_id"] == "elt-0-5"

    def failing(out, dbt):
        raise of.DataQualityFailure("x")

    monkeypatch.setattr(ep.dbt_runner, "run_dbt", failing)
    assert ep.main(argv) == of.CLASSES["data_quality"]["exit_code"]


def test_the_stages_get_the_arguments_and_the_events_carry_their_fields(
    stages, tmp_path, monkeypatch, caplog
):
    caplog.set_level("INFO", logger="etl.elt_pipeline")
    seen = {}
    real_elt, real_dbt = ep.elt_duckdb.run_elt, ep.dbt_runner.run_dbt
    monkeypatch.setattr(
        ep.elt_duckdb, "run_elt", lambda *a: seen.setdefault("elt", a) and real_elt(*a)
    )
    monkeypatch.setattr(
        ep.dbt_runner, "run_dbt", lambda *a: seen.setdefault("dbt", a) and real_dbt(*a)
    )
    clock = iter([10.0, 12.3456, 20.0, 20.5])
    monkeypatch.setattr(
        ep, "time", SimpleNamespace(monotonic=lambda: next(clock), time=ep.time.time)
    )
    ep.run_pipeline(tmp_path / "out", 4, 9, link_db=tmp_path / "l.sqlite", dbt="my-dbt", env=FAST)
    assert seen == {"elt": (tmp_path / "out", 4, 9), "dbt": (tmp_path / "out", "my-dbt")}
    by_name = {}
    for record in caplog.records:
        by_name.setdefault(record.getMessage(), []).append(record)
    started = by_name["run.started"][0]
    assert (started.seed, started.rows) == (4, 9)
    assert [r.duration_s for r in by_name["stage.completed"]] == [2.346, 0.5]
    done = by_name["run.completed"][0]
    assert (done.elt_run_id, done.dbt_invocation_id) == ("elt-4", "inv-1")
    written = by_name["artifact.written"]
    assert [r.artifact for r in written] == ["manifest.json", "dbt/dbt_run.json"]
    assert written[0].artifact_id == ml.sha256_file(tmp_path / "out" / "manifest.json")
    assert written[1].artifact_id == ml.sha256_file(tmp_path / "out" / "dbt" / "dbt_run.json")


def test_the_run_and_each_stage_open_a_span(stages, tmp_path, monkeypatch):
    import contextlib

    spans = []

    @contextlib.contextmanager
    def span(name, **attributes):
        spans.append((name, attributes))
        yield None

    monkeypatch.setattr(ep.obs_tracing, "span", span)
    ep.run_pipeline(tmp_path / "out", 4, 9, link_db=tmp_path / "l.sqlite", env=FAST)
    assert spans == [
        ("elt_pipeline.run", {"seed": 4, "rows": 9}),
        ("elt_pipeline.elt", {}),
        ("elt_pipeline.dbt", {}),
    ]


def test_the_trace_and_scientific_free_identifiers_reach_the_summary_and_the_link(stages, tmp_path):
    with oe.bind(trace_id="ab" * 16):
        summary = ep.run_pipeline(tmp_path / "o", 1, 5, link_db=tmp_path / "l.sqlite", env=FAST)
    (row,) = ml.LinkTable(tmp_path / "l.sqlite").rows()
    assert summary["trace_id"] == row["trace_id"] == "ab" * 16
    assert row["dag_run_id"] is None and row["scientific_run_id"] is None


def test_a_run_without_a_dag_run_binds_no_dag_run_id(stages, tmp_path, caplog):
    caplog.set_level("INFO", logger="etl.elt_pipeline")
    ep.run_pipeline(tmp_path / "o", 1, 5, link_db=tmp_path / "l.sqlite", env=FAST)
    assert not any(hasattr(r, "dag_run_id") for r in caplog.records)


def test_the_given_run_id_and_the_mlflow_names_are_used(stages, tmp_path, server):  # noqa: F811
    url = f"http://127.0.0.1:{server.server_port}"
    ep.run_pipeline(
        tmp_path / "o", 1, 5, link_db=tmp_path / "l.sqlite", mlflow_url=url, pipeline_run_id="p-7"
    )
    assert set(server.state["experiments"]) == {"elt-synthetic"}
    run = server.state["runs"]["run1"]
    assert run["body"]["run_name"] == "p-7" and run["tags"]["etl.pipeline_run_id"] == "p-7"


def test_the_environment_argument_sets_the_retry_policy(stages, tmp_path, monkeypatch):
    monkeypatch.setenv("ETL_RETRY_MAX_ATTEMPTS", "5")
    calls = []

    def flaky(out, dbt):
        calls.append(1)
        raise of.InfrastructureFailure("busy", transient=True)

    monkeypatch.setattr(ep.dbt_runner, "run_dbt", flaky)
    with pytest.raises(of.InfrastructureFailure):
        ep.run_pipeline(
            tmp_path / "o", 1, 5, link_db=tmp_path / "l.sqlite", env={"ETL_RETRY_MAX_ATTEMPTS": "2"}
        )
    assert len(calls) == 2


def test_the_process_environment_is_the_default_policy(stages, tmp_path, monkeypatch):
    monkeypatch.setenv("ETL_RETRY_MAX_ATTEMPTS", "4")
    monkeypatch.setenv("ETL_RETRY_BASE_DELAY_S", "0.001")
    calls = []

    def flaky(out, dbt):
        calls.append(1)
        raise of.InfrastructureFailure("busy", transient=True)

    monkeypatch.setattr(ep.dbt_runner, "run_dbt", flaky)
    with pytest.raises(of.InfrastructureFailure):
        ep.run_pipeline(tmp_path / "o", 1, 5, link_db=tmp_path / "l.sqlite")
    assert len(calls) == 4


def test_the_command_line_passes_typed_arguments_and_configures_logging(
    stages, tmp_path, monkeypatch, logging_setup
):
    seen = {}

    def fake(out, seed, rows, **options):
        seen.update(out=out, seed=seed, rows=rows, **options)
        return {"pipeline_run_id": "x"}

    monkeypatch.setattr(ep, "run_pipeline", fake)
    base = ["--out", str(tmp_path / "o"), "--link-db", str(tmp_path / "l.sqlite")]
    assert ep.main(base) == 0
    assert logging_setup == ["configure", "events", "redaction"]
    assert seen == {
        "out": tmp_path / "o",
        "seed": 0,
        "rows": 1000,
        "link_db": tmp_path / "l.sqlite",
        "dbt": None,
        "mlflow_url": None,
        "pipeline_run_id": None,
        "dag_run_id": None,
    }
    full = [*base, "--seed", "3", "--rows", "7", "--dbt", "d", "--mlflow-url", "u"]
    ep.main([*full, "--pipeline-run-id", "p", "--dag-run-id", "g"])
    assert (seen["seed"], seen["rows"], seen["dbt"], seen["mlflow_url"]) == (3, 7, "d", "u")
    assert (seen["pipeline_run_id"], seen["dag_run_id"]) == ("p", "g")
    for missing in (["--link-db", "x"], ["--out", "x"]):
        with pytest.raises(SystemExit):
            ep.main(missing)


def test_a_failure_through_the_command_line_is_reported_exactly_once(
    stages, tmp_path, monkeypatch, caplog, logging_setup
):
    caplog.set_level("INFO", logger="etl.elt_pipeline")

    def failing(out, dbt):
        raise of.DataQualityFailure("x")

    monkeypatch.setattr(ep.dbt_runner, "run_dbt", failing)
    argv = ["--out", str(tmp_path / "o"), "--link-db", str(tmp_path / "l.sqlite")]
    assert ep.main(argv) == of.CLASSES["data_quality"]["exit_code"]
    names = [r.getMessage() for r in caplog.records]
    assert names.count("run.failed") == 1
    assert all(r.name == "etl.elt_pipeline" for r in caplog.records)
