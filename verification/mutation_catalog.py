"""Reconcile mutmut 3.8 native catalogs without asserting execution provenance.

The generation index is independent of verdict counts. Parsing it cannot prove
that execution is current: the promotion layer must validate that separately.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from verification.mutation_policy import _identity, _module, validate_policy

NATIVE_OUTCOMES = (
    "killed",
    "survived",
    "no_tests",
    "skipped",
    "suspicious",
    "timeout",
    "check_was_interrupted_by_user",
    "segfault",
)
META_FIELDS = {
    "exit_code_by_key",
    "hash_by_function_name",
    "type_check_error_by_key",
    "durations_by_key",
    "estimated_durations_by_key",
}
NATIVE_STATUS = {
    1: "killed",
    3: "killed",
    0: "survived",
    5: "no tests",
    33: "no tests",
    2: "check was interrupted by user",
    None: "not checked",
    34: "skipped",
    35: "suspicious",
    36: "timeout",
    37: "caught by type check",
    -24: "timeout",
    24: "timeout",
    152: "timeout",
    255: "timeout",
    -11: "segfault",
    -9: "segfault",
}


def _pairs(items: list[tuple]) -> dict:
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"duplicate native JSON field: {key}")
        result[key] = value
    return result


def _read(cache: Path, relative: str, artifacts: dict) -> dict:
    path = cache / relative
    if path.is_symlink() or not path.resolve().is_relative_to(cache.resolve()):
        raise ValueError("native catalog paths must stay inside the cache")
    try:
        content = path.read_bytes()
    except OSError as error:
        raise ValueError(f"native catalog file unavailable: {relative}") from error
    data = json.loads(content, object_pairs_hook=_pairs)
    if not isinstance(data, dict):
        raise ValueError("native catalog files must be JSON objects")
    artifacts[relative] = hashlib.sha256(content).hexdigest()
    return data


def _index(data: dict, path: str) -> set[str]:
    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("unsupported native generation index version")
    spans = data.get("spans")
    if not isinstance(spans, dict):
        raise ValueError("native generation index must record spans")
    keys = set()
    for local, span in spans.items():
        if (
            not isinstance(span, list)
            or len(span) != 2
            or any(type(value) is not int or value <= 0 for value in span)
            or span[1] < span[0]
        ):
            raise ValueError("invalid native source span")
        if not re.fullmatch(r".+__mutmut_(?:orig|[1-9][0-9]*)", local):
            raise ValueError("unknown native generation index identity")
        if local.endswith("__mutmut_orig"):
            continue
        key = _module(path) + "." + local
        _identity(key, path)
        keys.add(key)
    return keys


def _listing(text: str) -> dict:
    if not isinstance(text, str):
        raise ValueError("native result listing must be text")
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        key, separator, outcome = line.strip().partition(": ")
        if not separator or key in result:
            raise ValueError("invalid or duplicated native result listing")
        result[key] = outcome
    return result


def _function_hashes(source: str) -> dict[str, str]:
    """Independent check of mutmut 3.8's function-AST fingerprint format.

    This binds generated functions, not module globals or past test execution.
    Full-file and execution-context binding remains a promotion requirement.
    """
    hashes = {}

    def visit(nodes: list[ast.stmt], owners: tuple[str, ...]) -> None:
        for node in nodes:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                prefix = "xǁ" + ".".join(owners) + "ǁ" if owners else "x_"
                hashes[prefix + node.name] = hashlib.sha256(
                    ast.dump(node, annotate_fields=False).encode()
                ).hexdigest()[:12]
            elif isinstance(node, ast.ClassDef):
                visit(node.body, (*owners, node.name))

    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise ValueError("current source is not parseable") from error
    visit(tree.body, ())
    return hashes


def read_native(policy: dict, root: Path, cache: Path, stats: dict, listing: str) -> dict:
    """Require agreement of generation index, verdict metadata, counts and listing.

    Native pytest-internal-error code 3 and unknown exit codes are error outcomes,
    never successful kills. Preserve native counts separately for reconciliation.
    """
    validate_policy(policy, root)
    if (
        not isinstance(stats, dict)
        or set(stats) != {"total", *NATIVE_OUTCOMES}
        or any(type(value) is not int or value < 0 for value in stats.values())
    ):
        raise ValueError("invalid native mutation statistics")
    catalog: dict[str, list[str]] = {}
    artifacts: dict[str, str] = {}
    records, native, missing = [], {}, []
    for path, unit in sorted(policy["units"].items()):
        catalog[path] = []
        meta_path = cache / f"{path}.meta"
        if not meta_path.exists() and not meta_path.is_symlink():
            if "no_mutants" not in unit:
                missing.append(path)
            continue
        meta = _read(cache, f"{path}.meta", artifacts)
        if set(meta) != META_FIELDS or any(not isinstance(value, dict) for value in meta.values()):
            raise ValueError("invalid native metadata structure")
        verdicts = meta["exit_code_by_key"]
        generated = _index(_read(cache, f"{path}.spans", artifacts), path)
        if set(verdicts) != generated:
            raise ValueError("verdict population differs from native generation index")
        functions = {
            key.rsplit("__mutmut_", 1)[0].removeprefix(_module(path) + ".") for key in generated
        }
        hashes = meta["hash_by_function_name"]
        if set(hashes) != functions or any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{12}", value)
            for value in hashes.values()
        ):
            raise ValueError("native function hashes do not bind the generated catalog")
        if "no_mutants" in unit and verdicts:
            raise ValueError("technical no-mutant scope received mutants")
        current = _function_hashes((root / path).read_text())
        if any(current.get(name) != value for name, value in hashes.items()):
            raise ValueError("native function hashes differ from current source")
        catalog[path] = sorted(generated)
        for key, code in sorted(verdicts.items()):
            if code is not None and type(code) is not int:
                raise ValueError("native exit codes must be integers or null")
            native_status = NATIVE_STATUS.get(code, "suspicious")
            native[key] = native_status
            outcome = "error" if code == 3 or code not in NATIVE_STATUS else native_status
            records.append({"id": key, "path": path, "outcome": outcome})
    if _listing(listing) != native:
        raise ValueError("full native listing differs from verdict metadata")
    counts = Counter(value.replace(" ", "_") for value in native.values())
    expected = {"total": len(native), **{name: counts[name] for name in NATIVE_OUTCOMES}}
    if stats != expected:
        raise ValueError("native statistics differ from catalog outcomes")
    return {
        "catalog": catalog,
        "records": records,
        "missing": missing,
        "native_stats": dict(stats),
        "artifacts": artifacts,
        "execution_provenance_verified": False,
    }
