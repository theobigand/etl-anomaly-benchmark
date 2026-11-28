"""Synthetic ELT through DuckDB over Parquet, with provenance (#143, ADR-0004).

Engineering workload on seeded synthetic data only: it reads no benchmark view, fits no detector and
touches no scientific result. Three stages, each written as Parquet under one output directory:

- ``raw``: the synthetic orders (nested struct and list columns, a UTC timestamp, a null column);
- ``staging``: the same rows through DuckDB, ordered by key, nesting kept (nothing is flattened);
- ``marts``: an aggregation per customer tier computed by SQL.

The manifest records the engine versions, the SQL hash, the hash and row count of every output and
the logical schema check. Output directories inside the archived evidence paths are refused before
anything is written. DuckDB is an optional dependency (``elt`` group, ADR-0001) and runs with one
thread so the output bytes are reproducible. It sits outside ``src/`` and the top-level
``experiments/`` scripts, so the scientific fingerprint is unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ARCHIVED = ("verification/evidence", "experiments/results", "docs/thesis-remediation/evidence")
TIERS = ("basic", "plus", "premium")
SKUS = ("a", "b", "c", "d")
SQL = """
select customer.tier as tier,
       count(*) as orders,
       sum(list_aggregate(list_transform(items, lambda i: i.qty), 'sum'))::bigint as units,
       sum(amount) as amount
from staging
group by customer.tier
order by customer.tier
"""
KNOWN_DIFFERENCES = [
    "list element field name (item becomes element)",
    "field nullability (columns without nulls become required)",
]


class ArchivedPathError(ValueError):
    """The output directory lies inside an archived evidence path."""


class ELTError(RuntimeError):
    """A stage failed or an optional dependency is missing."""


def check_output_dir(out: Path) -> Path:
    resolved = out.resolve()
    for archived in ARCHIVED:
        base = (ROOT / archived).resolve()
        if resolved == base or base in resolved.parents:
            raise ArchivedPathError(f"output inside archived evidence: {archived}")
    return out


def synthetic_orders(seed: int, rows: int) -> Any:
    """Seeded orders with nested struct and list columns, a UTC timestamp and a null column."""
    import pyarrow as pa

    rng = random.Random(seed)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    data = {
        "order_id": list(range(rows)),
        "customer": [
            {"id": rng.randrange(1000), "tier": rng.choice([*TIERS, None])} for _ in range(rows)
        ],
        "items": [
            [
                {"sku": rng.choice(SKUS), "qty": rng.randrange(1, 6)}
                for _ in range(rng.randrange(0, 4))
            ]
            for _ in range(rows)
        ],
        "ts": [start + timedelta(minutes=rng.randrange(100000)) for _ in range(rows)],
        "amount": [
            round(rng.uniform(1, 500), 2) if rng.random() > 0.1 else None for _ in range(rows)
        ],
        "note": [None] * rows,
    }
    schema = pa.schema(
        [
            ("order_id", pa.int64()),
            ("customer", pa.struct([("id", pa.int64()), ("tier", pa.string())])),
            ("items", pa.list_(pa.struct([("sku", pa.string()), ("qty", pa.int32())]))),
            ("ts", pa.timestamp("us", tz="UTC")),
            ("amount", pa.float64()),
            ("note", pa.null()),
        ]
    )
    return pa.table(data, schema=schema)


def _describe(arrow_type: Any) -> str:
    import pyarrow as pa

    if pa.types.is_struct(arrow_type):
        inner = ",".join(f"{f.name}:{_describe(f.type)}" for f in arrow_type)
        return f"struct<{inner}>"
    if pa.types.is_list(arrow_type):
        return f"list<{_describe(arrow_type.value_type)}>"
    return str(arrow_type)


def logical_schema(schema: Any) -> list[list[str]]:
    """Field names and logical types, without list element names or nullability."""
    return [[f.name, _describe(f.type)] for f in schema]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_id(manifest: dict[str, Any]) -> str:
    """Identifier derived from the engine, seed, rows, SQL and output hashes."""
    key = json.dumps(
        [manifest["engine"], manifest["seed"], manifest["rows"], manifest["sql_sha256"]]
        + [o["sha256"] for o in manifest["outputs"]]
    )
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def run_elt(out: Path, seed: int, rows: int) -> dict[str, Any]:
    if rows <= 0:
        raise ValueError("rows must be positive")
    out = check_output_dir(Path(out))
    try:
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as error:
        raise ELTError(
            "duckdb is not installed; install the optional group: pip install --group elt "
            "(see [dependency-groups] in pyproject.toml)"
        ) from error
    work = out.with_name(out.name + ".partial")
    shutil.rmtree(work, ignore_errors=True)
    try:
        for stage in ("raw", "staging", "marts"):
            (work / stage).mkdir(parents=True)
        table = synthetic_orders(seed, rows)
        pq.write_table(table, work / "raw/orders.parquet")
        connection = duckdb.connect(config={"threads": 1})
        connection.execute(
            f"create view raw as select * from read_parquet('{work / 'raw/orders.parquet'}')"
        )
        connection.execute(
            "copy (select * from raw order by order_id) "
            f"to '{work / 'staging/orders.parquet'}' (format parquet)"
        )
        connection.execute(
            "create view staging as select * from "
            f"read_parquet('{work / 'staging/orders.parquet'}')"
        )
        try:
            connection.execute(
                f"copy ({SQL}) to '{work / 'marts/orders_by_tier.parquet'}' (format parquet)"
            )
        except duckdb.Error as error:
            raise ELTError(f"transformation failed: {error}") from error
        connection.close()
        outputs = []
        for stage, name in (("raw", "orders"), ("staging", "orders"), ("marts", "orders_by_tier")):
            path = work / stage / f"{name}.parquet"
            written = pq.read_table(path)
            outputs.append(
                {
                    "stage": stage,
                    "path": f"{stage}/{name}.parquet",
                    "sha256": _sha256(path),
                    "rows": written.num_rows,
                    "logical_schema": logical_schema(written.schema),
                }
            )
        preserved = logical_schema(table.schema) == outputs[1]["logical_schema"]
        manifest: dict[str, Any] = {
            "engine": {"duckdb": duckdb.__version__, "pyarrow": pa.__version__},
            "seed": seed,
            "rows": rows,
            "sql_sha256": hashlib.sha256(SQL.encode()).hexdigest(),
            "outputs": outputs,
            "schema_preserved": preserved,
            "known_schema_differences": KNOWN_DIFFERENCES,
        }
        manifest["run_id"] = run_id(manifest)
        (work / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
        shutil.rmtree(out, ignore_errors=True)
        work.rename(out)
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--rows", type=int, default=1000)
    args = parser.parse_args(argv)
    print(json.dumps(run_elt(args.out, args.seed, args.rows), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
