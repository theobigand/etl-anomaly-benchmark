"""Reuse cached mutation verdicts only for code and tests that did not change.

mutmut keeps one verdict per mutant and re-runs a mutant when the source of its function
changes. It does not notice a modified test file. This guard hashes the test files after
each run (``record``) and, before the next run (``prepare``), puts back to "not checked":

* killed mutants of every function covered by a modified or removed test file;
* every verdict that is not final (survived, timeout, suspicious, no tests, unchecked)
  when a test file was modified, removed or added, since the test may now reach it.

Killed mutants of untouched functions under untouched tests, and verdicts of the type
checker, are kept. A run without a record (first run, fresh checkout) resets nothing:
mutmut then runs everything it has no verdict for. A release can still be certified from
a fresh ``mutants/`` directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

MUTANTS = "mutants"
HASHES = "test-hashes.json"
KILLED = {1, 3}  # mutmut: assertion failure, internal pytest error
TYPED = {37}  # caught by the type checker, independent of the tests
FINAL = KILLED | TYPED


def function_of(key: str) -> str:
    return key.rsplit("__mutmut_", 1)[0]


def hash_tests(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((root / "tests").rglob("*.py"))
    }


def keys_to_reset(
    old: Mapping[str, str] | None,
    new: Mapping[str, str],
    tests_by_function: Mapping[str, list[str]],
    verdicts: Mapping[str, int | None],
) -> list[str]:
    if old is None:
        return []
    modified = {name for name in old if name in new and old[name] != new[name]}
    removed = {name for name in old if name not in new}
    added = set(new) - set(old)
    changed = modified | removed
    if not changed and not added:
        return []
    prefixes = tuple(f"{name}::" for name in changed)
    reset = []
    for key, code in verdicts.items():
        if code in TYPED:
            continue
        if code in KILLED:
            covered = any(
                t.startswith(prefixes) for t in tests_by_function.get(function_of(key), ())
            )
            if covered:
                reset.append(key)
        else:
            reset.append(key)
    return reset


def _read(path: Path) -> Any:
    return json.loads(path.read_text())


def record(root: Path) -> Path:
    target = root / MUTANTS / HASHES
    target.write_text(json.dumps(hash_tests(root), indent=2, sort_keys=True) + "\n")
    return target


def prepare(root: Path) -> dict[str, Any]:
    cache = root / MUTANTS
    metas = sorted(cache.rglob("*.meta")) if cache.is_dir() else []
    documents = {path: _read(path) for path in metas}
    verdicts: dict[str, int | None] = {}
    for document in documents.values():
        verdicts.update(document["exit_code_by_key"])
    settled = sum(code is not None for code in verdicts.values())
    stats, baseline = cache / "mutmut-stats.json", cache / HASHES
    if not (stats.is_file() and baseline.is_file()):
        return {
            "kept": settled,
            "reset": 0,
            "modified_tests": [],
            "removed_tests": [],
            "added_tests": [],
        }
    old, new = _read(baseline), hash_tests(root)
    reset = set(keys_to_reset(old, new, _read(stats)["tests_by_mangled_function_name"], verdicts))
    cleared = 0
    for path, document in documents.items():
        touched = False
        for key in document["exit_code_by_key"]:
            if key in reset and document["exit_code_by_key"][key] is not None:
                document["exit_code_by_key"][key] = None
                cleared += 1
                touched = True
        if touched:
            path.write_text(json.dumps(document, indent=2) + "\n")
    return {
        "kept": settled - cleared,
        "reset": cleared,
        "modified_tests": sorted(n for n in old if n in new and old[n] != new[n]),
        "removed_tests": sorted(n for n in old if n not in new),
        "added_tests": sorted(set(new) - set(old)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=["prepare", "record"])
    args = parser.parse_args(argv)
    root = Path.cwd()
    if args.step == "record":
        record(root)
        return 0
    report = prepare(root)
    print(f"mutation cache: kept {report['kept']}, reset {report['reset']}")
    for label in ("modified_tests", "removed_tests", "added_tests"):
        if report[label]:
            print(f"  {label.replace('_', ' ')}: {', '.join(report[label])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
