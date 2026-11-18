# ruff: noqa: E501
"""Static audit of the test suite: size, duplicated test bodies, reliance on private names, absolute paths, sleeps.

    python docs/thesis-remediation/evidence/test_suite_audit.py [OUTPUT.json]

Reads every `test_*.py` under tests/, research/tests/ and slides/tests/. It counts tests, groups tests whose bodies are
identical once names are erased, counts accesses to private (single underscore) attributes of the module under test per
file, and lists files that hard-code an absolute path or sleep. It changes nothing; timings come from `pytest --durations`.
"""

import ast
import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FOLDERS = ("tests", "research/tests", "slides/tests")
BASELINE = "e2576a0"


class Erase(ast.NodeTransformer):
    def visit_Name(self, node):
        return ast.copy_location(ast.Name(id="_", ctx=node.ctx), node)

    def visit_arg(self, node):
        node.arg = "_"
        return node


def tests_of(path: Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            yield node


def main() -> None:
    files = sorted(p for f in FOLDERS for p in (ROOT / f).rglob("test_*.py"))
    added = set(
        subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=A", BASELINE, "HEAD", "--", *FOLDERS],
            cwd=ROOT, capture_output=True, text=True,
        ).stdout.split()
    )  # fmt: skip
    groups: dict[str, list[str]] = defaultdict(list)
    per_file = {}
    total = 0
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text()
        count = 0
        for node in tests_of(path):
            count += 1
            body = ast.dump(Erase().visit(ast.Module(body=node.body, type_ignores=[])))
            if len(body) > 200:
                groups[hashlib.sha256(body.encode()).hexdigest()].append(f"{rel}::{node.name}")
        total += count
        per_file[rel] = {
            "tests": count,
            "added_since_baseline": rel in added,
            "private_attribute_accesses": len(re.findall(r"\b\w+\._[a-z]\w*", text)),
            "absolute_path": bool(re.search(r"[\"'](/Users/|/tmp/|/Volumes/)", text)),
            "sleeps": "time.sleep(" in text and "monkeypatch" not in text,
        }
    duplicates = [names for names in groups.values() if len(names) > 1]
    record = {
        "baseline": BASELINE,
        "test_files": len(files),
        "tests": total,
        "tests_in_files_added_since_baseline": sum(
            v["tests"] for v in per_file.values() if v["added_since_baseline"]
        ),
        "files_added_since_baseline": sum(
            1 for v in per_file.values() if v["added_since_baseline"]
        ),
        "duplicate_bodies": duplicates,
        "files_with_absolute_paths": [k for k, v in per_file.items() if v["absolute_path"]],
        "files_with_unmocked_sleep": [k for k, v in per_file.items() if v["sleeps"]],
        "most_private_attribute_accesses": sorted(
            ((k, v["private_attribute_accesses"], v["tests"]) for k, v in per_file.items()),
            key=lambda t: -t[1],
        )[:15],
        "per_file": per_file,
    }
    text = json.dumps(record, indent=1, sort_keys=True) + "\n"
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text)
    print(json.dumps({k: v for k, v in record.items() if k != "per_file"}, indent=1)[:4000])


if __name__ == "__main__":
    main()
