# ruff: noqa: E501
"""Consolidate the native mutmut verdicts of every classified unit into one measurement record and one report.

    python docs/thesis-remediation/evidence/consolidate_l4_campaign.py

Reads mutants/<path>.meta (written by run_l4_campaign.py), the risk policy, and the owner equivalence file. It records
raw counts, the exact integer comparison against the unit's threshold, and the adjusted score only for equivalence
records that validate against the current source and catalog digests. It is a local development measurement, not the
controller campaign, and it certifies nothing. It reads results and writes the two files below; it creates no owner
decision.
"""

import hashlib
import json
import platform
import subprocess
import sys
from datetime import date
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from verification import mutation_policy  # noqa: E402

OUT = Path(__file__).parent / "l4-campaign-2026-11-13"
STATUS = {
    1: "killed",
    0: "survived",
    -24: "timeout",
    255: "incomplete",
    33: "not_executed",
    None: "not_run",
}
OUTCOME = {
    1: "killed",
    0: "survived",
    -24: "timeout",
    255: "error",
    33: "no tests",
    None: "not checked",
}


def tally(path: str) -> tuple[dict[str, int], list[str], dict[str, int] | None]:
    meta = ROOT / "mutants" / f"{path}.meta"
    if not meta.exists():
        return {}, [], None
    codes = json.loads(meta.read_text())["exit_code_by_key"]
    counts: dict[str, int] = {}
    for code in codes.values():
        name = STATUS.get(code, f"exit_{code}")
        counts[name] = counts.get(name, 0) + 1
    return counts, sorted(codes), codes


def main() -> None:
    policy = json.loads((ROOT / "verification/mutation_risk_policy.json").read_text())
    thresholds = policy["thresholds"]
    equivalence = json.loads((ROOT / "verification/mutation_equivalence.json").read_text())
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    measured = {path: tally(path) for path in policy["units"]}
    catalog = {path: keys for path, (_c, keys, _codes) in measured.items() if keys}
    records = [
        {"id": key, "path": path, "outcome": OUTCOME.get(code, "error")}
        for path, (_c, _k, codes) in measured.items()
        if codes
        for key, code in codes.items()
    ]
    sources = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in policy["units"]
    }
    environment = {
        name: version(name)
        for name in sorted({n for r in equivalence["records"] for n in r["environment"]})
    }
    try:
        waived = mutation_policy.accepted_equivalents(
            equivalence,
            policy["units"],
            sources,
            catalog,
            records,
            policy["governance"],
            environment,
        )
        validation = "valid for the environment of this measurement"
    except ValueError as error:
        waived, validation = {}, f"refused by mutation_policy.accepted_equivalents: {error}"
    modules = {}
    for path, unit in sorted(policy["units"].items()):
        counts, keys, _codes = measured[path]
        total = len(keys)
        killed = counts.get("killed", 0)
        threshold = thresholds[unit["level"]]
        digest = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        catalog_sha = mutation_policy.catalog_digest(keys) if keys else None
        accepted = sorted(waived.get(path, ()))
        unresolved = {k: v for k, v in counts.items() if k not in ("killed", "survived")}
        adjusted = total - len(accepted)
        if not total:
            status = "NO_MUTANTS" if "no_mutants" in unit else "INCOMPLETE"
        elif unresolved:
            status = "INCOMPLETE"
        else:
            status = (
                "PASS_RAW"
                if killed * 100 >= threshold * total
                else (
                    "PASS_ADJUSTED" if adjusted and killed * 100 >= threshold * adjusted else "FAIL"
                )
            )
        modules[path] = {
            "level": unit["level"],
            "threshold": threshold,
            "source_sha256": digest,
            "catalog_sha256": catalog_sha,
            "eligible": total,
            "counts": counts,
            "killed": killed,
            "raw_score": round(100 * killed / total, 2) if total else None,
            "needed_for_threshold": -(-threshold * total // 100) if total else None,
            "accepted_equivalents": accepted,
            "adjusted_eligible": adjusted,
            "adjusted_score": round(100 * killed / adjusted, 2) if adjusted else None,
            "status": status,
        }
    summary = {}
    for item in modules.values():
        summary[item["status"]] = summary.get(item["status"], 0) + 1
    record = {
        "date": date.today().isoformat(),
        "head": head,
        "kind": "local development measurement, not the controller campaign",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            **{n: version(n) for n in ("pandas", "numpy", "mutmut")},
        },
        "policy_sha256": mutation_policy.policy_digest(policy),
        "equivalence_validation": validation,
        "equivalence_environment": environment,
        "summary": summary,
        "mutants": sum(m["eligible"] for m in modules.values()),
        "killed": sum(m["killed"] for m in modules.values()),
        "modules": modules,
    }
    (OUT / "final-measurement.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "head": head,
                "summary": summary,
                "mutants": record["mutants"],
                "killed": record["killed"],
            }
        )
    )


if __name__ == "__main__":
    main()
