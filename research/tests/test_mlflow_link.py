"""MLflow tracking and the link table, against a local fake of the MLflow REST API (#168)."""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mlflow_link as ml  # noqa: E402
import obs_events as oe  # noqa: E402
import obs_failures as of  # noqa: E402


class Fake(BaseHTTPRequestHandler):
    """Just enough of the MLflow 2.0 REST API; state lives on the server object."""

    def log_message(self, *args):
        pass

    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.server.state["requests"].append(("GET", self.path, None))
        url = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        state = self.server.state
        if url.path.endswith("experiments/get-by-name"):
            found = state["experiments"].get(query["experiment_name"])
            if found is None:
                return self._send(404, {"error_code": "RESOURCE_DOES_NOT_EXIST"})
            return self._send(200, {"experiment": {"experiment_id": found}})
        run = state["runs"][query["run_id"]]
        data = {
            name: [{"key": k, "value": v} for k, v in run[name].items()]
            for name in ("tags", "params", "metrics")
            if run[name]
        }
        self._send(200, {"run": {"info": {"status": run["status"]}, "data": data}})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        state = self.server.state
        path = urlparse(self.path).path
        state["requests"].append(("POST", self.path, body))
        if self.headers["Content-Type"] != "application/json":
            return self._send(415, {})
        if state["fail"]:
            return self._send(state["fail"], {})
        if path.endswith("experiments/create"):
            state["experiments"][body["name"]] = str(len(state["experiments"]) + 1)
            return self._send(200, {"experiment_id": state["experiments"][body["name"]]})
        if path.endswith("runs/create"):
            run_id = f"run{len(state['runs']) + 1}"
            state["runs"][run_id] = {
                "status": "RUNNING",
                "tags": {},
                "params": {},
                "metrics": {},
                "body": body,
            }
            return self._send(200, {"run": {"info": {"run_id": run_id}}})
        run = state["runs"][body["run_id"]]
        if path.endswith("runs/log-batch"):
            run["tags"].update({t["key"]: t["value"] for t in body["tags"]})
            run["params"].update({p["key"]: p["value"] for p in body["params"]})
            run["metrics"].update({m["key"]: m["value"] for m in body["metrics"]})
        else:
            run["status"] = body["status"]
        self._send(200, {})


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), Fake)
    httpd.state = {"experiments": {}, "runs": {}, "fail": 0, "requests": []}
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def client(server):
    return ml.MlflowRest(f"http://127.0.0.1:{server.server_port}")


@pytest.fixture
def table(tmp_path):
    return ml.LinkTable(tmp_path / "links.sqlite")


def _t(client, table, kind="synthetic", **more):
    return ml.track(client, table, experiment="e", run_name="r", kind=kind, **more)


def test_a_synthetic_run_is_linked_on_both_sides(client, table, server, tmp_path):
    artifact = tmp_path / "view.csv"
    artifact.write_text("a,b\n1,2\n")
    with (
        oe.bind(pipeline_run_id="pipe-1", dag_run_id="dag-1", trace_id="ab" * 16),
        ml.track(
            client,
            table,
            experiment="synthetic",
            run_name="r",
            kind="synthetic",
            params={"rows": "2"},
            artifacts={"view": artifact},
        ) as run,
    ):
        assert oe.current()["mlflow_run_id"] == "run1"
        run["metrics"]["duration_s"] = 0.5
    (row,) = table.rows()
    assert row["mlflow_run_id"] == "run1" and row["status"] == "FINISHED"
    assert row["artifact_digests"] == {"view": ml.sha256_file(artifact)}
    assert ml.verify(client, row) == []
    stored = server.state["runs"]["run1"]
    assert stored["metrics"] == {"duration_s": 0.5} and stored["params"]["rows"] == "2"
    assert stored["tags"]["etl.trace_id"] == "ab" * 16
    assert "mlflow_run_id" not in oe.current()


def test_a_failing_block_ends_the_run_failed_and_still_stores_the_link(client, table, server):
    with (
        pytest.raises(RuntimeError),
        _t(client, table, "integration"),
    ):
        raise RuntimeError("boom")
    (row,) = table.rows()
    assert row["status"] == "FAILED" and server.state["runs"]["run1"]["status"] == "FAILED"
    assert ml.verify(client, row) == []


def test_an_existing_experiment_is_reused(client, table, server):
    for _ in range(2):
        with ml.track(client, table, experiment="same", run_name="r", kind="synthetic"):
            pass
    assert server.state["experiments"] == {"same": "1"}


def test_a_scientific_run_id_is_only_allowed_on_a_scientific_run(client, table):
    with oe.bind(scientific_run_id="sci-1"):
        with (
            pytest.raises(ValueError, match="must not carry a scientific run id"),
            _t(client, table, "synthetic"),
        ):
            pass
        with _t(client, table, "scientific"):
            pass
    assert table.find(scientific_run_id="sci-1")[0]["kind"] == "scientific"


def test_an_unknown_kind_is_refused(client, table):
    with (
        pytest.raises(ValueError, match="unknown run kind"),
        _t(client, table, "pilot"),
    ):
        pass
    assert table.rows() == []


@pytest.mark.parametrize(
    "params", [{"ground_truth": "x"}, {"note": "uses labels"}, {"api": "token=abc"}]
)
def test_ground_truth_vocabulary_and_secrets_never_reach_the_server(client, table, server, params):
    with (
        pytest.raises(ValueError, match="run refused"),
        _t(client, table, "synthetic", params=params),
    ):
        pass
    assert server.state["runs"] == {} and table.rows() == []


def test_a_metric_that_is_not_a_finite_number_is_refused_and_the_run_is_failed(
    client, table, server
):
    with (
        pytest.raises(ValueError, match="not a finite number"),
        _t(client, table, "synthetic") as run,
    ):
        run["metrics"]["bad"] = float("nan")
    assert server.state["runs"]["run1"]["status"] == "FAILED"
    assert server.state["runs"]["run1"]["metrics"] == {}
    assert table.rows()[0]["status"] == "FAILED"


def test_a_metric_name_that_names_ground_truth_is_refused(client, table):
    with (
        pytest.raises(ValueError, match="ground-truth"),
        _t(client, table, "synthetic") as run,
    ):
        run["metrics"]["y_true"] = 1.0


def test_a_boolean_is_not_a_metric(client, table):
    with (
        pytest.raises(ValueError, match="not a finite number"),
        _t(client, table, "synthetic") as run,
    ):
        run["metrics"]["ok"] = True


def test_an_unreachable_server_degrades_the_run_to_untracked_and_the_work_continues(table):
    dead = ml.MlflowRest("http://127.0.0.1:9", timeout=0.5)
    done = []
    with ml.track(dead, table, experiment="e", run_name="r", kind="synthetic"):
        done.append(1)
    assert done == [1]
    (row,) = table.rows()
    assert row["status"] == "UNTRACKED" and row["mlflow_run_id"] is None
    assert ml.verify(dead, row) == ["the link row has no MLflow run id"]


def test_a_server_error_while_finishing_leaves_the_run_unfinished_in_the_link(
    client, table, server
):
    with _t(client, table, "synthetic"):
        server.state["fail"] = 503
    assert table.rows()[0]["status"] == "UNFINISHED"


def test_a_client_error_is_not_transient(client, server):
    server.state["fail"] = 400
    with pytest.raises(of.InfrastructureFailure) as error:
        client.experiment("new")
    assert error.value.transient is False


def test_a_server_error_is_transient(client, server):
    server.state["fail"] = 500
    with pytest.raises(of.InfrastructureFailure) as error:
        client.experiment("new")
    assert error.value.transient is True


def test_verify_reports_every_difference(client, table, server, tmp_path):
    artifact = tmp_path / "a.bin"
    artifact.write_bytes(b"x")
    with (
        oe.bind(pipeline_run_id="pipe-1"),
        ml.track(
            client, table, experiment="e", run_name="r", kind="synthetic", artifacts={"a": artifact}
        ),
    ):
        pass
    (row,) = table.rows()
    run = server.state["runs"]["run1"]
    run["tags"]["etl.pipeline_run_id"] = "other"
    run["tags"]["etl.kind"] = "scientific"
    run["params"]["digest.a"] = "0" * 64
    run["status"] = "FAILED"
    assert ml.verify(client, row) == [
        "pipeline_run_id differs between the link row and the MLflow tags",
        "kind differs between the link row and the MLflow tags",
        "digest of a differs from the one on the MLflow run",
        "status FINISHED differs from MLflow status FAILED",
    ]


def test_the_link_table_survives_reopening_and_finds_rows_by_identifier(client, tmp_path):
    path = tmp_path / "t.sqlite"
    with oe.bind(dag_run_id="dag-9"), _t(client, ml.LinkTable(path)):
        pass
    again = ml.LinkTable(path)
    assert [r["mlflow_run_id"] for r in again.find(dag_run_id="dag-9")] == ["run1"]
    assert again.find(dag_run_id="none") == []


def test_the_timestamps_come_from_the_injected_clock(client, table, server):
    ticks = iter([10.0, 12.5])
    with ml.track(
        client, table, experiment="e", run_name="r", kind="synthetic", clock=lambda: next(ticks)
    ):
        pass
    assert server.state["runs"]["run1"]["body"]["start_time"] == 10000
    assert table.rows()[0]["created_at"] == 12.5


def test_sha256_file_matches_hashlib(tmp_path):
    path = tmp_path / "f"
    path.write_bytes(b"abc" * 400_000)
    import hashlib

    assert ml.sha256_file(path) == hashlib.sha256(b"abc" * 400_000).hexdigest()


def test_the_exact_requests_of_one_run_are_sent_with_a_json_content_type(client, table, server):
    ticks = iter([1.5, 2.5])
    with (
        oe.bind(pipeline_run_id="p1"),
        ml.track(
            client,
            table,
            experiment="exp",
            run_name="name",
            kind="synthetic",
            params={"k": "v"},
            clock=lambda: next(ticks),
        ) as run,
    ):
        run["metrics"]["m"] = 2
    assert server.state["requests"] == [
        ("GET", "/api/2.0/mlflow/experiments/get-by-name?experiment_name=exp", None),
        ("POST", "/api/2.0/mlflow/experiments/create", {"name": "exp"}),
        (
            "POST",
            "/api/2.0/mlflow/runs/create",
            {"experiment_id": "1", "run_name": "name", "start_time": 1500},
        ),
        (
            "POST",
            "/api/2.0/mlflow/runs/log-batch",
            {
                "run_id": "run1",
                "tags": [
                    {"key": "etl.kind", "value": "synthetic"},
                    {"key": "etl.pipeline_run_id", "value": "p1"},
                ],
                "params": [{"key": "k", "value": "v"}],
                "metrics": [{"key": "m", "value": 2, "timestamp": 2500, "step": 0}],
            },
        ),
        (
            "POST",
            "/api/2.0/mlflow/runs/update",
            {"run_id": "run1", "status": "FINISHED", "end_time": 2500},
        ),
    ]


def test_a_trailing_slash_in_the_base_url_is_ignored_and_the_timeout_is_kept(server):
    client = ml.MlflowRest(f"http://127.0.0.1:{server.server_port}//")
    assert client.timeout == 10.0 and ml.MlflowRest("http://x", 3).timeout == 3
    assert client.experiment("a") == "1"


def test_a_run_without_tags_params_or_metrics_reads_back_empty(client, server):
    run_id = client.create_run(client.experiment("e"), "r", 0)
    assert client.get_run(run_id) == {"status": "RUNNING", "tags": {}, "params": {}, "metrics": {}}


def test_failures_name_the_call_and_the_cause(client, server):
    server.state["fail"] = 404
    with pytest.raises(
        of.InfrastructureFailure, match="^MLflow POST experiments/create answered 404$"
    ):
        client.experiment("new")
    dead = ml.MlflowRest("http://127.0.0.1:9", timeout=0.5)
    with pytest.raises(of.InfrastructureFailure, match="^MLflow unreachable: "):
        dead.experiment("x")


def test_every_correlation_identifier_is_compared_by_verify(client, table, server):
    ids = {
        "scientific_run_id": "s1",
        "pipeline_run_id": "p1",
        "dag_run_id": "d1",
        "trace_id": "ab" * 16,
    }
    with oe.bind(**ids), ml.track(client, table, experiment="e", run_name="r", kind="scientific"):
        pass
    (row,) = table.rows()
    assert ml.verify(client, row) == []
    for name in ids:
        server.state["runs"]["run1"]["tags"][f"etl.{name}"] = "other"
        assert ml.verify(client, row) == [
            f"{name} differs between the link row and the MLflow tags"
        ]
        server.state["runs"]["run1"]["tags"][f"etl.{name}"] = ids[name]


def test_the_refusal_lists_every_finding(client, table):
    with (
        pytest.raises(ValueError) as error,
        ml.track(
            client,
            table,
            experiment="e",
            run_name="r",
            kind="synthetic",
            params={"ground_truth": "x", "tok": "token=abc"},
        ),
    ):
        pass
    assert str(error.value) == (
        "synthetic run refused: params ground_truth: field name names a ground-truth concept; "
        "params tok: 'token=abc' contains a secret"
    )


def test_link_ids_increase_and_digests_are_stored_sorted(table):
    first = table.add(
        {
            "kind": "synthetic",
            "status": "X",
            "created_at": 1,
            "artifact_digests": {"b": "1", "a": "2"},
        }
    )
    second = table.add({"kind": "synthetic", "status": "X", "created_at": 2})
    assert (first, second) == (1, 2)
    import sqlite3

    stored = sqlite3.connect(table.path).execute("select artifact_digests from links").fetchall()
    assert stored == [('{"a": "2", "b": "1"}',), ("{}",)]
