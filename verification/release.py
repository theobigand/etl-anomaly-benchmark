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
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from verification import claims, evidence_schema, lineage, mutation_scope

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "verification" / "release_policy.json"
POLICY_VERSION = 1
EVIDENCE_DIR = ROOT / "experiments" / "results" / "evidence"
ARCHIVE = ROOT / "verification" / "evidence"
LOCK = ROOT / "verification" / "environment"
# Packages whose version can change a scientific result. Every profile must
# record them and they must agree across profiles and with the recorded lock.
RESULT_PACKAGES = ("numpy", "pandas", "scikit-learn", "pyod")


def load_policy(path: Path = POLICY) -> dict:
    """The versioned list of evidence a release needs (and what it does not)."""
    policy = json.loads(path.read_text())
    if policy.get("version") != POLICY_VERSION:
        raise ValueError(f"release policy version must be {POLICY_VERSION}")
    return policy


def attestation() -> str:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return f"ci-run:{os.environ.get('GITHUB_RUN_ID', 'unknown')} (not independently attested)"
    return "local-unattested"


def locked_versions(directory: Path = LOCK) -> dict[str, str]:
    """Result-affecting package versions pinned by the recorded environment lock."""
    pinned: dict[str, str] = {}
    for explicit in sorted(directory.glob("conda-*.explicit.txt")):
        for line in explicit.read_text().splitlines():
            if line.startswith("http"):
                stem = line.rsplit("/", 1)[1].split("#")[0]
                name, found, _ = stem.rsplit("-", 2)
                pinned.setdefault(name, found)
    freeze = directory / "pip-freeze.txt"
    if freeze.is_file():
        for line in freeze.read_text().splitlines():
            name, sep, found = line.partition("==")
            if sep:
                pinned.setdefault(name.strip().lower(), found.strip())
    return {name: pinned[name] for name in RESULT_PACKAGES if name in pinned}


def _minor(version: str) -> str:
    return ".".join(version.split(".")[:2])


def check_typing(doc: dict, pins: dict) -> list[str]:
    """The typing baseline is only valid for the pinned checker and stubs."""
    problems = []
    for package, pinned in pins.items():
        found = doc["result"].get(package)
        if found != pinned:
            problems.append(f"types: {package} {found} is not the pinned {pinned}")
    return problems


def check_environments(docs: dict, locked: dict) -> tuple[list[str], list[str], dict]:
    """Compare the environments of the valid profiles; see ``assess``.

    Rejected: a result-affecting version missing, or two profiles disagreeing
    on a result-affecting version or on the Python minor version. Incomplete:
    the versions are consistent but differ from the recorded lock (or no lock
    exists), so exact-environment certification is not demonstrated. The
    operating system may differ between profiles: that is cross-platform
    evidence and is labelled as such, not rejected.
    """
    rejected: list[str] = []
    incomplete: list[str] = []
    seen = {kind: doc["environment"] for kind, doc in docs.items() if doc is not None}
    for kind, environment in seen.items():
        for package in RESULT_PACKAGES:
            if not environment["packages"].get(package):
                rejected.append(f"{kind}: the {package} version is not recorded")
    for package in RESULT_PACKAGES:
        versions = {k: e["packages"].get(package) for k, e in seen.items()}
        if len({v for v in versions.values() if v}) > 1:
            listing = ", ".join(f"{k}={v}" for k, v in versions.items() if v)
            rejected.append(f"{package}: the profiles ran different versions ({listing})")
    minors = {kind: _minor(e["python"]) for kind, e in seen.items()}
    if len(set(minors.values())) > 1:
        listing = ", ".join(f"{k}={v}" for k, v in minors.items())
        rejected.append(f"python: the profiles ran different minor versions ({listing})")
    packages = {}
    for package in RESULT_PACKAGES:
        found = [e["packages"][package] for e in seen.values() if e["packages"].get(package)]
        packages[package] = found[0] if found else None
    drift = [
        f"{package} {found} (lock {locked.get(package)})"
        for package, found in packages.items()
        if found and locked.get(package) != found
    ]
    if drift:
        incomplete.append(
            "the environment differs from the recorded lock: " + ", ".join(drift)
            if locked
            else "no environment lock is recorded for " + ", ".join(RESULT_PACKAGES)
        )
    platforms = sorted({e["platform"] for e in seen.values()})
    exact = not drift and len(platforms) == 1 and len(set(minors.values())) == 1
    return rejected, incomplete, {
        "mode": "exact-environment" if exact else "cross-platform",
        "platforms": platforms,
        "packages": packages,
        "locked": locked,
    }  # fmt: skip


def freshness(root: Path = ROOT):
    """Predicate: is evidence of that revision still current at HEAD?

    It is when the revision is an ancestor of HEAD and no code or configuration changed
    since (``claims.is_code``); documentation and archived evidence do not age it.
    """

    def fresh(revision: str) -> bool:
        def git(*args):
            return subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True, check=False
            )

        if git("merge-base", "--is-ancestor", revision, "HEAD").returncode != 0:
            return False
        changed = git("diff", "--name-only", revision, "HEAD").stdout.split()
        return not any(claims.is_code(path) for path in changed)

    return fresh


def assess(docs, *, current, root, manifest, lineage, locked, scope, policy, fresh=None) -> dict:  # noqa: PLR0912
    """Pure decision over the loaded evidence; see the module docstring."""
    rejected: list[str] = []
    incomplete: list[str] = []
    profiles = {}
    if current.get("worktree_dirty"):
        rejected.append("the worktree is dirty: a release needs a clean source")
    for kind in policy["required"]:
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
        moved = source["revision"] != current["revision"]
        if moved and (fresh is None or fresh(source["revision"]) is not True):
            reason = "is not the current one"
            if fresh is not None:
                reason += " (not an ancestor, or code changed since)"
            rejected.append(f"{kind}: revision {source['revision'][:8]} {reason}")
        if source["scientific_fingerprint"] != current["scientific_fingerprint"]:
            rejected.append(f"{kind}: scientific fingerprint differs from the current source")
        if source["worktree_dirty"]:
            rejected.append(f"{kind}: produced from a dirty worktree")
    valid = {
        kind: doc
        for kind, doc in docs.items()
        if kind in profiles and doc is not None and profiles[kind] != "INVALID"
    }
    if "types" in valid:
        rejected += check_typing(valid["types"], policy["typing_pins"])
    if "deep" in valid:
        rejected += [
            f"deep scope: {problem}"
            for problem in mutation_scope.check_evidence(
                valid["deep"]["result"], scope["inventory"], scope["config"]
            )
        ]
    env_rejected, env_incomplete, environment = check_environments(
        {k: d for k, d in valid.items() if k != "types"}, locked
    )
    rejected += env_rejected
    incomplete += env_incomplete
    revisions = {d["source"]["revision"] for d in docs.values() if d and "source" in d}
    if len(revisions) > 1:
        rejected.append("revision: the profiles were produced on different revisions")
    executions = {}
    for kind, doc in docs.items():
        if doc is None or profiles.get(kind) == "INVALID":
            continue
        where = doc.get("execution")
        executions[kind] = (
            "unrecorded"
            if where is None
            else where["runner_environment"] or "ci"
            if where["ci"]
            else "local"
        )
    real = docs.get("real")
    if real is not None and profiles["real"] != "INVALID":
        if "execution" not in real:
            rejected.append("real: the execution context is not recorded")
        elif real["execution"]["ci"] and real["execution"]["runner_environment"] != "self-hosted":
            rejected.append(
                "real: produced by a CI run on a hosted runner, which cannot hold the research "
                "datasets"
            )
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
    performance = {}
    for name, (state, reasons) in sorted(lineage.get("performance", {}).items()):
        performance[name] = state
        if state == "STALE":
            incomplete.append(
                f"performance evidence {name} is stale: {'; '.join(reasons)}; "
                "re-measure it or withdraw it from the publication"
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
        "executions": executions,
        "policy": {
            key: policy[key]
            for key in ("version", "required", "optional", "deferred", "not_applicable")
        },
        "environment": environment,
        "performance": performance,
        "revision": current["revision"],
        "attestation": attestation(),
        "generated_at": datetime.now(UTC).isoformat(),
    }


def load_docs(directory: Path, kinds) -> dict:
    docs = {}
    for kind in kinds:
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
    performance = {}
    scaling = archive / "scaling.json"
    if scaling.is_file():
        performance["scaling"] = lineage.check_measurement(json.loads(scaling.read_text()), current)
    return {"legacy": legacy, "dirty": dirty, "problems": problems, "performance": performance}


def reference_hashes(archive: Path = ARCHIVE) -> dict:
    manifest = json.loads((archive / "manifest.json").read_text())["datasets"]
    return {name: item.get("sha256") for name, item in manifest.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE_DIR)
    parser.add_argument("--output", type=Path, default=EVIDENCE_DIR / "release.json")
    args = parser.parse_args(argv)
    config = mutation_scope.load()
    policy = load_policy()
    report = assess(
        load_docs(args.evidence, policy["required"]),
        current=evidence_schema.collect_source(),
        root=ROOT,
        manifest=reference_hashes(),
        lineage=archive_lineage(),
        locked=locked_versions(),
        scope={"inventory": mutation_scope.inventory(ROOT, config), "config": config},
        policy=policy,
        fresh=freshness(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"release: {report['status']} ({report['attestation']})")
    for reason in report["reasons"]:
        print(f"  - {reason}")
    return 0 if report["status"] == "CERTIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
