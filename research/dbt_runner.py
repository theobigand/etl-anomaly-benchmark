"""Run the dbt project over the Parquet stages of the DuckDB ELT, with provenance (#146, ADR-0005).

Engineering workload on seeded synthetic data only: it reads no benchmark view, fits no detector
and touches no scientific result. ``run_dbt`` runs ``dbt build`` and ``dbt docs generate`` of
``platform/dbt_orders`` against the output directory of ``elt_duckdb.run_elt``, in a separate
interpreter (dbt keeps its own Jinja and adapter stack, ADR-0001 and ADR-0005: the executable comes
from ``DBT_BIN`` or the ``--dbt`` option, never from this environment). The project reads the ELT
raw Parquet as a source and its singular test compares the dbt mart with the ELT mart.

The record ``dbt_run.json`` holds the invocation id of dbt, the dbt and adapter versions, the status
of every node, the hash of each artifact and the run id of the ELT it was built on. Artifacts are
written under ``<elt output>/dbt`` and the output directory must not lie inside the archived
evidence paths. The module sits outside ``src/`` and the top-level ``experiments/`` scripts, so the
scientific fingerprint is unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import elt_duckdb as elt

PROJECT = elt.ROOT / "platform" / "dbt_orders"
ARTIFACTS = ("manifest.json", "run_results.json", "catalog.json")
TIMEOUT = 600


class DbtError(RuntimeError):
    """dbt could not run or reported a failed node."""


class DbtUnavailable(DbtError):
    """No dbt executable was given or it cannot be started."""


def dbt_command(dbt: str | None) -> str:
    command = dbt or os.environ.get("DBT_BIN")
    if not command:
        raise DbtUnavailable("no dbt executable: set DBT_BIN or pass --dbt")
    return command


def _invoke(command: str, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            [command, *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )
    except (FileNotFoundError, PermissionError) as error:
        raise DbtUnavailable(f"cannot start dbt: {error}") from error
    except subprocess.TimeoutExpired as error:
        raise DbtError(f"dbt timed out after {TIMEOUT} s: {args[0]}") from error


def read_results(target: Path) -> dict[str, Any]:
    """Invocation id and node statuses from ``run_results.json``."""
    path = target / "run_results.json"
    if not path.is_file():
        raise DbtError("dbt wrote no run_results.json")
    document = json.loads(path.read_text())
    nodes = {item["unique_id"]: item["status"] for item in document["results"]}
    return {"invocation_id": document["metadata"]["invocation_id"], "nodes": nodes}


def lineage(target: Path) -> dict[str, list[str]]:
    """Parents of every model and test of the manifest: the lineage the generated docs draw."""
    document = json.loads((target / "manifest.json").read_text())
    return {name: sorted(parents) for name, parents in sorted(document["parent_map"].items())}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_dbt(elt_out: Path, dbt: str | None = None) -> dict[str, Any]:
    elt_out = elt.check_output_dir(Path(elt_out)).resolve()
    elt_manifest = elt_out / "manifest.json"
    if not elt_manifest.is_file():
        raise DbtError(f"{elt_out} holds no ELT manifest; run elt_duckdb first")
    command = dbt_command(dbt)
    target = elt_out / "dbt" / "target"
    target.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "ELT_RAW": str(elt_out / "raw" / "orders.parquet"),
        "ELT_MARTS": str(elt_out / "marts" / "orders_by_tier.parquet"),
        "DBT_DUCKDB_PATH": str(elt_out / "dbt" / "orders.duckdb"),
    }
    flags = [
        "--project-dir",
        str(PROJECT),
        "--profiles-dir",
        str(PROJECT),
        "--target-path",
        str(target),
        "--log-path",
        str(elt_out / "dbt" / "logs"),
    ]
    build = _invoke(command, ["build", *flags], env)
    written = (target / "run_results.json").is_file()
    results = read_results(target) if written else {"nodes": {}}
    failed = sorted(n for n, s in results["nodes"].items() if s not in ("pass", "success"))
    if build.returncode != 0 or failed:
        raise DbtError(
            f"dbt build failed (exit {build.returncode}): {', '.join(failed) or 'no node result'}"
        )
    results = read_results(target)  # a clean exit without results is an error too
    docs = _invoke(command, ["docs", "generate", *flags], env)
    if docs.returncode != 0:
        raise DbtError(f"dbt docs generate failed (exit {docs.returncode})")
    version = _invoke(command, ["--version"], env).stdout
    record = {
        "elt_run_id": json.loads(elt_manifest.read_text())["run_id"],
        "invocation_id": results["invocation_id"],
        "dbt_version": version,
        "nodes": results["nodes"],
        "lineage": lineage(target),
        "artifacts": {name: _sha256(target / name) for name in ARTIFACTS},
    }
    (elt_out / "dbt" / "dbt_run.json").write_text(
        json.dumps(record, indent=1, sort_keys=True) + "\n"
    )
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elt-out", required=True)
    parser.add_argument("--dbt")
    args = parser.parse_args(argv)
    print(json.dumps(run_dbt(args.elt_out, args.dbt), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
