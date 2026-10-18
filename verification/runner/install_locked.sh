#!/usr/bin/env bash
# Build the REAL environment from the recorded Linux lock: Linux x86_64, CPython 3.11,
# hash-pinned wheels, no dependency resolution and no source build. pip, setuptools and
# wheel come with the standard-library venv and are not part of the lock.
set -euo pipefail

venv=${1:?usage: install_locked.sh <directory for the new environment>}
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
lock=$root/verification/environment/linux-x86_64-py311.lock.txt

[ "$(uname -s)-$(uname -m)" = "Linux-x86_64" ] || { echo "the lock is for Linux x86_64" >&2; exit 1; }
python -c 'import sys; sys.exit(sys.version_info[:2] != (3, 11))' \
  || { echo "the lock is for CPython 3.11" >&2; exit 1; }

python -m venv "$venv"
"$venv/bin/python" -m pip install --quiet --disable-pip-version-check --no-input \
  --require-hashes --no-deps --only-binary=:all: -r "$lock"
echo "installed $(grep -c '==' "$lock") pinned packages into $venv"
