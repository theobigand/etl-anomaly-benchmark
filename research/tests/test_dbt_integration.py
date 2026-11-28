"""dbt build over the DuckDB ELT output with the real dbt (#146). Needs DBT_BIN and duckdb."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dbt_runner as dr  # noqa: E402
import elt_duckdb as elt  # noqa: E402


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("platform") / "elt"
    elt.run_elt(out, seed=1, rows=300)
    return out, dr.run_dbt(out, os.environ["DBT_BIN"])


def test_dbt_build_passes_every_model_and_test(built):
    _, record = built
    assert set(record["nodes"].values()) <= {"success", "pass"}
    assert sum(name.startswith("model.") for name in record["nodes"]) == 3
    assert sum(name.startswith("test.") for name in record["nodes"]) == 8


def test_the_record_links_the_dbt_invocation_to_the_elt_run(built):
    out, record = built
    elt_manifest = json.loads((out / "manifest.json").read_text())
    assert record["elt_run_id"] == elt_manifest["run_id"]
    assert len(record["invocation_id"]) == 36
    assert json.loads((out / "dbt" / "dbt_run.json").read_text()) == record


def test_the_lineage_runs_from_the_raw_source_to_the_mart(built):
    _, record = built
    lineage = record["lineage"]
    assert lineage["model.orders.stg_orders"] == ["source.orders.elt.raw_orders"]
    assert lineage["model.orders.int_order_units"] == ["model.orders.stg_orders"]
    assert lineage["model.orders.mart_tier_summary"] == ["model.orders.int_order_units"]


def test_the_dbt_mart_equals_the_duckdb_mart(built):
    import duckdb

    out, _ = built
    connection = duckdb.connect(str(out / "dbt" / "orders.duckdb"), read_only=True)
    dbt_rows = connection.execute("select * from mart_tier_summary order by tier").fetchall()
    elt_rows = connection.execute(
        f"select * from read_parquet('{out / 'marts/orders_by_tier.parquet'}') order by tier"
    ).fetchall()
    assert dbt_rows == elt_rows


def test_a_corrupted_mart_makes_the_singular_test_fail(tmp_path):
    out = tmp_path / "elt"
    elt.run_elt(out, seed=1, rows=300)
    import duckdb

    marts = out / "marts" / "orders_by_tier.parquet"
    connection = duckdb.connect()
    connection.execute(
        f"copy (select tier, orders + 1 as orders, units, amount from read_parquet('{marts}')) "
        f"to '{marts}' (format parquet)"
    )
    with pytest.raises(dr.DbtError, match="test.orders.mart_matches_the_elt_marts"):
        dr.run_dbt(out, os.environ["DBT_BIN"])


def test_the_tracked_pipeline_runs_the_real_elt_and_dbt_and_links_them(tmp_path):
    import elt_pipeline as ep
    import mlflow_link as ml

    summary = ep.run_pipeline(
        tmp_path / "out",
        seed=2,
        rows=200,
        link_db=tmp_path / "links.sqlite",
        dbt=os.environ["DBT_BIN"],
        dag_run_id="dag-1",
    )
    (row,) = ml.LinkTable(tmp_path / "links.sqlite").rows()
    assert row["pipeline_run_id"] == summary["pipeline_run_id"] == "elt-2-200"
    assert row["dag_run_id"] == "dag-1"
    record = json.loads((tmp_path / "out" / "dbt" / "dbt_run.json").read_text())
    assert summary["dbt_invocation_id"] == record["invocation_id"]
    assert summary["elt_run_id"] == record["elt_run_id"]
    assert row["artifact_digests"]["dbt_run"] == ml.sha256_file(
        tmp_path / "out" / "dbt" / "dbt_run.json"
    )
