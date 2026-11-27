"""Check the MLflow linkage against the real local MLflow server (#168).

Runs synthetic work only: it reads no dataset and runs no detector. It tracks a successful and a
failing run, then compares the link table with what the server stored.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
import mlflow_link as ml  # noqa: E402
import obs_events as oe  # noqa: E402


def check(name: str, problems: list[str]) -> None:
    if problems:
        sys.exit(f"FAIL {name}: " + "; ".join(problems))
    print(f"ok  {name}")


def main() -> None:
    url = f"http://127.0.0.1:{os.environ.get('MLFLOW_PORT', '55000')}"
    client = ml.MlflowRest(url)
    with tempfile.TemporaryDirectory() as work:
        table = ml.LinkTable(Path(work) / "links.sqlite")
        artifact = Path(work) / "synthetic_view.csv"
        artifact.write_text("a,b\n1,2\n3,4\n")
        ids = {"pipeline_run_id": "synthetic-pipeline", "dag_run_id": "synthetic-dag"}
        with oe.bind(trace_id="0af7651916cd43dd8448eb211c80319c", **ids):
            with ml.track(
                client,
                table,
                experiment="etl-platform-synthetic",
                run_name="linkage-ok",
                kind="synthetic",
                params={"rows": "2"},
                artifacts={"view": artifact},
            ) as run:
                run["metrics"]["duration_s"] = 0.25
            try:
                with ml.track(
                    client,
                    table,
                    experiment="etl-platform-synthetic",
                    run_name="linkage-failed",
                    kind="integration",
                ):
                    raise RuntimeError("synthetic failure")
            except RuntimeError:
                pass
        ok, failed = table.rows()
        check("the successful run is tracked", [] if ok["status"] == "FINISHED" else [ok["status"]])
        check("the failed run is marked failed", [] if failed["status"] == "FAILED" else ["not"])
        check("the successful run links to the server", ml.verify(client, ok))
        check("the failed run links to the server", ml.verify(client, failed))
        stored = client.get_run(ok["mlflow_run_id"])
        check(
            "parameters, metric and kind are on the server",
            []
            if stored["metrics"] == {"duration_s": 0.25}
            and stored["params"]["rows"] == "2"
            and stored["tags"]["etl.kind"] == "synthetic"
            else [str(stored)],
        )
        check("no artifact content was uploaded", [] if "view" not in stored["params"] else ["x"])
        try:
            with (
                oe.bind(scientific_run_id="sci-1"),
                ml.track(client, table, experiment="x", run_name="x", kind="synthetic"),
            ):
                pass
            check("a synthetic run cannot carry a scientific run id", ["accepted"])
        except ValueError:
            check("a synthetic run cannot carry a scientific run id", [])


if __name__ == "__main__":
    main()
