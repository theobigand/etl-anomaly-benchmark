"""Decide whether the collected evidence certifies the current revision.

CERTIFIED needs all four profiles to pass on the same clean revision and
source, with intact artifacts, reference dataset hashes and valid experiment
lineage. Missing or unfinished evidence gives INCOMPLETE; wrong, stale or
inconsistent evidence gives REJECTED. A report produced here is generated on
the machine that runs it: it records where it ran, never that it was
independently attested.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from verification import evidence_schema, lineage

ROOT = Path(__file__).resolve().parents[1]
KINDS = evidence_schema.KINDS
EVIDENCE_DIR = ROOT / "experiments" / "results" / "evidence"
ARCHIVE = ROOT / "verification" / "evidence"


def attestation() -> str:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return f"ci-run:{os.environ.get('GITHUB_RUN_ID', 'unknown')} (not independently attested)"
    return "local-unattested"


def assess(docs, *, current, root, manifest, lineage) -> dict:  # noqa: PLR0912
    """Pure decision over the loaded evidence; see the module docstring."""
    rejected: list[str] = []
    incomplete: list[str] = []
    profiles = {}
    if current.get("worktree_dirty"):
        rejected.append("the worktree is dirty: a release needs a clean source")
    for kind in KINDS:
        doc = docs.get(kind)
        if doc is None:
            profiles[kind] = "MISSING"
            incomplete.append(f"{kind} evidence is missing")
            continue
        problems = evidence_schema.validate(doc, root=root)
        if problems:
            profiles[kind] = "INVALID"
            rejected += [f"{kind}: {problem}" for problem in problems]
            continue
        profiles[kind] = doc["status"]
        if doc["status"] == "FAIL":
            rejected.append(f"{kind} profile failed")
        elif doc["status"] != "PASS":
            incomplete.append(f"{kind} profile is {doc['status']}")
        source = doc["source"]
        if source["revision"] != current["revision"]:
            rejected.append(f"{kind}: revision {source['revision'][:8]} is not the current one")
        if source["scientific_fingerprint"] != current["scientific_fingerprint"]:
            rejected.append(f"{kind}: scientific fingerprint differs from the current source")
        if source["worktree_dirty"]:
            rejected.append(f"{kind}: produced from a dirty worktree")
    revisions = {d["source"]["revision"] for d in docs.values() if d and "source" in d}
    if len(revisions) > 1:
        rejected.append("revision: the profiles were produced on different revisions")
    real = docs.get("real")
    if real and profiles["real"] == "PASS":
        recorded = {item["dataset"]: item.get("sha256") for item in real["result"]["datasets"]}
        for name in real["result"]["required"]:
            if manifest.get(name) is None or recorded.get(name) != manifest[name]:
                rejected.append(f"dataset {name}: hash differs from the reference manifest")
    for name, problems in lineage["problems"].items():
        rejected += [f"lineage {name}: {problem}" for problem in problems]
    if lineage["legacy"]:
        incomplete.append(
            "experiment records predate the scientific fingerprint "
            f"({', '.join(sorted(lineage['legacy']))}); a clean replay is required"
        )
    if lineage.get("dirty"):
        incomplete.append(
            "archived runs were made on a dirty worktree "
            f"({', '.join(sorted(lineage['dirty']))}); kept as labelled history, "
            "a clean replay is required"
        )
    status = "REJECTED" if rejected else "INCOMPLETE" if incomplete else "CERTIFIED"
    return {
        "schema_version": 1,
        "status": status,
        "reasons": [*rejected, *incomplete],
        "profiles": profiles,
        "revision": current["revision"],
        "attestation": attestation(),
        "generated_at": datetime.now(UTC).isoformat(),
    }


def load_docs(directory: Path) -> dict:
    docs = {}
    for kind in KINDS:
        try:
            docs[kind] = json.loads((directory / f"{kind}.json").read_text())
        except (OSError, ValueError):
            docs[kind] = None
    return docs


def archive_lineage(archive: Path = ARCHIVE) -> dict:
    anchor = lineage.files_at(lineage.anchor_revision())
    current = lineage.worktree_files()
    legacy, dirty, problems = [], [], {}
    for path in sorted(archive.glob("run_*.json")):
        record = json.loads(path.read_text())
        if record.get("fingerprint_recipe", 1) == 1:
            legacy.append(path.stem)
        if record.get("worktree_dirty"):
            dirty.append(path.stem)
        found = lineage.check_record(record, anchor, current)
        if found:
            problems[path.stem] = found
    return {"legacy": legacy, "dirty": dirty, "problems": problems}


def reference_hashes(archive: Path = ARCHIVE) -> dict:
    manifest = json.loads((archive / "manifest.json").read_text())["datasets"]
    return {name: item.get("sha256") for name, item in manifest.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE_DIR)
    parser.add_argument("--output", type=Path, default=EVIDENCE_DIR / "release.json")
    args = parser.parse_args(argv)
    report = assess(
        load_docs(args.evidence),
        current=evidence_schema.collect_source(),
        root=ROOT,
        manifest=reference_hashes(),
        lineage=archive_lineage(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"release: {report['status']} ({report['attestation']})")
    for reason in report["reasons"]:
        print(f"  - {reason}")
    return 0 if report["status"] == "CERTIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
