"""Summary of the alert-budget runs: JSON with exact denominators and a Markdown table."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import alert_budget as ab  # noqa: E402


def load(folder: Path) -> tuple[list[dict], list[str]]:
    runs, failed = [], []
    for path in sorted(folder.glob("*.json")):
        run = json.loads(path.read_text())
        (failed if "failed" in run else runs).append(run["problem"])
        if "failed" not in run:
            runs[-1] = run
    return [r for r in runs if isinstance(r, dict)], [p for p in failed if isinstance(p, str)]


def markdown(table: dict, accounting: dict, failed: list[str]) -> str:
    lines = [
        f"Problems evaluated: {accounting['problems']}; "
        f"problems that failed to load: {len(failed)}; "
        f"failed seed runs: {accounting['failed_runs']}; skipped (problem, detector) pairs: "
        f"{accounting['skipped_detectors']}.",
        "",
        "| Detector | Budget | Problems | Seed runs | Median alert rate | Alert/budget | "
        "Precision | Recall | F1 | FPR |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for method, cells in table.items():
        for budget, c in cells.items():
            lines.append(
                f"| {method} | {float(budget):.3f} | {c['problems']} | {c['seed_runs']} | "
                f"{c['median_test_alert_rate']:.4f} | {c['median_realized_over_nominal']:.2f} | "
                f"{c['median_precision']:.3f} | {c['median_recall']:.3f} | {c['median_f1']:.3f} | "
                f"{c['median_fpr']:.4f} |"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args(argv)
    runs, failed = load(args.folder)
    table = ab.summarize(runs)
    accounting = ab.accounting(runs)
    args.json.write_text(
        json.dumps(
            {"budgets": list(ab.BUDGETS), "accounting": accounting, "failed_problems": failed,
             "rules": ab.rule_reference(runs),
             "table": table}, indent=1, sort_keys=True) + "\n"
    )  # fmt: skip
    args.markdown.write_text(markdown(table, accounting, failed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
