"""Fail-closed interpretation of a mutation campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

OUTCOMES = (
    "killed",
    "survived",
    "no_tests",
    "skipped",
    "suspicious",
    "timeout",
    "check_was_interrupted_by_user",
    "segfault",
)


def classify(stats: dict) -> tuple[str, float]:
    """Count every non-killed mutant against the 95% pilot threshold."""
    if "total" not in stats or any(key not in stats for key in OUTCOMES):
        raise ValueError("missing mutation outcomes")
    total = stats["total"]
    if total <= 0 or sum(stats[key] for key in OUTCOMES) != total:
        raise ValueError("incomplete or inconsistent mutation outcomes")
    score = 100.0 * stats["killed"] / total
    return ("PASS" if score >= 95.0 else "FAIL", score)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stats", type=Path)
    args = parser.parse_args()
    status, score = classify(json.loads(args.stats.read_text()))
    print(f"mutation gate: {status} ({score:.2f}% killed)")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
