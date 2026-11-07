"""Combine native mutation outcomes with their source and execution bindings.

A stored report can be checked for internal consistency. Current certification
also requires reloading its artifacts against the actual production inventory.
These checks do not independently attest that execution occurred.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from verification import mutation_cache, mutation_catalog, mutation_policy, mutation_run
from verification.mutation_policy import _relative

FORMAT_VERSION = 2
EQUIVALENCE = "verification/mutation_equivalence.json"
HEX64 = re.compile(r"[0-9a-f]{64}")
ATTEMPT = re.compile(r"mutants/attempts/([0-9a-f]{32})/execution\.json")


def _input(root: Path, value: Path | str) -> Path:
    path = Path(value)
    name = path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
    return _relative(name, root)


def _json(root: Path, path: Path) -> dict:
    return mutation_catalog._read(root, path.relative_to(root).as_posix(), {})


def _runtime(proof: dict) -> None:
    runtime = proof["context"]["runtime"]
    command = runtime.get("native_command")
    packages = runtime["packages"]
    if (
        not isinstance(command, list)
        or len(command) != 7
        or command[1:-1] != ["-P", "-m", "mutmut", "run", "--max-children"]
        or not isinstance(command[0], str)
        or not Path(command[0]).is_absolute()
        or not isinstance(command[-1], str)
        or not command[-1].isdecimal()
        or int(command[-1]) <= 0
        or packages.get("mutmut") != "3.8.0"
        or not isinstance(packages.get("pytest"), str)
        or not packages["pytest"]
        or any(not isinstance(value, str) or not value for value in packages.values())
    ):
        raise ValueError("execution runtime does not identify the supported native runner")
    for name in ("python", "platform", "executable_sha256"):
        if not isinstance(runtime.get(name), str) or not runtime[name]:
            raise ValueError("execution runtime identity is incomplete")
    if not HEX64.fullmatch(runtime["executable_sha256"]):
        raise ValueError("execution interpreter hash is invalid")
    environment = runtime.get("environment_sha256")
    if not isinstance(environment, dict) or any(
        environment.get(key) != hashlib.sha256(value.encode()).hexdigest()
        for key, value in mutation_run.FIXED_ENV.items()
    ):
        raise ValueError("execution environment does not match the native launch settings")


def load_campaign(
    root: Path, stats: Path, results: Path, run_report: Path
) -> tuple[dict, list[Path]]:
    """Recompute a campaign from its raw files and current source inventory."""
    root = root.resolve()
    stats, results, run_report = (_input(root, path) for path in (stats, results, run_report))
    sources, configured = mutation_run._scope(root)
    policy = _json(root, root / "verification/mutation_risk_policy.json")
    proof = mutation_cache.validate_execution(root, sources, mutated_sources=configured)
    _runtime(proof)
    run = _json(root, run_report)
    if run.get("proof_sha256") != proof["sha256"] or (
        type(run.get("native_exit_code")) is not int
        or run["native_exit_code"] != proof["native_exit_code"]
    ):
        raise ValueError("controller result differs from the execution proof")
    name = run.get("attempt_record")
    match = ATTEMPT.fullmatch(name) if isinstance(name, str) else None
    if match is None or run.get("native_log") != f"mutants/attempts/{match[1]}/native.log":
        raise ValueError("controller attempt paths are not canonical")
    record_path, log_path = (_input(root, run[name]) for name in ("attempt_record", "native_log"))
    record = _json(root, record_path)
    if (
        record.get("proof") != proof
        or record.get("admission") != run.get("admission")
        or not isinstance(run.get("admission"), dict)
        or run["admission"].get("context_sha256") != mutation_cache._digest(proof["context"])
        or record.get("native_log") != run["native_log"]
        or record.get("native_log_sha256") != hashlib.sha256(log_path.read_bytes()).hexdigest()
        or type(record.get("native_pid")) is not int
        or record["native_pid"] <= 0
    ):
        raise ValueError("immutable attempt record or native log differs from its binding")
    native_stats = _json(root, stats)
    cache = root / mutation_cache.MUTANTS
    native = mutation_catalog.read_native(policy, root, cache, native_stats, results.read_text())
    parsed_metadata = {
        name: digest
        for name, digest in native["metadata_sha256"].items()
        if name.removesuffix(".meta") in configured
    }
    if parsed_metadata != proof["metadata_sha256"]:
        raise ValueError("parsed native metadata differs from the execution binding")
    if mutation_cache.validate_execution(root, sources, mutated_sources=configured) != proof:
        raise ValueError("execution binding changed while the campaign was read")
    equivalence_path = root / EQUIVALENCE
    equivalence = _json(root, equivalence_path) if equivalence_path.is_file() else None
    analysis = mutation_policy.evaluate(
        policy, root, native["catalog"], native["records"], equivalence
    )
    result = {
        "format_version": FORMAT_VERSION,
        "policy": policy,
        "catalog": native["catalog"],
        "records": native["records"],
        "analysis": analysis,
        "equivalence": equivalence,
        "native_stats": native_stats,
        "native_exit_code": proof["native_exit_code"],
        "execution_proof_sha256": proof["sha256"],
        "runtime": proof["context"]["runtime"],
        "paths": {
            name: path.relative_to(root).as_posix()
            for name, path in (("stats", stats), ("results", results), ("run", run_report))
        },
    }
    artifacts = [
        stats,
        results,
        run_report,
        cache / mutation_cache.EXECUTION_RECORD,
        record_path,
        log_path,
    ]
    artifacts.extend(cache / name for name in native["artifacts"])
    artifacts.extend(
        cache / name
        for name, digest in proof["native_artifacts_sha256"].items()
        if digest is not None
    )
    if equivalence is not None:
        artifacts.append(equivalence_path)
    graph = cache / "mutmut-stats.json"
    if graph.is_file():
        artifacts.append(graph)
    return result, sorted(set(artifacts))


def status(result: dict) -> str:
    """Check recorded arithmetic; callers must also validate current artifacts."""
    if type(result.get("format_version")) is not int or result["format_version"] != FORMAT_VERSION:
        raise ValueError("mutation campaign format must be 2")
    if "reason" in result:
        if (
            set(result) != {"format_version", "reason"}
            or not isinstance(result["reason"], str)
            or not result["reason"]
        ):
            raise ValueError("incomplete campaign must state its input failure")
        return "INCOMPLETE"
    analysis = mutation_policy.evaluate_snapshot(
        result["policy"],
        result["analysis"]["sources"],
        result["catalog"],
        result["records"],
        result.get("equivalence"),
    )
    if analysis != result["analysis"] or type(result["native_exit_code"]) is not int:
        raise ValueError("stored mutation arithmetic differs from the recomputed result")
    if analysis["status"] == "FAIL":
        return "FAIL"
    return (
        "PASS" if analysis["status"] == "PASS" and result["native_exit_code"] == 0 else "INCOMPLETE"
    )


def validate_current(result: dict, root: Path) -> list[Path]:
    """Reject a stored result inconsistent with its current source or raw files."""
    paths = result["paths"]
    if not isinstance(paths, dict) or set(paths) != {"stats", "results", "run"}:
        raise ValueError("campaign artifact paths are incomplete")
    fresh, artifacts = load_campaign(
        root, *(_input(root, paths[name]) for name in ("stats", "results", "run"))
    )
    if fresh != result:
        raise ValueError("stored campaign differs from current policy, source or execution")
    return artifacts
