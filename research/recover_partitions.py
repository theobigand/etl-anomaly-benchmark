"""Recover the train/validation/test memberships of the labelled-pool experiments (T088, T089).

The historical runs did not archive row identifiers. The split is a deterministic function of the
cleaned table and the seed (``normalise.split``, unchanged since the archives were written), so
the memberships are recomputed, never invented: each record keeps the digests of the source file,
of the cleaned table and of every index set, the partition sizes and prevalences, and the result
of replaying the deterministic Z-score detector on the recomputed partitions against the archived
per-seed metrics. A problem whose replay differs from the archive is flagged, not repaired.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labelled_benchmark as lb  # noqa: E402
import normalise as nm  # noqa: E402

FORMAT = 1
TOLERANCE = 1e-9


def _digest(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def partitions(x: np.ndarray, y: np.ndarray, seeds: tuple[int, ...]) -> dict[str, Any]:
    """Digests, sizes and prevalences of the split of every seed."""
    out: dict[str, Any] = {}
    for seed in seeds:
        part = nm.split(x, y, seed)
        record: dict[str, Any] = {}
        for name in ("train", "val", "test"):
            rows = np.asarray(part[f"idx_{name}"], dtype=np.int64)
            record[name] = {
                "rows": int(len(rows)),
                "anomalies": int(y[rows].sum()),
                "prevalence": float(y[rows].mean()),
                "sha256": _digest(rows),
            }
        out[str(seed)] = record
    return out


def _same(archived: dict[str, float], replayed: dict[str, float]) -> bool:
    return set(archived) == set(replayed) and all(
        abs(archived[key] - replayed[key]) <= TOLERANCE for key in archived
    )


def replay_matches(x: np.ndarray, y: np.ndarray, archive: dict[str, Any]) -> list[bool]:
    """Whether the deterministic Z-score detector reproduces the archived metrics seed by seed."""
    seeds = tuple(archive["seeds"])
    rows = archive["metrics"].get("zscore", [])
    if len(rows) != len(seeds):
        return [False] * len(seeds)
    replay = lb.run_problem(x, y, seeds=seeds, methods=["zscore"])["metrics"]["zscore"]
    return [_same(old, new) for old, new in zip(rows, replay, strict=True)]


def recover(job: dict[str, Any], archive: dict[str, Any]) -> dict[str, Any]:
    if job["source"] == "adbench":
        x, y, report = lb.load_adbench(job["name"], Path(job["path"]))
    else:
        x, y, report = lb.load_uci(job["meta"], Path(job["path"]))
    seeds = tuple(archive["seeds"])
    matches = replay_matches(x, y, archive)
    return {
        "format": FORMAT,
        "problem": job["problem"],
        "source": job["source"],
        "recovery": "recomputed from the deterministic split; not archived at run time",
        "input_sha256": _file_digest(Path(job["path"])),
        "cleaned_rows": int(len(y)),
        "cleaned_sha256": _digest(np.ascontiguousarray(x)),
        "labels_sha256": _digest(np.asarray(y, dtype=np.int64)),
        "seeds": list(seeds),
        "partitions": partitions(x, y, seeds),
        "archived_rows": archive.get("rows"),
        "archive_replay": {"detector": "zscore", "seeds_matching": matches, "all": all(matches)},
        "report_rows_out": report.get("rows_out"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = HERE.parent
    parser.add_argument(
        "--registry", type=Path, default=root / "verification/evidence/dataset_registry"
    )
    parser.add_argument("--adbench", type=Path, default=root / "data" / "adbench")
    parser.add_argument("--pool", type=Path, default=root / "data" / "pool")
    parser.add_argument(
        "--archive", type=Path, default=root / "verification/evidence/labelled_pool/runs"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    mismatched = 0
    for job in lb.jobs(args.registry, args.adbench, args.pool):
        stem = job["problem"].replace(":", "_")
        archive_path = args.archive / f"{stem}.json"
        if not archive_path.is_file():
            print(job["problem"], "no archived run")
            mismatched += 1
            continue
        archive = json.loads(archive_path.read_text())
        if "failed" in archive:
            print(job["problem"], "archived run failed; not recoverable")
            mismatched += 1
            continue
        record = recover(job, archive)
        (args.output / f"{stem}.json").write_text(
            json.dumps(record, indent=1, sort_keys=True) + "\n"
        )
        flag = "ok" if record["archive_replay"]["all"] else "REPLAY DIFFERS"
        mismatched += not record["archive_replay"]["all"]
        print(job["problem"], flag, flush=True)
    print(f"{mismatched} problems not confirmed")
    return 0 if mismatched == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
