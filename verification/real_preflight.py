"""Read-only preflight of the machine that will run the REAL profile.

It reads the interpreter, the installed packages, the three dataset files
(by hash, never by content), the Git state and the workflow, then prints one
line per check. It does not run the benchmark, writes nothing and uploads
nothing. ``--check-registration LABEL`` also reads the repository's runner
list through the GitHub API (a refused read is reported as unknown, never as
proof that no runner exists).

Exit status 1 when any check is ``FAIL``; ``WARN`` is advisory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

from verification import bundles, release

ROOT = Path(__file__).resolve().parents[1]
REPO = "theobigand/etl-anomaly-benchmark"
WORKFLOW = ROOT / ".github" / "workflows" / "verify-release.yml"
MANIFEST = ROOT / "verification" / "evidence" / "manifest.json"
PYTHON_MINOR = "3.11"
MIN_DISK = 5 * 2**30
MIN_CPUS = 2
MIN_RAM = 8 * 2**30
REAL_REPORTS = {
    "experiments/results/real_verification.json",
    "experiments/results/evidence/real.json",
}


@dataclass(frozen=True)
class Result:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class Resources:
    free_bytes: int
    cpus: int
    ram_bytes: int


def check_python(version_info: Sequence[int], expected: str) -> Result:
    found = f"{version_info[0]}.{version_info[1]}"
    status = "PASS" if found == expected else "FAIL"
    return Result("python", status, f"{found} (locked environment uses {expected})")


def check_platform(system: str, machine: str) -> Result:
    if (system, machine) == ("Linux", "x86_64"):
        return Result(
            "platform", "PASS", "Linux x86_64, the platform of the hash-locked environment"
        )
    return Result(
        "platform", "WARN",
        f"{system} {machine}: only a statistical match with the archive can be expected",
    )  # fmt: skip


def check_dependencies(installed: Mapping[str, str | None], locked: Mapping[str, str]) -> Result:
    problems = []
    for name, wanted in locked.items():
        found = installed.get(name)
        if found is None:
            problems.append(f"{name} not installed")
        elif found != wanted:
            problems.append(f"{name} {found} != {wanted}")
    if problems:
        return Result("dependencies", "FAIL", "; ".join(problems))
    return Result("dependencies", "PASS", ", ".join(f"{k} {v}" for k, v in locked.items()))


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, hashlib.sha256).hexdigest()


def check_datasets(paths: Mapping[str, Path], reference: Mapping[str, Any]) -> list[Result]:
    """Presence, SHA-256 against the reference manifest, and file mode. No content is read out."""
    results = []
    for name, path in paths.items():
        if not path.is_file():
            results.append(Result(f"dataset {name}", "FAIL", "file absent"))
            continue
        expected = reference[name]["sha256"]
        same = _sha256(path) == expected
        results.append(
            Result(
                f"dataset {name}",
                "PASS" if same else "FAIL",
                "sha256 matches the reference" if same else "sha256 differs from the reference",
            )
        )
        mode = path.stat().st_mode & 0o777
        if mode & 0o022:
            status, detail = "FAIL", f"mode {mode:o} is writable beyond the owner"
        elif mode & 0o044:
            status, detail = "WARN", f"mode {mode:o} is readable beyond the owner"
        else:
            status, detail = "PASS", f"mode {mode:o}"
        results.append(Result(f"dataset permissions {name}", status, detail))
    return results


def measure_resources(where: Path) -> Resources:
    ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    return Resources(shutil.disk_usage(where).free, os.cpu_count() or 1, ram)


def check_resources(found: Resources) -> Result:
    short = []
    if found.free_bytes < MIN_DISK:
        short.append(f"disk {found.free_bytes // 2**30} GiB free, {MIN_DISK // 2**30} needed")
    if found.cpus < MIN_CPUS:
        short.append(f"cpu {found.cpus}, {MIN_CPUS} needed")
    if found.ram_bytes < MIN_RAM:
        short.append(f"memory {found.ram_bytes // 2**30} GiB, {MIN_RAM // 2**30} needed")
    if short:
        return Result("resources", "FAIL", "; ".join(short))
    free, ram = found.free_bytes // 2**30, found.ram_bytes // 2**30
    return Result("resources", "PASS", f"{free} GiB free, {found.cpus} cpu, {ram} GiB memory")


def git_state(root: Path) -> tuple[str, bool]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    return head, bool(dirty)


def check_revision(head: str, expected: str, dirty: bool) -> Result:
    if not expected:
        return Result("revision", "FAIL", "no approved revision given (--expect-sha)")
    if head != expected:
        return Result("revision", "FAIL", f"HEAD {head[:12]} is not the approved {expected[:12]}")
    if dirty:
        return Result("revision", "FAIL", "the worktree is not clean")
    return Result("revision", "PASS", f"{head[:12]}, clean worktree")


def check_bundle_allowlist(kinds: Mapping[str, Sequence[str]] | None = None) -> Result:
    members = set((kinds if kinds is not None else bundles.KINDS).get("real", ()))
    if members != REAL_REPORTS:
        return Result("bundle allowlist", "FAIL", f"the real bundle allows {sorted(members)}")
    return Result("bundle allowlist", "PASS", "the real bundle allows the two JSON reports only")


def check_upload_paths(workflow: str) -> Result:
    start = workflow.find("  real:")
    if start < 0:
        return Result("upload paths", "FAIL", "no real job in the workflow")
    job = workflow[start : workflow.find("  release:", start)]
    paths = [
        line.split("path:", 1)[1].strip()
        for line in job.splitlines()
        if line.strip().startswith("path:")
    ]
    if paths != ["evidence-real.tgz"]:
        return Result("upload paths", "FAIL", f"the real job uploads {paths}")
    return Result("upload paths", "PASS", "the real job uploads evidence-real.tgz only")


def check_runner(env: Mapping[str, str]) -> Result:
    kind = env.get("RUNNER_ENVIRONMENT")
    if kind is None:
        return Result("runner", "WARN", "not inside a GitHub Actions job (advisory)")
    if kind != "self-hosted":
        return Result("runner", "FAIL", f"RUNNER_ENVIRONMENT is {kind}, not self-hosted")
    return Result("runner", "PASS", "self-hosted")


def check_registration(label: str, listing: Mapping[str, Any] | None) -> Result:
    name = f"registration {label}"
    if listing is None:
        return Result(name, "WARN", "the runner list could not be read; registration is unknown")
    for runner in listing.get("runners", []):
        labels = {entry["name"] for entry in runner.get("labels", [])}
        if runner.get("status") == "online" and {"self-hosted", label} <= labels:
            return Result(name, "PASS", "an online self-hosted runner carries the label")
    return Result(name, "FAIL", "no online self-hosted runner carries the label")


def fetch_registrations(repo: str) -> dict[str, Any] | None:
    done = subprocess.run(
        ["gh", "api", f"repos/{repo}/actions/runners"], capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        return None
    return json.loads(done.stdout)


def _installed(names: Sequence[str]) -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for name in names:
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            found[name] = None
    return found


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-sha", default="", help="commit the operator approved")
    parser.add_argument("--check-registration", metavar="LABEL", help="read the runner list")
    parser.add_argument("--repo", default=REPO)
    return parser.parse_args(argv)


def run_checks(args: argparse.Namespace) -> list[Result]:
    from etl_benchmark.datasets import DATASETS

    reference = json.loads(MANIFEST.read_text())["datasets"]
    locked = release.locked_versions()
    head, dirty = git_state(ROOT)
    results = [
        check_python(tuple(sys.version_info[:3]), PYTHON_MINOR),
        check_platform(platform.system(), platform.machine()),
        check_dependencies(_installed(list(locked)), locked),
        *check_datasets(
            {name: spec.csv for name, spec in DATASETS.items() if name in reference}, reference
        ),
        check_resources(measure_resources(ROOT)),
        check_revision(head, args.expect_sha, dirty),
        check_bundle_allowlist(),
        check_upload_paths(WORKFLOW.read_text()),
        check_runner(os.environ),
    ]
    if args.check_registration:
        results.append(check_registration(args.check_registration, fetch_registrations(args.repo)))
    return results


def main(
    argv: Sequence[str] | None = None, checks: Callable[..., list[Result]] | None = None
) -> int:
    args = parse_args(argv)
    results = (checks or run_checks)(args)
    for result in results:
        print(f"{result.status} {result.name}: {result.detail}")
    failed = [r for r in results if r.status == "FAIL"]
    warned = [r for r in results if r.status == "WARN"]
    if failed:
        print(f"preflight: FAIL ({len(failed)} failed)")
        return 1
    print(f"preflight: PASS ({len(warned)} warning{'' if len(warned) == 1 else 's'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
