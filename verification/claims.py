"""Tie every published verification figure to the run that produced it.

``claims.json`` holds the figures quoted in ``paper/main.tex`` and a
``published_run`` block that names the run: revision, where it was produced,
platform and date. A current run keeps its evidence envelopes (and the mutant
listing) under ``evidence/runs/<id>/``, sealed by sha256; the figures are read
from those envelopes by ``archive`` and checked against them by ``check_run``.
A run is stale as soon as the scientific fingerprint differs or code changed in
the repository since its revision; documentation alone does not age it. A
historical run (figures kept for the record) must say why.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from verification import evidence_schema, mutation_scope

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "verification" / "claims.json"
RUNS = "verification/evidence/runs"
KINDS = ("fast", "deep", "faults", "real", "tools", "types", "reproduction")
IDENTITY = ("revision", "source", "platform", "captured")
_HEX40 = re.compile(r"[0-9a-f]{40}")
CODE_PREFIXES = ("src/", "experiments/", "tests/", ".github/")
CODE_FILES = ("Makefile", "pyproject.toml", "environment.yml")


def load(path: Path | None = None) -> dict:
    return json.loads((path or CLAIMS).read_text())


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_code(path: str) -> bool:
    """Whether a changed file can alter what a verification run measured."""
    if path.startswith(CODE_PREFIXES) or path in CODE_FILES:
        return True
    configuration = ("verification/release_policy.json", "verification/mutation_scope.json")
    return path.startswith("verification/") and path.count("/") == 1 and (
        path.endswith(".py") or path in configuration
    )  # fmt: skip


def _in_scientific(candidate: str, scientific: list[str]) -> bool:
    for entry in scientific:
        if entry.endswith("/") and (candidate + "/").startswith(entry):
            return True
        if candidate + ".py" == entry or (candidate + "/").startswith(entry + "/"):
            return True
    return False


def split_mutants(text: str, scope: dict) -> dict:
    """Killed and total mutants of the scientific modules and of everything else."""
    counts = {"scientific_killed": 0, "scientific_total": 0, "other_killed": 0, "other_total": 0}
    for line in text.splitlines():
        name, sep, status = line.strip().partition(": ")
        if not sep or ".x" not in name:
            continue
        module = name.rsplit(".", 1)[0].replace(".", "/")
        path = f"src/{module}" if module.startswith("etl_benchmark/") else module
        which = "scientific" if _in_scientific(path, scope.get("scientific", [])) else "other"
        counts[f"{which}_total"] += 1
        counts[f"{which}_killed"] += status.strip() == "killed"
    return counts


def figures_from_run(directory: Path, scope: dict) -> dict:
    """The figures the manuscript quotes, read from the envelopes of a run."""

    def envelope(kind: str) -> dict:
        return json.loads((directory / f"{kind}.json").read_text())

    fast, tools = envelope("fast")["result"], envelope("tools")["result"]
    stats = envelope("deep")["result"]["stats"]
    mutation = {
        "killed": stats["killed"],
        "total": stats["total"],
        "survived": stats["survived"],
        **split_mutants((directory / "results.txt").read_text(), scope),
    }
    return {
        "fast": {
            "tests": fast["tests"]["total"],
            "line_covered": fast["coverage"]["line"]["covered"],
            "line_coverable": fast["coverage"]["line"]["coverable"],
            "branch_covered": fast["coverage"]["branch"]["covered"],
            "branch_coverable": fast["coverage"]["branch"]["coverable"],
        },
        "verifier": {
            "line": tools["coverage"]["line"]["covered"],
            "branch": tools["coverage"]["branch"]["covered"],
        },
        "mutation": mutation,
        "faults": len(envelope("faults")["result"]["faults"]),
    }


def paper_identity(doc: dict) -> str:
    run = doc["published_run"]
    where = (
        "local run, not independently attested"
        if run["source"] == "local-unattested"
        else run["source"]
    )
    return f"commit {run['revision'][:8]} ({where})"


def check_paper(doc: dict, tex: str) -> list[str]:
    identity = paper_identity(doc)
    squashed = re.sub(r"\s+", " ", tex)
    if identity not in squashed:
        return [f"the manuscript names no run: it must say {identity!r}"]
    return []


def _check_identity(run: dict) -> list[str]:
    problems = [f"published_run.{key} is missing" for key in IDENTITY if not run.get(key)]
    revision = run.get("revision")
    if revision and not _HEX40.fullmatch(revision):
        problems.append("published_run.revision must be a 40-character commit hash")
    source = run.get("source", "local-unattested")
    if source != "local-unattested" and not str(source).startswith("ci-run:"):
        problems.append("published_run.source must be local-unattested or ci-run:<id>")
    return problems


def check_run(doc: dict, *, root: Path, scientific_fingerprint: str, scope: dict) -> list[str]:
    """Reasons the claims are not a faithful, current account of one run."""
    run = doc.get("published_run")
    if not isinstance(run, dict):
        return ["published_run is missing: the figures do not say which run they describe"]
    problems = _check_identity(run)
    if problems:
        return problems
    revision = run["revision"]
    if _git(root, "merge-base", "--is-ancestor", revision, "HEAD").returncode != 0:
        return [f"revision {revision[:8]} is not in the history of HEAD"]
    if run.get("historical"):
        return (
            [] if str(run.get("note", "")).strip() else ["a historical run needs a note saying why"]
        )
    directory = root / run.get("evidence_dir", "")
    if not run.get("evidence_dir") or not directory.is_dir():
        return ["the run has no evidence_dir with its envelopes"]
    for name, expected in sorted(run.get("files", {}).items()):
        path = directory / name
        if not path.is_file():
            problems.append(f"run file {name} is missing")
        elif _sha256(path) != expected:
            problems.append(f"run file {name} hash differs from the sealed one")
    for kind in KINDS:
        if kind not in {n.removesuffix(".json") for n in run.get("files", {})}:
            problems.append(f"the run has no {kind} envelope")
    if problems:
        return problems
    for kind in KINDS:
        envelope = json.loads((directory / f"{kind}.json").read_text())
        problems += [f"{kind}: {p}" for p in evidence_schema.validate(envelope)]
        problems += _check_envelope(kind, envelope, revision, scientific_fingerprint)
    changed = _git(root, "diff", "--name-only", revision, "HEAD").stdout.split()
    problems += [
        f"{path} changed since the run, so its figures may be stale"
        for path in changed
        if is_code(path)
    ]
    if problems:
        return problems
    derived = figures_from_run(directory, scope)
    for group, values in derived.items():
        have = doc.get(group)
        for key, value in values.items() if isinstance(values, dict) else [(None, values)]:
            claimed = have if key is None else (have or {}).get(key)
            if claimed != value:
                label = group if key is None else f"{group}.{key}"
                problems.append(f"{label} is {claimed!r} in the claims but {value!r} in the run")
    return problems


def _check_envelope(kind: str, envelope: dict, revision: str, fingerprint: str) -> list[str]:
    source = envelope.get("source", {})
    problems = []
    if envelope.get("status") != "PASS":
        problems.append(f"{kind}: status is {envelope.get('status')}")
    if source.get("revision") != revision:
        problems.append(f"{kind}: revision {str(source.get('revision'))[:8]} is not the run's")
    if source.get("worktree_dirty"):
        problems.append(f"{kind}: produced from a dirty worktree")
    if source.get("scientific_fingerprint") != fingerprint:
        problems.append(f"{kind}: scientific fingerprint differs from the current source")
    return problems


def archive(
    *, run_id, source_label, platform, evidence, results, root, claims_path, scope, captured
) -> dict:  # noqa: PLR0913
    """Copy the envelopes of a finished run into the repository and seal the claims on them."""
    target = root / RUNS / run_id
    docs = {kind: json.loads((evidence / f"{kind}.json").read_text()) for kind in KINDS}
    revisions = {doc["source"]["revision"] for doc in docs.values()}
    if len(revisions) != 1:
        raise ValueError(f"the envelopes come from different revisions: {sorted(revisions)}")
    target.mkdir(parents=True, exist_ok=True)
    for kind in KINDS:
        shutil.copyfile(evidence / f"{kind}.json", target / f"{kind}.json")
    shutil.copyfile(results, target / "results.txt")
    doc = json.loads(claims_path.read_text()) if claims_path.is_file() else {}
    doc["schema_version"] = 2
    doc["published_run"] = {
        "id": run_id,
        "revision": revisions.pop(),
        "source": source_label,
        "platform": platform,
        "captured": captured,
        "historical": False,
        "evidence_dir": f"{RUNS}/{run_id}",
        "files": {p.name: _sha256(p) for p in sorted(target.iterdir())},
    }
    doc.update(figures_from_run(target, scope))
    claims_path.write_text(json.dumps(doc, indent=2) + "\n")
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="check claims.json against its run and the manuscript")
    make = sub.add_parser("archive", help="seal a finished run into the repository")
    make.add_argument("--id", required=True)
    make.add_argument("--source", default="local-unattested")
    make.add_argument("--platform", required=True)
    make.add_argument("--evidence", type=Path, default=ROOT / "experiments/results/evidence")
    make.add_argument("--results", type=Path, default=ROOT / "mutants/results.txt")
    args = parser.parse_args(argv)
    scope = mutation_scope.load()
    if args.command == "archive":
        doc = archive(
            run_id=args.id, source_label=args.source, platform=args.platform,
            evidence=args.evidence, results=args.results, root=ROOT, claims_path=CLAIMS,
            scope=scope, captured=date.today().isoformat(),
        )  # fmt: skip
        print(f"sealed run {args.id} at {doc['published_run']['revision'][:8]}")
        return 0
    doc = load()
    problems = check_run(
        doc,
        root=ROOT,
        scientific_fingerprint=evidence_schema.collect_source()["scientific_fingerprint"],
        scope=scope,
    )
    problems += check_paper(doc, (ROOT / "paper" / "main.tex").read_text())
    for problem in problems:
        print(f"claims: {problem}")
    print(f"claims: {'FAIL' if problems else 'PASS'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
