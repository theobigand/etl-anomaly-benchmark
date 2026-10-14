"""Copy the latest experiment outputs into ``evidence/`` and refresh the manifest.

Experiments write timestamped files to ``experiments/results``. After a replay,
this script keeps the newest run of each kind under its fixed name and
recomputes the checksums listed in ``evidence/manifest.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAMP = re.compile(r"_\d{8}_\d{6}")

# (pattern of the timestamped file, name kept in evidence/)
SINGLE_RUNS = [
    ("run_synthetic_*.json", "run_synthetic.json"),
    ("synthetic_metrics_*.csv", "synthetic_metrics.csv"),
    ("synthetic_recall_*.csv", "synthetic_recall.csv"),
    ("synthetic_precision_*.csv", "synthetic_precision.csv"),
    ("synthetic_[0-9]*.md", "synthetic.md"),
    ("run_severity_*.json", "run_severity.json"),
    ("severity_*.csv", "severity.csv"),
    ("run_curves_*.json", "run_curves.json"),
    ("contamination_sweep_*.csv", "contamination_sweep.csv"),
]


def _stable(name: str) -> str:
    return STAMP.sub("", name)


def _newest(results: Path, pattern: str) -> Path:
    candidates = sorted(results.glob(pattern))
    if not candidates:
        raise FileNotFoundError(f"no file matches {pattern} in {results}")
    return candidates[-1]


def _copy_all(pairs: list[tuple[Path, Path]]) -> None:
    for source, _ in pairs:
        if not source.is_file():
            raise FileNotFoundError(source)
    for source, target in pairs:
        shutil.copyfile(source, target)


def archive_real_runs(results: Path, evidence: Path) -> None:
    """Keep the newest baseline and fixed-calibration run of each real dataset."""
    newest: dict[tuple[str, str], Path] = {}
    for path in sorted(results.glob("run_benchmark_*.json")):
        record = json.loads(path.read_text())
        key = (record["dataset"]["identity"], record["settings"]["calibration"])
        newest[key] = path
    pairs = []
    for (dataset, calibration), record_path in newest.items():
        prefix = "fixed_" if calibration == "fixed" else ""
        record = json.loads(record_path.read_text())
        for name in record["outputs"]:
            pairs.append((results / name, evidence / f"{prefix}{_stable(name)}"))
        pairs.append((record_path, evidence / f"run_{prefix}benchmark_{dataset}.json"))
    _copy_all(pairs)


def archive_single_runs(results: Path, evidence: Path, runs=SINGLE_RUNS) -> None:
    _copy_all([(_newest(results, pattern), evidence / name) for pattern, name in runs])


def refresh_manifest(manifest: Path, root: Path, *, revision: str, dirty: bool) -> None:
    """Recompute every listed checksum; a missing artifact is an error."""
    data = json.loads(manifest.read_text())
    data["artifacts"] = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in data["artifacts"]
    }
    data["source_revision"] = revision
    data["worktree_dirty"] = dirty
    manifest.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "experiments" / "results")
    parser.add_argument("--evidence", type=Path, default=ROOT / "verification" / "evidence")
    parser.add_argument("--manifest-only", action="store_true")
    args = parser.parse_args()
    if not args.manifest_only:
        archive_real_runs(args.results, args.evidence)
        archive_single_runs(args.results, args.evidence)
    refresh_manifest(
        args.evidence / "manifest.json",
        ROOT,
        revision=_git("rev-parse", "HEAD"),
        dirty=bool(_git("status", "--porcelain")),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
