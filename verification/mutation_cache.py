"""Reuse cached mutation verdicts only for code and tests that did not change.

mutmut keeps one verdict per mutant and re-runs a mutant when the source of its function
changes. It does not notice a modified test file. This guard hashes the test files after
each run (``record``) and, before the next run (``prepare``), puts back to "not checked":

* killed mutants of every function covered by a modified or removed test file;
* every verdict that is not final (survived, timeout, suspicious, no tests, unchecked)
  when a test file was modified, removed or added, since the test may now reach it.

Fixture/support changes without attributed test-node IDs reopen every test-based
verdict. Root and research test files are hashed too. Pytest internal errors are
not treated as stable successful kills. Cached metadata may not alias external
files. Killed mutants of untouched functions under untouched tests, and verdicts of the type
checker, are kept. A run without a record (first run, fresh checkout) resets nothing:
mutmut then runs everything it has no verdict for. A release can still be certified from
a fresh ``mutants/`` directory.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from etl_benchmark.atomic import atomic_path
from verification import mutation_catalog
from verification.mutation_policy import _module, _relative

MUTANTS = "mutants"
HASHES = "test-hashes.json"
KILLED = {1}  # assertion failure; pytest internal errors are not stable successful kills
TYPED = {37}  # caught by the type checker, independent of the tests
FINAL = KILLED | TYPED
EXECUTION_VERSION = 1
EXECUTION_RECORD = "execution-context.json"
PENDING_EXECUTION = "execution-pending.json"


def function_of(key: str) -> str:
    return key.rsplit("__mutmut_", 1)[0]


def hash_tests(root: Path) -> dict[str, str]:
    paths = [root / "conftest.py"]
    for folder in (root / "tests", root / "research" / "tests"):
        paths.extend(folder.rglob("*.py"))
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
        if path.is_file()
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
    attributed = {test.split("::", 1)[0] for tests in tests_by_function.values() for test in tests}
    support_changed = changed - attributed
    support_added = {name for name in added if not Path(name).name.startswith("test_")}
    if support_changed or support_added:
        return [key for key, code in verdicts.items() if code not in TYPED]
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
    if cache.is_symlink() or not cache.resolve().is_relative_to(root.resolve()):
        raise ValueError("mutation cache must remain inside its owning root")
    metas = sorted(cache.rglob("*.meta")) if cache.is_dir() else []
    if any(
        path.is_symlink() or not path.resolve().is_relative_to(cache.resolve()) for path in metas
    ):
        raise ValueError("mutation cache metadata must not alias files outside the cache")
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


def _digest(data: Any) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _write_json(path: Path, data: dict) -> None:
    with atomic_path(path) as temporary:
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _globals_hash(source: str) -> str:
    class WithoutBodies(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            node.body = [ast.Pass()]
            return node

        visit_AsyncFunctionDef = visit_FunctionDef

    tree = WithoutBodies().visit(ast.parse(source))
    return hashlib.sha256(ast.dump(tree, annotate_fields=False).encode()).hexdigest()


def capture_context(
    root: Path, sources: list[str], *, runtime: dict, mutated_sources: list[str] | None = None
) -> dict:
    """Capture stable inputs, not an execution or a passing verification verdict.

    The controlling command supplies freshly observed runtime metadata. Source
    globals are bound separately because native function hashes do not cover them.
    """
    if (
        not isinstance(runtime, dict)
        or not isinstance(runtime.get("packages"), dict)
        or runtime["packages"].get("mutmut") != "3.8.0"
    ):
        raise ValueError("execution binding requires the inspected mutmut 3.8.0 format")
    if not isinstance(sources, list) or not sources or len(set(sources)) != len(sources):
        raise ValueError("execution sources must be explicit, unique and nonempty")
    scope = sources if mutated_sources is None else mutated_sources
    if (
        not isinstance(scope, list)
        or not scope
        or len(set(scope)) != len(scope)
        or set(scope) - set(sources)
    ):
        raise ValueError("mutated sources must belong to the captured source inventory")
    captured = {}
    for name in sorted(sources):
        path = _relative(name, root)
        if path.suffix != ".py" or not path.is_file():
            raise ValueError("execution sources must be existing Python files")
        source = path.read_text()
        captured[name] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "globals_sha256": _globals_hash(source),
            "functions": mutation_catalog._function_hashes(source),
        }
    candidates = [
        "pyproject.toml",
        "environment.yml",
        "verification/mutation_scope.json",
    ]
    candidates += [
        path.relative_to(root).as_posix()
        for path in (root / "verification/environment").glob("*")
        if path.is_file()
    ]
    dependencies = {
        name: hashlib.sha256(_relative(name, root).read_bytes()).hexdigest()
        for name in sorted(candidates)
        if (root / name).is_file()
    }
    return {
        "sources": captured,
        "mutation_scope": sorted(scope),
        "tests": hash_tests(root),
        "dependencies": dependencies,
        "runtime": deepcopy(runtime),
    }


def _execution_documents(root: Path, scope: list[str]) -> dict[Path, dict]:
    cache = root / MUTANTS
    if cache.is_symlink() or not cache.resolve().is_relative_to(root.resolve()):
        raise ValueError("mutation cache must remain inside its owning root")
    documents = {}
    for source in scope:
        relative = source + ".meta"
        path = cache / relative
        if not path.exists() and not path.is_symlink():
            continue
        data = mutation_catalog._read(cache, relative, {})
        if set(data) != mutation_catalog.META_FIELDS or any(
            not isinstance(value, dict) for value in data.values()
        ):
            raise ValueError("invalid native execution metadata")
        for key, code in data["exit_code_by_key"].items():
            mutation_catalog._identity(key, source)
            if code is not None and type(code) is not int:
                raise ValueError("invalid native execution verdict")
        documents[path] = data
    return documents


def _metadata_digest(data: dict) -> str:
    return _digest({name: data[name] for name in ("exit_code_by_key", "hash_by_function_name")})


def _statistics(root: Path) -> dict:
    path = root / MUTANTS / "mutmut-stats.json"
    data = mutation_catalog._read(root / MUTANTS, "mutmut-stats.json", {}) if path.exists() else {}
    result = {}
    for name in ("tests_by_mangled_function_name", "function_dependencies"):
        mapping = data.get(name, {})
        if not isinstance(mapping, dict) or any(
            not isinstance(key, str)
            or not isinstance(values, list)
            or any(not isinstance(value, str) for value in values)
            for key, values in mapping.items()
        ):
            raise ValueError("invalid native dependency or test map")
        result[name] = mapping
    return result


def _execution_proof(root: Path) -> dict | None:
    path = root / MUTANTS / EXECUTION_RECORD
    if not path.exists():
        return None
    proof = mutation_catalog._read(root / MUTANTS, EXECUTION_RECORD, {})
    payload = {key: value for key, value in proof.items() if key != "sha256"}
    if (
        type(proof.get("version")) is not int
        or proof["version"] != EXECUTION_VERSION
        or not isinstance(proof.get("context"), dict)
        or proof.get("sha256") != _digest(payload)
    ):
        raise ValueError("invalid execution proof")
    try:
        context = proof["context"]
        if (
            set(context) != {"runtime", "sources", "mutation_scope", "tests", "dependencies"}
            or not isinstance(context["runtime"], dict)
            or not isinstance(context["sources"], dict)
            or not context["sources"]
            or not isinstance(context["mutation_scope"], list)
            or not context["mutation_scope"]
            or set(context["mutation_scope"]) - set(context["sources"])
            or type(proof["native_exit_code"]) is not int
            or type(proof["settled"]) is not int
            or proof["settled"] < 0
        ):
            raise ValueError("invalid execution proof shape")
        mappings = [context["tests"], context["dependencies"], proof["metadata_sha256"]]
        for name, source in context["sources"].items():
            _relative(name, root)
            if set(source) != {"sha256", "globals_sha256", "functions"}:
                raise ValueError("invalid execution proof source")
            mappings.extend(
                [
                    {"source": source["sha256"], "globals": source["globals_sha256"]},
                    source["functions"],
                ]
            )
        for mapping in mappings:
            if not isinstance(mapping, dict) or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in mapping.items()
            ):
                raise ValueError("invalid execution proof mapping")
        for name in ("tests_by_mangled_function_name", "function_dependencies"):
            mapping = proof["statistics"][name]
            if not isinstance(mapping, dict) or any(
                not isinstance(key, str)
                or not isinstance(values, list)
                or any(not isinstance(value, str) for value in values)
                for key, values in mapping.items()
            ):
                raise ValueError("invalid execution proof statistics")
    except (KeyError, TypeError) as exc:
        raise ValueError("invalid execution proof shape") from exc
    return proof


def prepare_execution(
    root: Path, sources: list[str], *, runtime: dict, mutated_sources: list[str] | None = None
) -> dict:
    """Admit only bound cache entries; the caller must exclusively own this cache."""
    cache = root / MUTANTS
    if (cache / PENDING_EXECUTION).exists():
        raise ValueError("pending execution requires checking its process before recovery")
    context = capture_context(root, sources, runtime=runtime, mutated_sources=mutated_sources)
    previous = _execution_proof(root)
    documents = _execution_documents(root, context["mutation_scope"])
    verdicts = {
        key: code for data in documents.values() for key, code in data["exit_code_by_key"].items()
    }
    reset, reasons = set(), []
    if previous is None:
        reset.update(verdicts)
        reasons.append("no previous execution proof; bootstrap reconciliation")
    else:
        old = previous["context"]
        global_change = (
            context["runtime"] != old["runtime"]
            or context["dependencies"] != old["dependencies"]
            or {name: value["globals_sha256"] for name, value in context["sources"].items()}
            != {name: value["globals_sha256"] for name, value in old["sources"].items()}
        )
        partial = previous["native_exit_code"] != 0
        if global_change:
            reset.update(verdicts)
            reasons.append("runtime, dependency, source-global or inventory inputs changed")
        else:
            changed, support = set(), False
            for name, value in context["sources"].items():
                before, after = old["sources"][name]["functions"], value["functions"]
                functions = {
                    fn for fn in set(before) | set(after) if before.get(fn) != after.get(fn)
                }
                changed.update(_module(name) + "." + fn for fn in functions)
                support |= bool(functions) and name not in context["mutation_scope"]
            graph = previous["statistics"]["function_dependencies"]
            if support or (changed and (partial or not graph)):
                reset.update(verdicts)
                reasons.append("changed uninstrumented support or unavailable dependency graph")
            else:
                queue = list(changed)
                while queue:
                    for caller in graph.get(queue.pop(), []):
                        if caller not in changed:
                            changed.add(caller)
                            queue.append(caller)
                reset.update(key for key in verdicts if function_of(key) in changed)
                if changed:
                    reasons.append("changed source functions and transitive callers")
        if partial and old["tests"] != context["tests"]:
            reset.update(verdicts)
            reasons.append("test inputs changed after an incomplete native attempt")
        reset.update(
            keys_to_reset(
                old["tests"],
                context["tests"],
                previous["statistics"]["tests_by_mangled_function_name"],
                verdicts,
            )
        )
        for path, data in documents.items():
            name = path.relative_to(cache).as_posix()
            if previous["metadata_sha256"].get(name) != _metadata_digest(data):
                reset.update(data["exit_code_by_key"])
                reasons.append(f"unbound metadata change: {name}")
    cleared = 0
    for path, data in documents.items():
        changed = False
        for key in data["exit_code_by_key"]:
            if key in reset and data["exit_code_by_key"][key] is not None:
                data["exit_code_by_key"][key] = None
                cleared += 1
                changed = True
        if changed:
            _write_json(path, data)
    cache.mkdir(parents=True, exist_ok=True)
    _write_json(cache / PENDING_EXECUTION, {"version": EXECUTION_VERSION, "context": context})
    return {
        "kept": sum(code is not None for code in verdicts.values()) - cleared,
        "reset": cleared,
        "reasons": reasons,
        "context_sha256": _digest(context),
    }


def record_execution(
    root: Path,
    sources: list[str],
    *,
    runtime: dict,
    native_exit_code: int,
    mutated_sources: list[str] | None = None,
) -> dict:
    """Bind settled results only after the observed attempt and frozen-input check.

    A nonzero native exit remains explicit. This record is not a campaign PASS;
    incomplete catalogs and non-killed outcomes still fail the promotion policy.
    """
    cache = root / MUTANTS
    if not (cache / PENDING_EXECUTION).exists():
        raise ValueError("no pending execution to bind")
    pending = mutation_catalog._read(cache, PENDING_EXECUTION, {})
    context = capture_context(root, sources, runtime=runtime, mutated_sources=mutated_sources)
    if (
        type(pending.get("version")) is not int
        or pending["version"] != EXECUTION_VERSION
        or pending.get("context") != context
    ):
        raise ValueError("execution inputs changed during the attempt; do not promote")
    if type(native_exit_code) is not int:
        raise ValueError("native exit code must be an integer")
    documents = _execution_documents(root, context["mutation_scope"])
    settled = 0
    for path, data in documents.items():
        source = path.relative_to(cache).as_posix().removesuffix(".meta")
        functions = context["sources"][source]["functions"]
        for key, code in data["exit_code_by_key"].items():
            if code is None:
                continue
            local = function_of(key).removeprefix(_module(source) + ".")
            if (
                local not in functions
                or data["hash_by_function_name"].get(local) != functions[local]
            ):
                raise ValueError("settled native verdicts do not match current source")
            settled += 1
    proof = {
        "version": EXECUTION_VERSION,
        "context": context,
        "statistics": _statistics(root),
        "metadata_sha256": {
            path.relative_to(cache).as_posix(): _metadata_digest(data)
            for path, data in documents.items()
        },
        "native_exit_code": native_exit_code,
        "settled": settled,
        "captured_at": datetime.now(UTC).isoformat(),
    }
    proof["sha256"] = _digest(proof)
    _write_json(cache / EXECUTION_RECORD, proof)
    record(root)
    (cache / PENDING_EXECUTION).unlink()
    return proof


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
