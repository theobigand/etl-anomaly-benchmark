# ruff: noqa: E501
"""Adopt the verdicts measured on a case-sensitive volume for the units that were run there.

    python docs/thesis-remediation/evidence/merge_case_sensitive.py

`run_l4_campaign.py` run on a case-sensitive APFS volume (with TMPDIR on it) leaves `mutants/<unit>.meta` there; a copy
is kept next to the repository's own verdicts as `mutants/<unit>.meta.cs`. This script makes that copy the unit's verdict
file (the previous macOS file is kept as `<unit>.meta.mac`) and records the unit in `case-sensitive-units.json`, which
`consolidate_l4_campaign.py` reads. A unit is adopted only when the copy describes the same mutants as the verdict file it
replaces (same keys). It records, per unit, the counts of the case-insensitive file it replaces and, once, the\nHEAD and the digest of the test tree of the copy on the case-sensitive volume at the last adoption (the runs were made\nat earlier commits of that copy; each unit's own run is not tied to one commit). It decides nothing about equivalence and\ncreates no owner approval.
"""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent / "l4-campaign-2026-11-13" / "case-sensitive-units.json"


def main() -> None:
    adopted = json.loads(OUT.read_text()) if OUT.exists() else {}
    copy = Path(os.environ.get("CASE_SENSITIVE_COPY", "/Volumes/etlcs/repo"))
    if copy.is_dir():

        def tree(base: Path) -> str:
            digest = hashlib.sha256()
            for path in sorted(
                [*(base / "tests").rglob("*.py"), *(base / "research" / "tests").rglob("*.py")]
            ):
                digest.update(path.relative_to(base).as_posix().encode() + path.read_bytes())
            return digest.hexdigest()

        # The copy is made by rsync without .git: its own git metadata is stale. The digest of its test tree is
        # what identifies it; the HEAD of this repository is recorded only when that tree is identical to this one.
        copied, source = tree(copy), tree(ROOT)
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip()
        adopted["_last_copy"] = {
            "head": head if copied == source else None,
            "tests_sha256": copied,
            "tests_match_repository": copied == source,
        }
    for copy_file in sorted((ROOT / "mutants").rglob("*.meta.cs")):
        target = copy_file.with_suffix("")
        unit = target.relative_to(ROOT / "mutants").as_posix().removesuffix(".meta")
        new = json.loads(copy_file.read_text())["exit_code_by_key"]
        if target.exists():
            old = json.loads(target.read_text())["exit_code_by_key"]
            if set(old) != set(new):
                print(f"skipped {unit}: the mutant keys differ from the recorded verdicts")
                continue
            backup = target.with_suffix(".meta.mac")
            if not backup.exists():
                shutil.copy(target, backup)
        shutil.copy(copy_file, target)
        counts: dict[str, int] = {}
        names = {1: "killed", 0: "survived", -24: "timeout", 255: "incomplete", 33: "not_executed"}
        for code in new.values():
            name = names.get(code, "not_run" if code is None else f"exit_{code}")
            counts[name] = counts.get(name, 0) + 1
        mac = target.with_suffix(".meta.mac")
        previous: dict[str, int] = {}
        if mac.exists():
            for code in json.loads(mac.read_text())["exit_code_by_key"].values():
                name = names.get(code, "not_run" if code is None else f"exit_{code}")
                previous[name] = previous.get(name, 0) + 1
        adopted[unit] = {
            "counts": counts,
            "total": len(new),
            "case_insensitive_counts_before": previous,
        }
        print(f"adopted {unit}: {counts}")
    OUT.write_text(json.dumps(adopted, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
