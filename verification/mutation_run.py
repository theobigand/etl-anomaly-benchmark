"""Run native mutation in an owned POSIX process group before binding its cache.

A terminal parent alone is insufficient when workers remain alive. Unresolved
attempts retain their pending record and require process inspection before reuse.
This command records execution provenance, not mutation-policy compliance.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import platform
import subprocess
import sys
import tomllib
from importlib.metadata import distributions
from pathlib import Path
from uuid import uuid4

from verification import mutation_cache, mutation_scope
from verification.mutation_policy import _relative, validate_policy

FIXED_ENV = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONPATH": "",
}
ENVIRONMENT_KEYS = (
    *FIXED_ENV,
    "PYTEST_ADDOPTS",
    "PYTEST_PLUGINS",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
    "COVERAGE_PROCESS_START",
    "COVERAGE_RCFILE",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "CUDA_VISIBLE_DEVICES",
)


def collect_runtime(env: dict[str, str]) -> dict:
    """Observe this interpreter and installed versions; do not accept supplied pins."""
    packages: dict[str, str] = {}
    for distribution in distributions():
        name = distribution.metadata["Name"].lower().replace("_", "-")
        if name in packages and packages[name] != distribution.version:
            raise ValueError("conflicting installed distribution versions")
        packages[name] = distribution.version
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "executable_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "packages": dict(sorted(packages.items())),
        "environment_sha256": {
            key: hashlib.sha256(env[key].encode()).hexdigest() if key in env else None
            for key in ENVIRONMENT_KEYS
        },
    }


def _command(max_children: int) -> list[str]:
    return [sys.executable, "-P", "-m", "mutmut", "run", "--max-children", str(max_children)]


def _scope(root: Path) -> tuple[list[str], list[str]]:
    policy = json.loads((root / "verification/mutation_risk_policy.json").read_text())
    validate_policy(policy, root)
    configuration = tomllib.loads((root / "pyproject.toml").read_text())["tool"]["mutmut"]
    configured = mutation_scope.resolve(
        configuration["only_mutate"], root, configuration.get("do_not_mutate", [])
    )
    sources = sorted(policy["units"])
    required = {name for name, unit in policy["units"].items() if "no_mutants" not in unit}
    if required - set(configured) or set(configured) - set(sources):
        raise ValueError("native scope does not match the classified production inventory")
    roots = [_relative(name, root) for name in configuration.get("source_paths", [])]
    if any(not any((root / name).is_relative_to(base) for base in roots) for name in configured):
        raise ValueError("native source roots do not cover the configured scope")
    return sources, configured


def _require_terminal_group(pid: int) -> None:
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return
    except PermissionError as error:
        raise ValueError(
            "native process group cannot be inspected; retain pending execution"
        ) from error
    raise ValueError("native process group still has workers; retain pending execution")


def run(root: Path, *, max_children: int = 2, names: tuple[str, ...] = ()) -> dict:
    """Run the configured scope exclusively; preserve partial results honestly."""
    if type(max_children) is not int or max_children <= 0:
        raise ValueError("max children must be a positive integer")
    root = root.resolve()
    sources, configured = _scope(root)
    cache = _relative(mutation_cache.MUTANTS, root)
    cache.mkdir(parents=True, exist_ok=True)
    lock = _relative("mutants/execution.lock", root)
    with lock.open("a+") as ownership:
        try:
            fcntl.flock(ownership, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("mutation cache already has an active controller") from error
        env = {**os.environ, **FIXED_ENV}
        command = [*_command(max_children), *names]
        runtime = {**collect_runtime(env), "native_command": command}
        admission = mutation_cache.prepare_execution(
            root, sources, runtime=runtime, mutated_sources=configured
        )
        pending = cache / mutation_cache.PENDING_EXECUTION
        attempt = _relative(f"mutants/attempts/{uuid4().hex}", root)
        attempt.mkdir(parents=True)
        log_path = attempt / "native.log"
        with log_path.open("x") as log:
            process = subprocess.Popen(
                command,
                cwd=root,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            document = json.loads(pending.read_text())
            document["native_pid"] = process.pid
            document["native_log"] = log_path.relative_to(root).as_posix()
            mutation_cache._write_json(pending, document)
            exit_code = process.wait()
        _require_terminal_group(process.pid)
        if _scope(root) != (sources, configured):
            raise ValueError("scope changed during native execution; retain pending execution")
        observed = {**collect_runtime(env), "native_command": command}
        proof = mutation_cache.record_execution(
            root,
            sources,
            runtime=observed,
            native_exit_code=exit_code,
            mutated_sources=configured,
        )
        record_path = attempt / "execution.json"
        mutation_cache._write_json(
            record_path,
            {
                "native_pid": process.pid,
                "admission": admission,
                "proof": proof,
                "native_log": log_path.relative_to(root).as_posix(),
                "native_log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
            },
        )
        return {
            "native_exit_code": exit_code,
            "admission": admission,
            "proof_sha256": proof["sha256"],
            "native_log": log_path.relative_to(root).as_posix(),
            "attempt_record": record_path.relative_to(root).as_posix(),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--max-children", type=int, default=2)
    parser.add_argument("--names", nargs="*", default=[], help="native mutant-name patterns")
    args = parser.parse_args(argv)
    report = run(args.root, max_children=args.max_children, names=tuple(args.names))
    print(json.dumps(report, sort_keys=True))
    return 0 if report["native_exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
