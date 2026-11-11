"""Deterministic sharding of the mutation campaign and fail-closed aggregation.

A shard evidence manifest holds the catalog and outcomes of the modules assigned
to it by a plan, bound to the revision, policy, tests, configuration and runtime
that produced them. The aggregator accepts a campaign only when every shard of the
plan is present exactly once with the same context, every expected mutant appears
exactly once and the per-module arithmetic of the risk policy passes. A shard that
completed with failing scores is still valid diagnostic evidence; execution
failure and quality failure are different statuses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import tomllib
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _installed_version
from pathlib import Path
from typing import Any

from verification import mutation_cache, mutation_catalog, mutation_policy

PACKAGES = (
    "pytest", "pytest-cov", "mutmut", "numpy", "pandas", "scikit-learn", "pyod", "mypy",
    "pandas-stubs", "torch",
)  # fmt: skip
PLAN_FORMAT = 1
SHARD_FORMAT = 1
MANIFEST_KEYS = {
    "format", "plan_sha256", "index", "context", "modules", "sources", "catalog", "records",
    "missing", "native_exit_code",
}  # fmt: skip
CONTEXT_KEYS = ("revision", "tests_sha256", "configuration_sha256", "runtime")


def version(name: str) -> str | None:
    try:
        return _installed_version(name)
    except PackageNotFoundError:
        return None


def _digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def required_modules(policy: dict) -> list[str]:
    return sorted(name for name, unit in policy["units"].items() if "no_mutants" not in unit)


def plan(policy: dict, weights: dict[str, int], count: int) -> dict:
    """Assign every mutating module to one shard, balancing the estimated cost.

    Greedy longest-first placement with a stable order, so the same policy,
    weights and count always give the same plan. Weights are estimates only; the
    aggregation never depends on them.
    """
    if type(count) is not int or count < 1:
        raise ValueError("shard count must be a positive integer")
    modules = required_modules(policy)
    if set(weights) != set(modules) or any(type(w) is not int or w < 0 for w in weights.values()):
        raise ValueError("weights must cover exactly the mutating modules")
    shards: list[dict[str, Any]] = [
        {"index": index, "modules": [], "weight": 0} for index in range(count)
    ]
    for name in sorted(modules, key=lambda item: (-weights[item], item)):
        target = min(
            shards, key=lambda shard: (shard["weight"], len(shard["modules"]), shard["index"])
        )
        target["modules"].append(name)
        target["weight"] += weights[name]
    for shard in shards:
        shard["modules"].sort()
    body = {
        "format": PLAN_FORMAT,
        "policy_sha256": mutation_policy.policy_digest(policy),
        "shards": shards,
    }
    return {**body, "sha256": _digest(body)}


def validate_plan(document: dict, policy: dict) -> None:
    if (
        not isinstance(document, dict)
        or set(document) != {"format", "policy_sha256", "shards", "sha256"}
        or document["format"] != PLAN_FORMAT
    ):
        raise ValueError("invalid shard plan")
    body = {key: document[key] for key in ("format", "policy_sha256", "shards")}
    if document["sha256"] != _digest(body):
        raise ValueError("shard plan digest differs from its content")
    if document["policy_sha256"] != mutation_policy.policy_digest(policy):
        raise ValueError("shard plan belongs to a different policy")
    shards = document["shards"]
    if [shard.get("index") for shard in shards] != list(range(len(shards))) or not shards:
        raise ValueError("shard indexes must be consecutive from zero")
    assigned = [name for shard in shards for name in shard["modules"]]
    if sorted(assigned) != required_modules(policy):
        raise ValueError("shard plan must assign every mutating module exactly once")


def build_shard(
    policy: dict,
    root: Path,
    cache: Path,
    document: dict,
    index: int,
    context: dict,
    native_exit_code: int,
    attempt: Path | None = None,
) -> dict:
    """Read one shard's native cache into an evidence manifest bound to its context.

    With the controller's attempt record the manifest also carries a verified summary
    of the execution proof; without it the manifest is unbound and cannot pass.
    """
    validate_plan(document, policy)
    if type(index) is not int or not 0 <= index < len(document["shards"]):
        raise ValueError("shard index is outside the plan")
    _check_context(context)
    modules = document["shards"][index]["modules"]
    mutation_policy.validate_policy(policy, root)
    catalog, records, _, missing, _, metadata = mutation_catalog.read_modules(
        policy, root, cache, set(modules)
    )
    execution = None
    if attempt is not None:
        execution = _execution_summary(
            attempt, root, shard_patterns(document, index), modules, metadata, native_exit_code
        )
    manifest = {
        "format": SHARD_FORMAT,
        "plan_sha256": document["sha256"],
        "index": index,
        "context": context,
        "modules": modules,
        "sources": {name: _source(root, name) for name in modules},
        "catalog": catalog,
        "records": records,
        "missing": missing,
        "native_exit_code": native_exit_code,
    }
    if execution is not None:
        manifest["execution"] = execution
    return manifest


EXECUTION_KEYS = {
    "attempt_sha256", "native_log_sha256", "proof_sha256", "native_command", "native_exit_code",
    "context_sha256", "tests_sha256", "dependencies_sha256", "runtime", "sources",
    "metadata_sha256", "settled",
}  # fmt: skip


def _execution_summary(
    attempt: Path,
    root: Path,
    patterns: list[str],
    modules: list[str],
    metadata: dict[str, str],
    native_exit_code: int,
) -> dict:
    """Verify the controller's attempt record and keep the parts a shard must prove."""
    content = attempt.read_bytes()
    document = json.loads(content)
    if set(document) != {"native_pid", "admission", "proof", "native_log", "native_log_sha256"}:
        raise ValueError("invalid attempt record")
    proof = document["proof"]
    if proof.get("version") != mutation_cache.EXECUTION_VERSION or proof.get("sha256") != (
        mutation_cache._digest({key: value for key, value in proof.items() if key != "sha256"})
    ):
        raise ValueError("execution proof digest differs from its content")
    context = proof["context"]
    if document["admission"].get("context_sha256") != mutation_cache._digest(context):
        raise ValueError("attempt admission does not match the execution proof")
    log = (root / document["native_log"]).read_bytes()
    if hashlib.sha256(log).hexdigest() != document["native_log_sha256"]:
        raise ValueError("native log differs from the attempt record")
    command = context["runtime"].get("native_command")
    if (
        not isinstance(command, list)
        or len(command) < 7
        or command[1:6] != ["-P", "-m", "mutmut", "run", "--max-children"]
        or not str(command[6]).isdecimal()
        or command[7:] != patterns
        or proof["native_exit_code"] != native_exit_code
    ):
        raise ValueError("execution proof does not describe this shard's native run")
    sources = {name: context["sources"][name]["sha256"] for name in modules}
    if sources != {name: _source(root, name) for name in modules}:
        raise ValueError("execution proof is stale for the shard sources")
    proven = {f"{name}.meta": proof["metadata_sha256"].get(f"{name}.meta") for name in modules}
    if any(proven[name] != metadata.get(name) for name in proven if name in metadata):
        raise ValueError("execution proof does not bind the shard verdict metadata")
    return {
        "attempt_sha256": hashlib.sha256(content).hexdigest(),
        "native_log_sha256": document["native_log_sha256"],
        "proof_sha256": proof["sha256"],
        "native_command": command,
        "native_exit_code": proof["native_exit_code"],
        "context_sha256": mutation_cache._digest(context),
        "tests_sha256": mutation_cache._digest(context["tests"]),
        "dependencies_sha256": mutation_cache._digest(context["dependencies"]),
        "runtime": {
            "python": context["runtime"].get("python"),
            "platform": context["runtime"].get("platform"),
            "packages": {
                name: context["runtime"].get("packages", {}).get(name) for name in PACKAGES
            },
        },
        "sources": sources,
        "metadata_sha256": {name: proof["metadata_sha256"].get(name) for name in sorted(proven)},
        "settled": proof["settled"],
    }


def _source(root: Path, name: str) -> str:
    return hashlib.sha256((root / name).read_bytes()).hexdigest()


def _check_context(context) -> None:
    if (
        not isinstance(context, dict)
        or set(context) != set(CONTEXT_KEYS)
        or any(not context[key] for key in CONTEXT_KEYS)
    ):
        raise ValueError("shard context must bind revision, tests, configuration and runtime")


def aggregate(
    document: dict,
    manifests: list[dict],
    policy: dict,
    root: Path,
    expected_context: dict,
    equivalence: dict | None = None,
) -> dict:
    """Combine shard manifests into one campaign verdict or reject them."""
    validate_plan(document, policy)
    mutation_policy.validate_policy(policy, root)
    _check_context(expected_context)
    shards = document["shards"]
    seen: dict[int, dict[str, Any]] = {}
    for manifest in manifests:
        if (
            not isinstance(manifest, dict)
            or set(manifest) not in (MANIFEST_KEYS, MANIFEST_KEYS | {"execution"})
            or manifest["format"] != SHARD_FORMAT
            or type(manifest["index"]) is not int
        ):
            raise ValueError("invalid shard manifest")
        index = manifest["index"]
        if index in seen:
            raise ValueError(f"shard {index} appears more than once")
        seen[index] = manifest
    if set(seen) != set(range(len(shards))):
        raise ValueError("shard evidence is missing or outside the plan")
    units = policy["units"]
    catalog: dict[str, list[str]] = {name: [] for name in units}
    records: list[dict] = []
    ids: set[str] = set()
    incomplete = False
    bound = []
    for index, shard in enumerate(shards):
        manifest = seen[index]
        if manifest["plan_sha256"] != document["sha256"] or manifest["modules"] != shard["modules"]:
            raise ValueError(f"shard {index} does not belong to this plan")
        if manifest["context"] != expected_context:
            raise ValueError(f"shard {index} was produced in a different context")
        modules = set(shard["modules"])
        if set(manifest["sources"]) != modules or set(manifest["catalog"]) != modules:
            raise ValueError(f"shard {index} reports modules outside its assignment")
        for name in modules:
            if manifest["sources"][name] != _source(root, name):
                raise ValueError(f"shard {index} is stale for {name}")
            catalog[name] = list(manifest["catalog"][name])
        owned = {key for name in modules for key in catalog[name]}
        for record in manifest["records"]:
            key = record.get("id") if isinstance(record, dict) else None
            if key in ids or key not in owned or record.get("path") not in modules:
                raise ValueError(f"shard {index} has an unknown or duplicate mutant record")
            ids.add(key)
            records.append(record)
        bound.append(_check_execution(index, manifest, expected_context, document))
        if manifest["missing"] or type(manifest["native_exit_code"]) is not int:
            incomplete = True
        incomplete = incomplete or manifest["native_exit_code"] != 0
    _check_common_suite([seen[index].get("execution") for index in range(len(shards))])
    sources = {name: _source(root, name) for name in units}
    analysis = mutation_policy.evaluate_snapshot(
        policy, sources, catalog, records, equivalence, expected_context["runtime"]["packages"]
    )
    status = analysis["status"]
    if status == "PASS" and incomplete:
        status = "INCOMPLETE"
    exit_codes = [seen[index]["native_exit_code"] for index in range(len(shards))]
    return {
        "format": SHARD_FORMAT,
        "plan_sha256": document["sha256"],
        "context": expected_context,
        "shards": len(shards),
        "catalog": catalog,
        "records": records,
        "native_exit_code": next((code for code in exit_codes if code != 0), 0),
        "execution_bound": all(bound),
        "analysis": analysis,
        "status": status,
    }


def shard_patterns(document: dict, index: int) -> list[str]:
    """Native mutant-name patterns that select exactly the modules of one shard."""
    if type(index) is not int or not 0 <= index < len(document["shards"]):
        raise ValueError("shard index is outside the plan")
    return [mutation_catalog._module(name) + ".*" for name in document["shards"][index]["modules"]]


def _check_execution(index: int, manifest: dict, expected_context: dict, document: dict) -> bool:
    """True when the shard carries a consistent execution proof; None means unbound."""
    execution = manifest.get("execution")
    if execution is None:
        return False
    if not isinstance(execution, dict) or set(execution) != EXECUTION_KEYS:
        raise ValueError(f"shard {index} has an invalid execution proof")
    runtime = expected_context["runtime"]
    if (
        execution["native_command"][7:] != shard_patterns(document, index)
        or execution["native_exit_code"] != manifest["native_exit_code"]
        or execution["sources"] != manifest["sources"]
        or execution["runtime"]
        != {
            "python": runtime["python"],
            "platform": runtime["platform"],
            "packages": {name: runtime["packages"].get(name) for name in PACKAGES},
        }
    ):
        raise ValueError(f"shard {index} execution proof contradicts its manifest or context")
    return True


def _check_common_suite(executions: list) -> None:
    proven = [item for item in executions if item is not None]
    for key in ("tests_sha256", "dependencies_sha256"):
        if len({item[key] for item in proven}) > 1:
            raise ValueError("shards ran different test suites or dependencies")


def current_context(root: Path) -> dict:
    """Revision, test files, mutation configuration and tool versions of this checkout."""
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    tests = sorted(
        path for base in ("tests", "research/tests") for path in (root / base).rglob("*.py")
    )
    digest = hashlib.sha256()
    for path in tests:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    configuration = tomllib.loads((root / "pyproject.toml").read_text())["tool"]["mutmut"]
    return {
        "revision": revision,
        "tests_sha256": digest.hexdigest(),
        "configuration_sha256": _digest(configuration),
        "runtime": {
            "python": ".".join(map(str, sys.version_info[:3])),
            "platform": platform.platform(),
            "packages": {name: version(name) for name in PACKAGES},
        },
    }


def _load(path: str):
    return json.loads(Path(path).read_text())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("plan")
    make.add_argument("--policy", required=True)
    make.add_argument("--weights", required=True)
    make.add_argument("--count", type=int, required=True)
    make.add_argument("--output", required=True)
    context = commands.add_parser("context")
    context.add_argument("--root", default=".")
    context.add_argument("--output", required=True)
    build = commands.add_parser("build")
    build.add_argument("--root", default=".")
    build.add_argument("--plan", required=True)
    build.add_argument("--index", type=int, required=True)
    build.add_argument("--cache", default="mutants")
    build.add_argument("--native-exit-code", type=int, required=True)
    build.add_argument("--attempt", help="controller attempt record binding the execution")
    build.add_argument("--output", required=True)
    names = commands.add_parser("names")
    names.add_argument("--plan", required=True)
    names.add_argument("--index", type=int, required=True)
    join = commands.add_parser("aggregate")
    join.add_argument("--root", default=".")
    join.add_argument("--plan", required=True)
    join.add_argument("--manifests", nargs="+", required=True)
    join.add_argument("--equivalence")
    join.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    root = Path(getattr(args, "root", ".")).resolve()
    if args.command == "names":
        print(" ".join(shard_patterns(_load(args.plan), args.index)))
        return 0
    if args.command == "plan":
        policy = _load(args.policy)
        result = plan(policy, _load(args.weights), args.count)
    elif args.command == "context":
        result = current_context(root)
    else:
        policy = _load(str(root / "verification/mutation_risk_policy.json"))
        if args.command == "build":
            result = build_shard(
                policy, root, root / args.cache, _load(args.plan), args.index,
                current_context(root), args.native_exit_code,
                Path(args.attempt) if args.attempt else None,
            )  # fmt: skip
        else:
            result = aggregate(
                _load(args.plan), [_load(path) for path in args.manifests], policy, root,
                current_context(root), _load(args.equivalence) if args.equivalence else None,
            )  # fmt: skip
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if args.command == "aggregate":
        print(f"mutation campaign: {result['status']} ({result['shards']} shards)")
        return 0 if result["status"] == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
