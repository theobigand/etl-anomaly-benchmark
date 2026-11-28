# Local ELT through DuckDB over Parquet (#143)

`research/elt_duckdb.py` is a synthetic end-to-end ELT run: seeded synthetic orders are written as Parquet, transformed
by DuckDB and aggregated by SQL into a mart, and a manifest records the provenance. It reads no benchmark view, fits
no detector and changes no ledger count or scientific result. DuckDB is pinned exactly (`duckdb==2.0.1`, ADR-0004) in
the optional `elt` dependency group, outside `[project]`, so the scientific fingerprint and the governed environment are
unchanged.

```
uv venv ~/.cache/etl-elt-venv && uv pip install --python ~/.cache/etl-elt-venv/bin/python duckdb==2.0.1 pyarrow pytest
~/.cache/etl-elt-venv/bin/python research/elt_duckdb.py --out /tmp/elt-demo --seed 0 --rows 1000
```

## Stages and provenance

| Stage | Content | Written to |
|---|---|---|
| raw | synthetic orders: nested struct and list columns, a UTC timestamp, a null column | `<out>/raw/orders.parquet` |
| staging | the same rows through DuckDB, ordered by key, nesting kept | `<out>/staging/orders.parquet` |
| marts | orders, units and amount per customer tier, by SQL | `<out>/marts/orders_by_tier.parquet` |

`<out>/manifest.json` holds the DuckDB and PyArrow versions, the seed, the SQL hash, the SHA-256 and row count of every
output, the logical schema of each output, the schema-preservation result and a run identifier derived from them. The
output directory is written next to its final name and renamed, so a failed run leaves nothing. Directories inside
`verification/evidence`, `experiments/results` or `docs/thesis-remediation/evidence` are refused before anything is
written. One DuckDB thread keeps the output bytes reproducible: two runs with one seed give identical files.

## Verified Arrow and Parquet behaviour (DuckDB 2.0.1, PyArrow 26)

- Struct, list, timestamp with time zone, integer width and the null type survive Parquet and DuckDB unchanged.
- Two differences are expected and recorded, not corrected: the list element field is named `item` in memory and
  `element` once it has been through Parquet, and DuckDB marks columns that contain no nulls as required.
  `logical_schema` ignores exactly these two and detects any change of type, width, time zone or field name.
- Nothing is flattened: nested columns stay nested in staging and are queried with struct and list functions.
- DuckDB 2.0 rejects the old `x -> expr` lambda; the SQL uses `lambda x: expr`.

## Not done here

Linking the manifest to MLflow or the observability events (#146, #164), the dbt models (#146) and the Airflow task
(#148) are separate issues. DuckDB is not installed in the governed scientific environment; the tests of this module
are not collected there. `make verify-platform` runs them in an environment with the `elt` group, and CI runs it in the `platform` job.
