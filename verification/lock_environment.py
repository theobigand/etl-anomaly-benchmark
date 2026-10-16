"""Write the exact conda and pip package lists of the active environment.

``conda list --explicit --sha256`` pins every conda package by URL and hash;
the packages conda reports from PyPI are pinned by version (the editable
install of this project is left out). The lock is platform specific and is only a record of
the environment the results were produced in; it never changes ``environment.yml``.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "verification" / "environment"


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conda-env", default="etl-benchmark")
    parser.add_argument("--output", type=Path, default=TARGET)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    system = f"{platform.system().lower()}-{platform.machine()}"
    explicit = conda_lock(args.conda_env)
    (args.output / f"conda-{system}.explicit.txt").write_text(explicit)
    (args.output / "pip-freeze.txt").write_text(pip_lock(args.conda_env, explicit))
    print(f"wrote the lock of {args.conda_env} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
