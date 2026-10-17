"""Rerun an archived experiment and say what kind of reproduction was achieved.

``--dataset`` selects cardio (default), water_quality, credit_card or the synthetic
experiment. A dataset that is not on this machine, or differs from the one the
archived run used, makes every requested level ``NOT_RUN``: nothing is then claimed
reproduced. Rough budgets on a laptop: cardio about 6 s per run, synthetic (12,000
rows, 5 seeds) several minutes, water_quality and credit_card (284k rows) more.

Levels, from the cheapest:

* ``archive``: a fresh run against the archived result in ``evidence/``;
* ``same_environment``: two fresh runs, same source, interpreter and seeds;
* ``locked_environment``: a run in a new environment rebuilt from the recorded
  lock (``environment/``), needing network access to the package indexes;
* ``version_sensitivity``: the same run after changing one package version.
  This one measures a difference and is never a pass/fail gate.

The first three levels are mandatory: when one is requested, anything other
than ``PASS`` (``FAIL``, ``NOT_RUN``, a crash) makes the command exit 1 and the
report ``outcome`` ``FAIL`` or ``INCOMPLETE``. The sensitivity level reports
``MEASURED`` or ``NOT_RUN`` and cannot change the outcome in either direction,
but a run that requested no mandatory level certifies nothing and is
``INCOMPLETE``. The report is written on every one of these paths.

Four things are kept apart. *Numerical*: every metric is bit-identical.
*Statistical*: metrics differ but each mean stays within one reference
standard deviation. *Artifact*: the archived split-id file is byte-identical.
*Timing*: ``detect_s`` columns are compared as a relative spread only and never
decide a status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from verification import evidence_schema, lock_environment

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "verification" / "environment"
ARCHIVED = ROOT / "verification" / "evidence"
LEVELS = ("archive", "same_environment", "locked_environment", "version_sensitivity")
MANDATORY = ("archive", "same_environment", "locked_environment")
# What a replay runs, which archived files it is compared with, and where its input lives.
TARGETS: dict[str, dict[str, Any]] = {
    "cardio": {
        "script": "run_benchmark.py",
        "args": ["--dataset", "cardio"],
        "table": "benchmark_cardio_*.csv",
        "splits": "split_ids_cardio_*.json.gz",
        "reference_table": "benchmark_cardio.csv",
        "reference_splits": "split_ids_cardio.json.gz",
        "record": "run_benchmark_cardio.json",
        "data": "data/cardio.csv",
    },
    "water_quality": {
        "script": "run_benchmark.py",
        "args": ["--dataset", "water_quality"],
        "table": "benchmark_water_quality_*.csv",
        "splits": "split_ids_water_quality_*.json.gz",
        "reference_table": "benchmark_water_quality.csv",
        "reference_splits": "split_ids_water_quality.json.gz",
        "record": "run_benchmark_water_quality.json",
        "data": "data/water_quality.csv",
    },
    "credit_card": {
        "script": "run_benchmark.py",
        "args": ["--dataset", "credit_card"],
        "table": "benchmark_credit_card_*.csv",
        "splits": "split_ids_credit_card_*.json.gz",
        "reference_table": "benchmark_credit_card.csv",
        "reference_splits": "split_ids_credit_card.json.gz",
        "record": "run_benchmark_credit_card.json",
        "data": "data/creditcard.csv",
    },
    "synthetic": {
        "script": "run_synthetic_benchmark.py",
        "args": [],
        "table": "synthetic_metrics_*.csv",
        "splits": None,
        "reference_table": "synthetic_metrics.csv",
        "reference_splits": None,
        "record": "run_synthetic.json",
        "data": None,
    },
}
TOLERANCE = {
    "numerical": "every non-timing metric is bit-identical",
    "statistical": "each mean differs by less than one reference standard deviation",
    "artifact": "the split-id archive is byte-identical",
    "timing": "detect_s columns are a relative spread and never decide a status; "
    "they are not deterministic across machines",
}


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


def _archived_record(dataset: str, archived: Path = ARCHIVED) -> dict:
    return json.loads((archived / str(TARGETS[dataset]["record"])).read_text())


def command_for(dataset: str, python: str, results_dir: Path, archived: Path = ARCHIVED) -> list:
    """The command that replays the archived run, with its seeds and size."""
    target = TARGETS[dataset]
    record = _archived_record(dataset, archived)
    command = [python, f"experiments/{target['script']}", *target["args"]]
    command += ["--results-dir", str(results_dir), "--seeds", *map(str, record["seeds"])]
    if dataset == "synthetic":
        command += ["--rows", str(record["settings"]["rows"])]
        command += ["--figure", str(results_dir / "heatmap_replay.png")]
    return command


def check_input(dataset: str, root: Path = ROOT, archived: Path = ARCHIVED) -> str | None:
    """Why the dataset cannot be replayed on this machine, or None when it can."""
    relative = TARGETS[dataset]["data"]
    if relative is None:
        return None
    path = root / relative
    if not path.is_file():
        return f"dataset {relative} is not available on this machine"
    expected = _archived_record(dataset, archived)["dataset"]["sha256"]
    found = hashlib.sha256(path.read_bytes()).hexdigest()
    if found != expected:
        return f"dataset {relative} differs from the archived run ({found[:12]} != {expected[:12]})"
    return None


def run_dataset(python: str, dataset: str, results_dir: Path) -> dict[str, Path | None]:
    """One replay in the given interpreter; returns the table and the split archive."""
    target = TARGETS[dataset]
    results_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    done = subprocess.run(
        command_for(dataset, python, results_dir),
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=7200, check=False,
    )  # fmt: skip
    if done.returncode != 0:
        raise RuntimeError(f"benchmark failed: {done.stderr.strip().splitlines()[-1:]}")
    splits = next(results_dir.glob(target["splits"])) if target["splits"] else None
    return {"table": next(results_dir.glob(target["table"])), "splits": splits}


def _level(candidate: dict[str, Any], reference: dict[str, Any]) -> dict:
    result = compare(candidate["table"], reference["table"])
    if reference["splits"] is None:
        same_splits = True  # this experiment archives no split ids
        result["artifact_identical"] = None
    elif candidate["splits"] is None:
        same_splits = False  # the archive has split ids and the replay wrote none
        result["artifact_identical"] = False
    else:
        same_splits = candidate["splits"].read_bytes() == reference["splits"].read_bytes()
        result["artifact_identical"] = same_splits
    result["status"] = "PASS" if result["kind"] in ("NUMERICAL", "STATISTICAL") else "FAIL"
    if not same_splits:
        result["status"] = "FAIL"
    return result


def lock_strategy() -> dict[str, Any] | None:
    """How this platform rebuilds the recorded environment, or None when it cannot."""
    system, machine = platform.system(), platform.machine()
    conda = LOCK / f"conda-{system.lower()}-{machine}.explicit.txt"
    if conda.is_file():
        strategy, path = "conda-explicit", conda
    elif (system, machine) == ("Linux", "x86_64"):
        strategy, path = "pip-hashes", LOCK / lock_environment.LINUX_LOCK
    else:
        return None
    return {
        "strategy": strategy,
        "file": f"verification/environment/{path.name}",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "path": path,
    }


def build_environment(prefix: Path, extra_pip: list[str] | None = None) -> str:
    """Rebuild the recorded environment in ``prefix``; return its interpreter."""
    strategy = lock_strategy()
    if strategy is None:
        raise RuntimeError(f"no recorded lock for {platform.system()} {platform.machine()}")
    run: dict[str, Any] = {"check": True, "capture_output": True, "text": True, "timeout": 1800}
    python = str(prefix / "bin" / "python")
    if strategy["strategy"] == "conda-explicit":
        subprocess.run(
            ["conda", "create", "-y", "-p", str(prefix), "--file", str(strategy["path"])], **run
        )
        pip = [python, "-m", "pip", "install", "--no-deps", "-q"]
        subprocess.run([*pip, "-r", str(LOCK / "pip-freeze.txt")], **run)
    else:
        wanted = tuple(int(part) for part in lock_environment.LINUX_PYTHON.split("."))
        if tuple(sys.version_info[:2]) != wanted:
            raise RuntimeError(f"the Linux lock is for Python {lock_environment.LINUX_PYTHON}")
        subprocess.run([sys.executable, "-m", "venv", str(prefix)], **run)
        pip = [python, "-m", "pip", "install", "--no-deps", "-q"]
        subprocess.run([*pip, "--require-hashes", "-r", str(strategy["path"])], **run)
    if extra_pip:
        subprocess.run([*pip, *extra_pip], **run)
    return python


def _not_run(reason: str) -> dict:
    return {"status": "NOT_RUN", "reason": reason}


def _failed(reason: str) -> dict:
    return {"status": "FAIL", "reason": reason}


def reproduce(levels: list[str], workdir: Path, sensitivity_pin: str, dataset: str = "cardio"):
    target = TARGETS[dataset]
    reference = {
        "table": ARCHIVED / target["reference_table"],
        "splits": ARCHIVED / target["reference_splits"] if target["reference_splits"] else None,
    }
    report: dict = {}
    unavailable = check_input(dataset)
    if unavailable:
        report = {name: _not_run(unavailable) for name in levels}
        for name, level in report.items():
            level["required"] = name in MANDATORY
        return report
    first = None
    try:
        first = run_dataset(sys.executable, dataset, workdir / "first")
    except (OSError, RuntimeError, subprocess.SubprocessError, StopIteration) as exc:
        for name in levels:
            report[name] = _failed(f"the reference run failed: {exc}")
    if first is not None:
        if "archive" in levels:
            report["archive"] = _level(first, reference)
        if "same_environment" in levels:
            try:
                report["same_environment"] = _level(
                    run_dataset(sys.executable, dataset, workdir / "second"), first
                )
            except (OSError, RuntimeError, subprocess.SubprocessError, StopIteration) as exc:
                report["same_environment"] = _failed(f"the second run failed: {exc}")
        if "locked_environment" in levels:
            try:
                python = build_environment(workdir / "locked")
                report["locked_environment"] = _level(
                    run_dataset(python, dataset, workdir / "locked_run"), first
                )
            except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
                report["locked_environment"] = _not_run(f"environment could not be rebuilt: {exc}")
        if "version_sensitivity" in levels:
            try:
                python = build_environment(workdir / "changed", [sensitivity_pin])
                changed = _level(run_dataset(python, dataset, workdir / "changed_run"), first)
                changed["status"] = "MEASURED"
                changed["changed"] = sensitivity_pin
                report["version_sensitivity"] = changed
            except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
                report["version_sensitivity"] = _not_run(f"changed environment failed: {exc}")
    for name, level in report.items():
        level["required"] = name in MANDATORY
    return report


def judge(report: dict) -> tuple[str, list[str]]:
    """Return the outcome and the reasons it is not a pass."""
    reasons = []
    outcome = "PASS"
    if not any(name in MANDATORY for name in report):
        return "INCOMPLETE", ["no mandatory level was requested"]
    for name in MANDATORY:
        if name not in report or report[name]["status"] == "PASS":
            continue
        level = report[name]
        detail = level.get("reason") or level.get("kind") or ""
        reasons.append(f"{name} is {level['status']}" + (f": {detail}" if detail else ""))
        if level["status"] == "FAIL":
            outcome = "FAIL"
        elif outcome == "PASS":
            outcome = "INCOMPLETE"
    return outcome, reasons


def default_output(dataset: str) -> Path:
    name = "reproducibility.json" if dataset == "cardio" else f"reproducibility_{dataset}.json"
    return ROOT / "experiments" / "results" / name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(TARGETS), default="cardio")
    parser.add_argument("--levels", nargs="+", choices=LEVELS, default=list(LEVELS[:2]))
    parser.add_argument("--sensitivity-pin", default="scikit-learn==1.8.0")
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or default_output(args.dataset)
    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="repro-"))
    report = reproduce(args.levels, workdir, args.sensitivity_pin, args.dataset)
    outcome, reasons = judge(report)
    record = _archived_record(args.dataset)
    strategy = lock_strategy()
    reference_splits = TARGETS[args.dataset]["reference_splits"]
    document = {
        "schema_version": 1,
        "outcome": outcome,
        "reasons": reasons,
        "captured_at": datetime.now(UTC).isoformat(),
        "source": evidence_schema.collect_source(),
        "environment": evidence_schema.collect_environment(),
        "lock": {
            key: value for key, value in (strategy or {"strategy": "none"}).items() if key != "path"
        },
        "dataset": args.dataset,
        "seeds": record["seeds"],
        "archived_run": {
            "file": f"verification/evidence/{TARGETS[args.dataset]['record']}",
            "source_revision": record["source_revision"],
            "dataset_sha256": record["dataset"].get("sha256"),
            "split_ids_sha256": (
                hashlib.sha256((ARCHIVED / reference_splits).read_bytes()).hexdigest()
                if reference_splits
                else None
            ),
        },
        "tolerance": TOLERANCE,
        "levels": report,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    for name, level in report.items():
        print(f"{name}: {level['status']} {level.get('kind', level.get('reason', ''))}")
    print(f"outcome: {outcome}" + "".join(f"\n  - {reason}" for reason in reasons))
    return 0 if outcome == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
