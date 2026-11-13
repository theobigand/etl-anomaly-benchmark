"""Textual difference of every surviving or timed-out mutant of one unit.

    python docs/thesis-remediation/evidence/mutdiff.py MUTANTS_DIR path/to/unit.py

mutmut writes the original and every mutant of a function into the generated copy of the unit under
the mutants directory. This reads that copy and the unit's verdict file; it needs no running mutmut and
decides nothing. The generated copy is a mutated source only right after that unit was run (mutmut rewrites it for the
next unit), so dump the differences straight after each run.
"""

import ast
import difflib
import json
import sys
from pathlib import Path

SURVIVED, TIMEOUT = 0, -24


def survivors(root: Path, path: str) -> list[dict]:
    """One record per survived or timed-out mutant: its key, verdict code and the changed lines."""
    verdicts = json.loads((root / f"{path}.meta").read_text())["exit_code_by_key"]
    source = (root / path).read_text()
    lines = source.splitlines()
    functions = {
        node.name: node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }

    def body(name: str) -> list[str]:
        node = functions[name]
        text = lines[node.lineno - 1 : node.end_lineno]
        text[0] = text[0].replace(name, "FUNCTION", 1)
        return text

    out = []
    for key, code in verdicts.items():
        if code not in (SURVIVED, TIMEOUT):
            continue
        mangled = key.rsplit(".", 1)[-1]
        function = mangled.split("__mutmut_")[0]
        original = f"{function}__mutmut_orig"
        if original not in functions or mangled not in functions:
            out.append({"key": key, "code": code, "diff": None})
            continue
        changed = [
            line
            for line in difflib.unified_diff(body(original), body(mangled), lineterm="", n=0)
            if not line.startswith(("---", "+++", "@@"))
        ]
        out.append({"key": key, "code": code, "diff": changed})
    return out


def main() -> None:
    root, path = Path(sys.argv[1]), sys.argv[2]
    for item in survivors(root, path):
        label = item["key"].rsplit(".", 1)[-1] + (" [timeout]" if item["code"] == TIMEOUT else "")
        print(f"## {label}" + ("" if item["diff"] is not None else " (no source)"))
        for line in item["diff"] or []:
            print(line)


if __name__ == "__main__":
    main()
