"""Rerun the cardio benchmark and say what kind of reproduction was achieved.

Levels, from the cheapest:

* ``archive``: a fresh run against the archived result in ``evidence/``;
* ``same_environment``: two fresh runs, same source, interpreter and seeds;
* ``locked_environment``: a run in a new environment rebuilt from the recorded
  lock (``environment/``), needing network access to the package indexes;
* ``version_sensitivity``: the same run after changing one package version.
  This one measures a difference and is never a pass/fail gate.

Four things are kept apart. *Numerical*: every metric is bit-identical.
*Statistical*: metrics differ but each mean stays within one reference
standard deviation. *Artifact*: the archived split-id file is byte-identical.
*Timing*: ``detect_s`` columns are compared as a relative spread only and never
decide a status.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from verification import evidence_schema

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "verification" / "environment"
ARCHIVED = ROOT / "verification" / "evidence"
LEVELS = ("archive", "same_environment", "locked_environment", "version_sensitivity")


def _metrics(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = pd.read_csv(path, index_col=0)
    timing = [column for column in frame if str(column).startswith("detect_s")]
    return frame.drop(columns=timing), frame[timing]


def compare(candidate: Path, reference: Path) -> dict:
    """Numerical and statistical agreement of two benchmark tables; timing apart."""
    new, new_time = _metrics(candidate)
    old, old_time = _metrics(reference)
    if list(new.index) != list(old.index) or list(new.columns) != list(old.columns):
        return {"kind": "DIFFERENT_SHAPE", "max_abs_diff": None, "timing_max_rel_diff": None}
    diff = (new - old).abs()
    means = [column for column in new if str(column).endswith("_mean")]
    spread = old[[str(column).replace("_mean", "_std") for column in means]]
    spread.columns = means
    inside = bool((diff[means] <= spread.fillna(0.0)).all().all())
    timing = (
        ((new_time - old_time).abs() / old_time.abs()).max().max() if old_time.shape[1] else None
    )
    maximum = float(diff.max().max())
    kind = "NUMERICAL" if maximum == 0.0 else "STATISTICAL" if inside else "DIFFERENT"
    return {
        "kind": kind,
        "max_abs_diff": maximum,
        "timing_max_rel_diff": None if timing is None else float(timing),
    }


def run_cardio(python: str, results_dir: Path) -> dict[str, Path]:
    """One cardio benchmark in the given interpreter; returns the table and the split archive."""
    results_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    command = [python, "experiments/run_benchmark.py", "--dataset", "cardio"]
    command += ["--results-dir", str(results_dir)]
    done = subprocess.run(
        command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=1800, check=False
    )
    if done.returncode != 0:
        raise RuntimeError(f"benchmark failed: {done.stderr.strip().splitlines()[-1:]}")
    return {
        "table": next(results_dir.glob("benchmark_cardio_*.csv")),
        "splits": next(results_dir.glob("split_ids_cardio_*.json.gz")),
    }


def _level(candidate: dict[str, Path], reference: dict[str, Path]) -> dict:
    result = compare(candidate["table"], reference["table"])
    same_splits = candidate["splits"].read_bytes() == reference["splits"].read_bytes()
    result["artifact_identical"] = same_splits
    result["status"] = "PASS" if result["kind"] in ("NUMERICAL", "STATISTICAL") else "FAIL"
    if not same_splits:
        result["status"] = "FAIL"
    return result


def build_environment(prefix: Path, extra_pip: list[str] | None = None) -> str:
    """Rebuild the recorded environment in ``prefix``; return its interpreter."""
    conda = next(LOCK.glob("conda-*.explicit.txt"))
    subprocess.run(
        ["conda", "create", "-y", "-p", str(prefix), "--file", str(conda)],
        check=True, capture_output=True, text=True, timeout=1800,
    )  # fmt: skip
    python = str(prefix / "bin" / "python")
    pip = [python, "-m", "pip", "install", "--no-deps", "-q"]
    subprocess.run([*pip, "-r", str(LOCK / "pip-freeze.txt")], check=True,
                   capture_output=True, text=True, timeout=1800)  # fmt: skip
    if extra_pip:
        subprocess.run([*pip, *extra_pip], check=True, capture_output=True, text=True, timeout=1800)
    return python


def _not_run(reason: str) -> dict:
    return {"status": "NOT_RUN", "reason": reason}


def reproduce(levels: list[str], workdir: Path, sensitivity_pin: str) -> dict:
    reference = {
        "table": ARCHIVED / "benchmark_cardio.csv",
        "splits": ARCHIVED / "split_ids_cardio.json.gz",
    }
    report: dict = {}
    first = run_cardio(sys.executable, workdir / "first")
    if "archive" in levels:
        report["archive"] = _level(first, reference)
    if "same_environment" in levels:
        second = run_cardio(sys.executable, workdir / "second")
        report["same_environment"] = _level(second, first)
    if "locked_environment" in levels:
        try:
            python = build_environment(workdir / "locked")
            report["locked_environment"] = _level(run_cardio(python, workdir / "locked_run"), first)
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            report["locked_environment"] = _not_run(f"environment could not be rebuilt: {exc}")
    if "version_sensitivity" in levels:
        try:
            python = build_environment(workdir / "changed", [sensitivity_pin])
            changed = _level(run_cardio(python, workdir / "changed_run"), first)
            changed["status"] = "MEASURED"
            changed["changed"] = sensitivity_pin
            report["version_sensitivity"] = changed
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            report["version_sensitivity"] = _not_run(f"changed environment failed: {exc}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--levels", nargs="+", choices=LEVELS, default=list(LEVELS[:2]))
    parser.add_argument("--sensitivity-pin", default="scikit-learn==1.8.0")
    parser.add_argument("--workdir", type=Path)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "experiments/results/reproducibility.json"
    )
    args = parser.parse_args(argv)
    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="repro-"))
    report = reproduce(args.levels, workdir, args.sensitivity_pin)
    document = {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "source": evidence_schema.collect_source(),
        "environment": evidence_schema.collect_environment(),
        "dataset": "cardio",
        "levels": report,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    failed = False
    for name, level in report.items():
        print(f"{name}: {level['status']} {level.get('kind', level.get('reason', ''))}")
        failed |= level["status"] == "FAIL"
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
