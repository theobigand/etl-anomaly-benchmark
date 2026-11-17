#!/usr/bin/env bash
# Build the release environment from the recorded Linux lock: Linux x86_64, CPython 3.11,
# hash-pinned wheels, no dependency resolution and no source build. pip, setuptools and
# wheel come with the standard-library venv and are not part of the base lock.
#
#   install_locked.sh <venv> [--with-extras] [--editable-project]
#
# --with-extras       also install the hash-pinned supplement (CPU-only PyTorch stack and the
#                     pinned typing tools); torch is served by the PyTorch CPU index
# --editable-project  then install this project itself, without dependencies
#
# Every profile of the release (FAST, FAULTS, static, reproduction, DEEP, REAL, the gate) goes
# through this one script. The last step compares what is installed with every pin.
set -euo pipefail

venv=${1:?usage: install_locked.sh <directory for the new environment> [--with-extras] [--editable-project]}
shift
extras=0
editable=0
for flag in "$@"; do
  case "$flag" in
    --with-extras) extras=1 ;;
    --editable-project) editable=1 ;;
    *) echo "unknown option: $flag" >&2; exit 2 ;;
  esac
done
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
lock=$root/verification/environment/linux-x86_64-py311.lock.txt
extras_lock=$root/verification/environment/linux-x86_64-py311.extras.lock.txt

[ "$(uname -s)-$(uname -m)" = "Linux-x86_64" ] || { echo "the lock is for Linux x86_64" >&2; exit 1; }
python -c 'import sys; sys.exit(sys.version_info[:2] != (3, 11))' \
  || { echo "the lock is for CPython 3.11" >&2; exit 1; }

python -m venv "$venv"
pip_install=("$venv/bin/python" -m pip install --quiet --disable-pip-version-check --no-input)
"${pip_install[@]}" --require-hashes --no-deps --only-binary=:all: -r "$lock"
check=("$lock")
if [ "$extras" = 1 ]; then
  "${pip_install[@]}" --require-hashes --no-deps --only-binary=:all: \
    --extra-index-url https://download.pytorch.org/whl/cpu -r "$extras_lock"
  check+=("$extras_lock")
fi
if [ "$editable" = 1 ]; then
  [ "$extras" = 1 ] || { echo "--editable-project needs --with-extras (pinned setuptools)" >&2; exit 2; }
  (cd "$root" && "${pip_install[@]}" --no-deps --no-build-isolation -e .)
fi
# Compare every installed distribution with its pin; any difference fails the installation.
"$venv/bin/python" - "${check[@]}" <<'PY'
import sys
from importlib import metadata
from pathlib import Path


def pins(path: str) -> dict[str, str]:
    found = {}
    for line in Path(path).read_text().splitlines():
        name, sep, rest = line.partition("==")
        if sep and not line.startswith("#"):
            found[name.strip()] = rest.split()[0]
    return found


def problems(wanted: dict[str, str], installed: dict[str, str | None]) -> list[str]:
    return [
        f"{name} {installed.get(name) or 'not installed'} != {version}"
        for name, version in wanted.items()
        if installed.get(name) != version
    ]


def installed_versions(names) -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for name in names:
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            found[name] = None
    return found


if __name__ == "__main__":
    wanted: dict[str, str] = {}
    for lock in sys.argv[1:]:
        wanted |= pins(lock)
    found = problems(wanted, installed_versions(wanted))
    for line in found:
        print(f"lock check: {line}", file=sys.stderr)
    print("lock check:", "FAILED" if found else f"all {len(wanted)} pins match")
    raise SystemExit(1 if found else 0)
PY
echo "installed $(grep -c '==' "$lock") pinned packages into $venv"
