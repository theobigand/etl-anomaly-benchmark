"""Write the exact conda and pip package lists of the active environment.

``conda list --explicit --sha256`` pins every conda package by URL and hash;
the packages conda reports from PyPI are pinned by version (the editable
install of this project is left out). The lock is platform specific and is only a record of
the environment the results were produced in; it never changes ``environment.yml``.

``--linux`` writes the Linux lock. It is not read from a Linux machine: pip resolves
the project requirements for Linux x86_64 CPython 3.11 wheels (``--platform``,
``--abi``, ``--only-binary``) with the versions that affect results held to the ones
recorded in the macOS lock, and every wheel is pinned by version and sha256, so
``pip install --require-hashes --no-deps -r`` rebuilds it exactly.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "verification" / "environment"
LINUX_LOCK = "linux-x86_64-py311.lock.txt"
LINUX_PYTHON = "3.11"
LINUX_PLATFORMS = ("manylinux2014_x86_64", "manylinux_2_17_x86_64", "manylinux_2_28_x86_64")


def conda_lock(name: str) -> str:
    out = subprocess.check_output(
        ["conda", "list", "-n", name, "--explicit", "--sha256"], text=True
    )
    return out


def _norm(name: str) -> str:
    return name.lower().replace("_", "-")


def conda_names(explicit: str) -> set[str]:
    """Package names in an explicit conda lock (``base`` builds count for their parent)."""
    names = set()
    for line in explicit.splitlines():
        if line.startswith("http"):
            filename = line.rsplit("/", 1)[1].split("#")[0]
            name = _norm(filename.rsplit("-", 2)[0])
            names |= {name, name.removesuffix("-base")}
    return names


def pip_lock(name: str, explicit: str) -> str:
    """Packages installed from PyPI, pinned by version.

    A name that conda also installs is left out and listed in a comment: pip
    may keep a stale record of it, while the files on disk belong to the conda
    package.
    """
    out = subprocess.check_output(["conda", "list", "-n", name, "--json"], text=True)
    owned = conda_names(explicit)
    pypi = {
        item["name"]: item["version"]
        for item in json.loads(out)
        if item["channel"] == "pypi" and item["name"] != "etl-benchmark"
    }
    kept = {key: value for key, value in pypi.items() if _norm(key) not in owned}
    skipped = sorted(set(pypi) - set(kept), key=str.lower)
    header = f"# installed by conda as well, not pinned here: {', '.join(skipped)}\n"
    return header + "".join(f"{key}=={kept[key]}\n" for key in sorted(kept, key=str.lower))


def project_requirements(pyproject: Path = ROOT / "pyproject.toml") -> list[str]:
    """Runtime requirements and every extra, as declared (unpinned).

    PyTorch is left out: PyPI serves the CUDA build for Linux, with a long list of
    GPU libraries, while the archived runs and their reproduction use no neural
    detector. The Linux environment rebuilt from this lock runs them without it.
    """
    project = tomllib.loads(pyproject.read_text())["project"]
    found = list(project["dependencies"])
    for extra in project.get("optional-dependencies", {}).values():
        found += extra
    return [req for req in dict.fromkeys(found) if not req.startswith("torch")]


def resolve_linux(requirements: list[str], held: dict[str, str], workdir: Path) -> dict:
    """pip's installation report for Linux wheels, without installing anything."""
    constraints = workdir / "constraints.txt"
    constraints.write_text("".join(f"{name}=={found}\n" for name, found in sorted(held.items())))
    report = workdir / "report.json"
    command = ["python", "-m", "pip", "install", "--dry-run", "--ignore-installed", "--quiet"]
    command += ["--report", str(report), "--target", str(workdir / "target")]
    command += ["--only-binary=:all:", "--python-version", LINUX_PYTHON, "--implementation", "cp"]
    command += ["--abi", "cp" + LINUX_PYTHON.replace(".", "")]
    for tag in LINUX_PLATFORMS:
        command += ["--platform", tag]
    command += ["-c", str(constraints), *requirements]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=900)
    return json.loads(report.read_text())


def format_linux_lock(report: dict, held: dict[str, str]) -> str:
    """One ``name==version --hash=sha256:...`` line per wheel, sorted by name."""
    pins = {}
    for item in report["install"]:
        try:
            digest = item["download_info"]["archive_info"]["hashes"]["sha256"]
        except KeyError as exc:
            raise ValueError(f"no sha256 hash for {item['metadata']['name']}") from exc
        name = re.sub(r"[-_.]+", "-", item["metadata"]["name"]).lower()
        pins[name] = f"{name}=={item['metadata']['version']} --hash=sha256:{digest}"
    header = [
        "# Linux x86_64, CPython 3.11 (cp311), manylinux wheels only.",
        "# Resolved by pip for that platform, not on a Linux machine; install with",
        "#   pip install --require-hashes --no-deps -r <this file>",
        "# Held to the versions recorded in the macOS lock: "
        + ", ".join(f"{name}=={found}" for name, found in sorted(held.items())),
    ]
    return "\n".join(header + [pins[name] for name in sorted(pins)]) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conda-env", default="etl-benchmark")
    parser.add_argument("--output", type=Path, default=TARGET)
    parser.add_argument("--linux", action="store_true", help="write the Linux lock instead")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.linux:
        from verification import release

        held = release.locked_versions()
        with tempfile.TemporaryDirectory() as work:
            report = resolve_linux(project_requirements(), held, Path(work))
        (args.output / LINUX_LOCK).write_text(format_linux_lock(report, held))
        print(f"wrote the Linux lock to {args.output / LINUX_LOCK}")
        return 0
    system = f"{platform.system().lower()}-{platform.machine()}"
    explicit = conda_lock(args.conda_env)
    (args.output / f"conda-{system}.explicit.txt").write_text(explicit)
    (args.output / "pip-freeze.txt").write_text(pip_lock(args.conda_env, explicit))
    print(f"wrote the lock of {args.conda_env} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
