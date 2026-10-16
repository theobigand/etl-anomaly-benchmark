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


THRESHOLD = 95
# A campaign with any of these outcomes did not measure what it claims to
# measure, whatever its score: it is invalid, not merely low.
UNRELIABLE = ("check_was_interrupted_by_user", "segfault", "no_tests", "skipped")


def classify(stats: dict) -> tuple[str, float]:
    """Count every non-killed mutant against the 95% threshold.

    Raises ValueError when the counts are malformed or the campaign is
    unreliable (interrupted, crashed, mutants without tests, skipped mutants).
    """
    if not isinstance(stats, dict):
        raise ValueError("incomplete mutation outcomes: not a mapping")
    if "total" not in stats or any(key not in stats for key in OUTCOMES):
        raise ValueError("missing mutation outcomes")
    for key in ("total", *OUTCOMES):
        value = stats[key]
        if type(value) is not int or value < 0:
            raise ValueError(f"invalid mutation count for {key}: {value!r}")
    total = stats["total"]
    if total <= 0 or sum(stats[key] for key in OUTCOMES) != total:
        raise ValueError("incomplete or inconsistent mutation outcomes")
    for key in UNRELIABLE:
        if stats[key]:
            raise ValueError(f"unreliable campaign: {key}={stats[key]}")
    score = 100.0 * stats["killed"] / total
    # Compare in integers so the boundary involves no floating-point error.
    passed = stats["killed"] * 100 >= THRESHOLD * total
    return ("PASS" if passed else "FAIL", score)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stats", type=Path)
    args = parser.parse_args()
    try:
        status, score = classify(json.loads(args.stats.read_text()))
    except (OSError, ValueError) as exc:
        print(f"mutation gate: INVALID ({exc})")
        return 1
    print(f"mutation gate: {status} ({score:.2f}% killed)")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
