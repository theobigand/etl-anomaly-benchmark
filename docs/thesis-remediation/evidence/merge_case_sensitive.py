# ruff: noqa: E501
"""Adopt the verdicts measured on a case-sensitive volume for the units that were run there.

    python docs/thesis-remediation/evidence/merge_case_sensitive.py

`run_l4_campaign.py` run on a case-sensitive APFS volume (with TMPDIR on it) leaves `mutants/<unit>.meta` there; a copy
is kept next to the repository's own verdicts as `mutants/<unit>.meta.cs`. This script makes that copy the unit's verdict
file (the previous macOS file is kept as `<unit>.meta.mac`) and records the unit in `case-sensitive-units.json`, which
`consolidate_l4_campaign.py` reads. A unit is adopted only when the copy describes the same mutants as the verdict file it
replaces (same keys). It decides nothing about equivalence and creates no owner approval.
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent / "l4-campaign-2026-11-13" / "case-sensitive-units.json"


def main() -> None:
    adopted = json.loads(OUT.read_text()) if OUT.exists() else {}
    for copy in sorted((ROOT / "mutants").rglob("*.meta.cs")):
        target = copy.with_suffix("")
        unit = target.relative_to(ROOT / "mutants").as_posix().removesuffix(".meta")
        new = json.loads(copy.read_text())["exit_code_by_key"]
        if target.exists():
            old = json.loads(target.read_text())["exit_code_by_key"]
            if set(old) != set(new):
                print(f"skipped {unit}: the mutant keys differ from the recorded verdicts")
                continue
            backup = target.with_suffix(".meta.mac")
            if not backup.exists():
                shutil.copy(target, backup)
        shutil.copy(copy, target)
        counts: dict[str, int] = {}
        names = {1: "killed", 0: "survived", -24: "timeout", 255: "incomplete", 33: "not_executed"}
        for code in new.values():
            name = names.get(code, "not_run" if code is None else f"exit_{code}")
            counts[name] = counts.get(name, 0) + 1
        adopted[unit] = {"counts": counts, "total": len(new)}
        print(f"adopted {unit}: {counts}")
    OUT.write_text(json.dumps(adopted, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
