# ruff: noqa: E501
"""Collect the surviving, timed-out and incomplete mutants of focused mutmut runs, with their diffs and bindings.

    python docs/thesis-remediation/evidence/collect_survivors.py OUT.json research/a.py research/b.py ...

Reads mutants/<path>.meta (written by `make mutation-focus`), asks `mutmut show` for each diff, and records the
source SHA-256, the catalog digest (verification.mutation_policy.catalog_digest) and the raw counts. It reads results
only; it creates no owner decision and edits no policy file.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from verification import mutation_policy  # noqa: E402

STATUS = {1: "killed", 0: "survived", -24: "timeout", None: "not_run"}


def show(key: str) -> str:
    out = subprocess.run(
        [sys.executable, "-m", "mutmut", "show", key], cwd=ROOT, capture_output=True, text=True
    )
    text = out.stdout
    return "\n".join(text.splitlines()[1:]) if text.startswith("#") else text


def collect(path: str) -> dict:
    meta = json.loads((ROOT / "mutants" / f"{path}.meta").read_text())["exit_code_by_key"]
    keys = sorted(meta)
    counts: dict[str, int] = {}
    survivors = []
    for key, code in sorted(meta.items()):
        status = STATUS.get(code, f"exit_{code}")
        counts[status] = counts.get(status, 0) + 1
        if status not in ("killed",):
            survivors.append({"id": key, "outcome": status, "diff": show(key)})
    source = (ROOT / path).read_bytes()
    return {
        "path": path,
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "catalog_sha256": mutation_policy.catalog_digest(keys),
        "counts": counts,
        "total": len(keys),
        "survivors": survivors,
    }


if __name__ == "__main__":
    out, *paths = sys.argv[1:]
    from importlib.metadata import version

    document = {
        "environment": {name: version(name) for name in ("pandas", "numpy", "mutmut")},
        "modules": [collect(p) for p in paths],
    }
    Path(out).write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
