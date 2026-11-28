"""Synthetic ELT through DuckDB over Parquet with provenance (#143)."""

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

# duckdb is imported only inside the tests that need it: a forked mutation worker that
# inherits a loaded duckdb hangs
if importlib.util.find_spec("duckdb") is None and os.environ.get("PLATFORM_REQUIRE") != "1":
    pytest.skip("duckdb is not installed", allow_module_level=True)
pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import elt_duckdb as elt  # noqa: E402


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_the_run_writes_three_stages_and_a_manifest_outside_the_archived_paths(tmp_path):
    manifest = elt.run_elt(tmp_path / "out", seed=1, rows=200)
    for stage in ("raw", "staging", "marts"):
        assert (tmp_path / "out" / stage / f"{stage_name(stage)}.parquet").exists()
    assert json.loads((tmp_path / "out/manifest.json").read_text()) == manifest
    assert [s["stage"] for s in manifest["outputs"]] == ["raw", "staging", "marts"]


def stage_name(stage):
    return {"raw": "orders", "staging": "orders", "marts": "orders_by_tier"}[stage]


def test_the_mart_equals_an_independent_aggregation_of_the_raw_data(tmp_path):
    elt.run_elt(tmp_path, seed=3, rows=300)
    raw = pq.read_table(tmp_path / "raw/orders.parquet").to_pylist()
    expected = {}
    for row in raw:
        tier = row["customer"]["tier"]
        entry = expected.setdefault(tier, [0, 0, 0.0])
        entry[0] += 1
        entry[1] += sum(i["qty"] for i in row["items"])
        entry[2] += row["amount"] or 0.0
    mart = pq.read_table(tmp_path / "marts/orders_by_tier.parquet").to_pylist()
    assert {r["tier"]: [r["orders"], r["units"], r["amount"]] for r in mart} == {
        k: [v[0], v[1], pytest.approx(v[2])] for k, v in expected.items()
    }
    assert [r["tier"] for r in mart] == [*sorted(t for t in expected if t is not None), None]


def test_nested_structures_and_timestamps_survive_with_two_documented_differences(tmp_path):
    manifest = elt.run_elt(tmp_path, seed=2, rows=50)
    source = elt.synthetic_orders(2, 50)
    raw = pq.read_table(tmp_path / "raw/orders.parquet")
    staging = pq.read_table(tmp_path / "staging/orders.parquet")
    assert manifest["schema_preserved"] is True
    assert staging.to_pylist() == sorted(raw.to_pylist(), key=lambda r: r["order_id"])
    assert str(staging.schema.field("items").type).startswith("list<element: struct<")
    assert str(source.schema.field("items").type).startswith("list<item: struct<")
    assert (
        not staging.schema.field("order_id").nullable and source.schema.field("order_id").nullable
    )
    assert staging.schema.field("ts").type == source.schema.field("ts").type
    assert manifest["known_schema_differences"] == [
        "list element field name (item becomes element)",
        "field nullability (columns without nulls become required)",
    ]
    assert staging.num_rows == raw.num_rows


def test_the_logical_schema_ignores_those_differences_and_detects_a_real_change():
    a = pa.schema([("x", pa.list_(pa.field("item", pa.struct([("k", pa.int32())]))))])
    b = pa.schema(
        [
            pa.field(
                "x", pa.list_(pa.field("element", pa.struct([("k", pa.int32())]))), nullable=False
            )
        ]
    )
    c = pa.schema([("x", pa.list_(pa.struct([("k", pa.int64())])))])
    assert elt.logical_schema(a) == elt.logical_schema(b)
    assert elt.logical_schema(a) != elt.logical_schema(c)
    assert elt.logical_schema(
        pa.schema([("t", pa.timestamp("us", tz="UTC"))])
    ) != elt.logical_schema(pa.schema([("t", pa.timestamp("us"))]))


def test_the_manifest_records_versions_hashes_and_row_counts(tmp_path):
    manifest = elt.run_elt(tmp_path, seed=4, rows=120)
    import duckdb

    assert manifest["engine"] == {"duckdb": duckdb.__version__, "pyarrow": pa.__version__}
    assert manifest["seed"] == 4 and manifest["rows"] == 120
    assert manifest["sql_sha256"] == hashlib.sha256(elt.SQL.encode()).hexdigest()
    raw = manifest["outputs"][0]
    assert raw["sha256"] == _sha(tmp_path / "raw/orders.parquet") and raw["rows"] == 120
    assert manifest["outputs"][2]["rows"] == len(
        pq.read_table(tmp_path / "marts/orders_by_tier.parquet")
    )
    assert manifest["run_id"] == elt.run_id(manifest)


def test_two_runs_with_one_seed_give_identical_bytes_and_other_seeds_differ(tmp_path):
    one = elt.run_elt(tmp_path / "a", seed=5, rows=150)
    two = elt.run_elt(tmp_path / "b", seed=5, rows=150)
    assert [o["sha256"] for o in one["outputs"]] == [o["sha256"] for o in two["outputs"]]
    assert one["run_id"] == two["run_id"]
    other = elt.run_elt(tmp_path / "c", seed=6, rows=150)
    assert other["run_id"] != one["run_id"]


@pytest.mark.parametrize(
    "relative",
    ["verification/evidence/x", "experiments/results/y", "docs/thesis-remediation/evidence/z"],
)
def test_archived_evidence_paths_are_refused_before_anything_is_written(relative):
    target = elt.ROOT / relative
    with pytest.raises(elt.ArchivedPathError, match="^output inside archived evidence: "):
        elt.run_elt(target, seed=1, rows=10)
    assert not target.exists()


def test_a_path_that_only_resembles_an_archived_one_is_allowed(tmp_path):
    assert (
        elt.check_output_dir(elt.ROOT / "verification/evidence_not")
        == elt.ROOT / "verification/evidence_not"
    )
    assert elt.check_output_dir(tmp_path) == tmp_path


@pytest.mark.parametrize("rows", [0, -1])
def test_a_non_positive_row_count_is_rejected(tmp_path, rows):
    with pytest.raises(ValueError, match="^rows must be positive$"):
        elt.run_elt(tmp_path, seed=1, rows=rows)


def test_a_failing_transformation_is_classified_and_leaves_no_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(elt, "SQL", "select * from missing_table")
    with pytest.raises(elt.ELTError, match="^transformation failed: "):
        elt.run_elt(tmp_path / "out", seed=1, rows=20)
    assert not (tmp_path / "out").exists()


def test_the_output_is_readable_by_duckdb_itself(tmp_path):
    import duckdb

    elt.run_elt(tmp_path, seed=7, rows=80)
    query = f"select count(*) from read_parquet('{tmp_path}/staging/orders.parquet')"
    assert duckdb.sql(query).fetchall() == [(80,)]


def test_the_command_line_prints_the_manifest_and_returns_zero(tmp_path, capsys):
    assert elt.main(["--out", str(tmp_path / "o"), "--seed", "9", "--rows", "30"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == json.loads((tmp_path / "o/manifest.json").read_text())


def test_without_duckdb_the_module_still_imports_and_run_says_how_to_install(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "duckdb", None)
    with pytest.raises(
        elt.ELTError,
        match=r"^duckdb is not installed; install the optional group: pip install --group elt",
    ):
        elt.run_elt(tmp_path, seed=1, rows=5)


def test_the_synthetic_orders_follow_their_documented_distributions():
    from datetime import UTC, datetime, timedelta

    table = elt.synthetic_orders(1, 4000)
    assert table.schema.equals(
        pa.schema(
            [
                ("order_id", pa.int64()),
                ("customer", pa.struct([("id", pa.int64()), ("tier", pa.string())])),
                ("items", pa.list_(pa.struct([("sku", pa.string()), ("qty", pa.int32())]))),
                ("ts", pa.timestamp("us", tz="UTC")),
                ("amount", pa.float64()),
                ("note", pa.null()),
            ]
        )
    )
    rows = table.to_pylist()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    assert min(r["ts"] for r in rows) >= start
    assert max(r["ts"] for r in rows) < start + timedelta(minutes=100000)
    ids = [r["customer"]["id"] for r in rows]
    assert min(ids) <= 5 and 994 <= max(ids) <= 999
    assert {r["customer"]["tier"] for r in rows} == {*elt.TIERS, None}
    sizes = {len(r["items"]) for r in rows}
    assert sizes == {0, 1, 2, 3}
    items = [i for r in rows for i in r["items"]]
    assert {i["qty"] for i in items} == {1, 2, 3, 4, 5}
    assert {i["sku"] for i in items} == set(elt.SKUS)
    amounts = [r["amount"] for r in rows if r["amount"] is not None]
    assert 1 <= min(amounts) < 5 and 495 < max(amounts) <= 500
    assert all(round(a, 2) == a for a in amounts)
    assert 0.07 < 1 - len(amounts) / len(rows) < 0.13
    assert all(r["note"] is None for r in rows)
    assert table == elt.synthetic_orders(1, 4000) and table != elt.synthetic_orders(2, 4000)


def test_the_manifest_file_is_sorted_indented_json_with_a_newline(tmp_path):
    manifest = elt.run_elt(tmp_path, seed=1, rows=10)
    assert (tmp_path / "manifest.json").read_text() == (
        json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    )
    assert len(manifest["run_id"]) == 16
    assert manifest["outputs"][0]["path"] == "raw/orders.parquet"
    assert manifest["outputs"][2]["path"] == "marts/orders_by_tier.parquet"


def test_one_row_is_enough_and_a_stale_partial_directory_is_replaced(tmp_path):
    stale = tmp_path / "out.partial"
    stale.mkdir()
    (stale / "junk.txt").write_text("x")
    elt.run_elt(tmp_path / "out", seed=1, rows=1)
    assert not stale.exists() and not (tmp_path / "out/junk.txt").exists()
    assert pq.read_table(tmp_path / "out/raw/orders.parquet").num_rows == 1


def test_a_failed_run_leaves_neither_output_nor_partial_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(elt, "SQL", "select * from missing_table")
    with pytest.raises(elt.ELTError):
        elt.run_elt(tmp_path / "out", seed=1, rows=5)
    assert list(tmp_path.iterdir()) == []


def test_an_existing_output_directory_is_replaced_whole(tmp_path):
    (tmp_path / "old.txt").write_text("x")
    elt.run_elt(tmp_path, seed=1, rows=5)
    assert not (tmp_path / "old.txt").exists()


def test_the_install_hint_is_exact(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "duckdb", None)
    with pytest.raises(elt.ELTError) as error:
        elt.run_elt(tmp_path, seed=1, rows=5)
    assert str(error.value) == (
        "duckdb is not installed; install the optional group: pip install --group elt "
        "(see [dependency-groups] in pyproject.toml)"
    )


def test_the_logical_schema_describes_nested_types_exactly():
    schema = pa.schema(
        [
            ("c", pa.struct([("id", pa.int64()), ("tier", pa.string())])),
            ("i", pa.list_(pa.struct([("a", pa.int32())]))),
        ]
    )
    assert elt.logical_schema(schema) == [
        ["c", "struct<id:int64,tier:string>"],
        ["i", "list<struct<a:int32>>"],
    ]


def test_the_command_line_defaults_and_output_format(tmp_path, monkeypatch, capsys):
    seen = {}

    def fake(out, seed, rows):
        seen.update(out=out, seed=seed, rows=rows)
        return {"b": 1, "a": 2}

    monkeypatch.setattr(elt, "run_elt", fake)
    assert elt.main(["--out", str(tmp_path)]) == 0
    assert seen == {"out": tmp_path, "seed": 0, "rows": 1000}
    assert capsys.readouterr().out == json.dumps({"a": 2, "b": 1}, indent=1) + "\n"
    elt.main(["--out", str(tmp_path), "--seed", "3", "--rows", "4"])
    assert (seen["seed"], seen["rows"]) == (3, 4)
