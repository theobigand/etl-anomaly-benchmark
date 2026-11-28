#!/usr/bin/env bash
# Install an optional platform lock (ELT engine, dbt) from its recorded hash-pinned file: no
# dependency resolution and no source build, like install_locked.sh.
#
#   install_platform.sh <venv> elt|dbt
#
# elt  adds the DuckDB pin to an existing release environment
# dbt  builds a separate environment for dbt Core (ADR-0001, ADR-0005)
set -euo pipefail

venv=${1:?usage: install_platform.sh <venv> elt|dbt}
name=${2:?usage: install_platform.sh <venv> elt|dbt}
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
case "$name" in
  elt|dbt) lock=$root/verification/environment/linux-x86_64-py311.$name.lock.txt ;;
  *) echo "unknown platform lock: $name" >&2; exit 2 ;;
esac
[ "$(uname -s)-$(uname -m)" = "Linux-x86_64" ] || { echo "the lock is for Linux x86_64" >&2; exit 1; }
[ -x "$venv/bin/python" ] || python -m venv "$venv"
"$venv/bin/python" -m pip install --quiet --disable-pip-version-check --no-input --retries 10 \
  --timeout 60 --require-hashes --no-deps --only-binary=:all: -r "$lock"
