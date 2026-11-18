"""Check current per-module mutation thresholds and execution evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

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
    """Interpret a historical global-95% report without recertifying it.

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stats", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--results", type=Path, default=None)
    parser.add_argument("--run", type=Path, default=None, help="managed native controller result")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    from verification import mutation_campaign

    try:
        result, _ = mutation_campaign.load_campaign(
            args.root,
            args.stats,
            args.root / "mutants/results.txt" if args.results is None else args.results,
            args.root / "mutants/controller-result.json" if args.run is None else args.run,
        )
        status = mutation_campaign.status(result)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(f"mutation gate: INVALID ({exc})")
        return 1
    print(f"mutation gate: {status} (native exit {result['native_exit_code']})")
    for path, scope in result["analysis"]["modules"].items():
        if scope["status"] != "NO_MUTANTS_TECHNICAL":
            print(
                f"{path}: {scope['level']} {scope['status']} "
                f"({scope['killed']}/{scope['eligible']}; required {scope['threshold']}%)"
            )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
