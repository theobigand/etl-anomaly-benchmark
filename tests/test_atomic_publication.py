"""Scientific CSVs, tables, split archives and figures are published whole or not at all."""

import ast
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from etl_benchmark import atomic

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.end_to_end

# -- the publication primitive ------------------------------------------------


def _hidden(directory):
    return [p.name for p in directory.iterdir() if p.name.startswith(".")]


def test_a_published_file_appears_complete(tmp_path):
    target = tmp_path / "out" / "table.csv"
    with atomic.atomic_path(target) as partial:
        assert partial != target and partial.parent == target.parent
        partial.write_text("a,b\n1,2\n")
        assert not target.exists()
    assert target.read_text() == "a,b\n1,2\n"
    assert _hidden(target.parent) == []


def test_a_failed_write_leaves_the_previous_file_untouched_and_no_partial_file(tmp_path):
    target = tmp_path / "table.csv"
    target.write_text("old\n")
    with pytest.raises(OSError, match="disk full"), atomic.atomic_path(target) as partial:
        partial.write_text("half")
        raise OSError("disk full")
    assert target.read_text() == "old\n"
    assert _hidden(tmp_path) == []


def test_a_failed_first_write_creates_nothing(tmp_path):
    target = tmp_path / "new.csv"
    with pytest.raises(RuntimeError), atomic.atomic_path(target) as partial:
        partial.write_text("half")
        raise RuntimeError("boom")
    assert not target.exists() and _hidden(tmp_path) == []


def test_an_interrupt_is_not_swallowed_and_cleans_up(tmp_path):
    target = tmp_path / "t.csv"
    with pytest.raises(KeyboardInterrupt), atomic.atomic_path(target) as partial:
        partial.write_text("half")
        raise KeyboardInterrupt
    assert not target.exists() and _hidden(tmp_path) == []


def test_a_failed_rename_keeps_the_previous_file(tmp_path, monkeypatch):
    target = tmp_path / "t.csv"
    target.write_text("old")

    def refuse(source, destination):
        raise OSError("rename refused")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError, match="rename refused"), atomic.atomic_path(target) as partial:
        partial.write_text("new")
    monkeypatch.undo()
    assert target.read_text() == "old" and _hidden(tmp_path) == []


def test_a_writer_that_produces_nothing_is_refused(tmp_path):
    target = tmp_path / "t.csv"
    with pytest.raises(FileNotFoundError), atomic.atomic_path(target):
        pass
    assert not target.exists()


def test_an_empty_publication_is_refused(tmp_path):
    target = tmp_path / "t.csv"
    target.write_text("old")
    with pytest.raises(ValueError, match="empty"), atomic.atomic_path(target) as partial:
        partial.write_text("")
    assert target.read_text() == "old" and _hidden(tmp_path) == []


def test_the_partial_name_keeps_the_extension_so_formats_are_inferred(tmp_path):
    with atomic.atomic_path(tmp_path / "figure.png") as partial:
        assert partial.suffix == ".png"
        partial.write_bytes(b"x")


def test_text_and_bytes_helpers(tmp_path):
    atomic.write_text(tmp_path / "a.md", "hello")
    atomic.write_bytes(tmp_path / "b.bin", b"\x00\x01")
    assert (tmp_path / "a.md").read_text() == "hello"
    assert (tmp_path / "b.bin").read_bytes() == b"\x00\x01"


def test_the_load_stage_publishes_atomically(tmp_path, monkeypatch):
    from etl_benchmark import load

    frame = pd.DataFrame({"a": [1, 2]})
    out = load.write_csv(frame, tmp_path / "deep" / "x.csv")
    assert pd.read_csv(out).a.tolist() == [1, 2]
    monkeypatch.setattr(pd.DataFrame, "to_csv", _broken("csv"))
    (tmp_path / "keep.csv").write_text("old")
    with pytest.raises(OSError, match="disk full"):
        load.write_csv(frame, tmp_path / "keep.csv")
    assert (tmp_path / "keep.csv").read_text() == "old" and _hidden(tmp_path) == []


# -- no direct write in the scientific code -----------------------------------

DIRECT = {"to_csv", "savefig", "write_text", "write_bytes"}


def _scientific_sources():
    return sorted((ROOT / "src" / "etl_benchmark").glob("*.py")) + sorted(
        (ROOT / "experiments").glob("*.py")
    )


def _unguarded_writes(path):
    tree = ast.parse(path.read_text())
    guarded = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.With) and any(
            isinstance(item.context_expr, ast.Call)
            and getattr(item.context_expr.func, "attr", getattr(item.context_expr.func, "id", ""))
            == "atomic_path"
            for item in node.items
        ):
            guarded.update(id(child) for child in ast.walk(node))
    return [
        f"{path.name}:{node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in DIRECT
        and id(node) not in guarded
    ]


def test_every_result_write_goes_through_the_atomic_helper():
    offenders = []
    for path in _scientific_sources():
        if path.name == "atomic.py":
            continue
        offenders += _unguarded_writes(path)
    assert offenders == []


# -- failure injection in the experiment entry points -------------------------

DRIVER = """
import runpy, sys
from pathlib import Path
import pandas as pd
from matplotlib.figure import Figure

kind, script = sys.argv[1], sys.argv[2]
sys.argv = [script, *sys.argv[3:]]
sys.path.insert(0, str(Path(script).parent))

def broken(target, *args, **kwargs):
    with open(target, "wb") as stream:
        stream.write(b"half")
    raise OSError("disk full")

if kind == "csv":
    pd.DataFrame.to_csv = lambda self, path=None, *a, **k: broken(path)
elif kind == "figure":
    Figure.savefig = lambda self, path, *a, **k: broken(path)
elif kind == "bytes":
    Path.write_bytes = lambda self, *a, **k: broken(self)
elif kind == "text":
    Path.write_text = lambda self, *a, **k: broken(self)
runpy.run_path(script, run_name="__main__")
"""


def _broken(kind):
    def writer(self, path=None, *args, **kwargs):
        Path(path).write_bytes(b"half")
        raise OSError("disk full")

    return writer


def _run_broken(kind, script, *args):
    return subprocess.run(
        [sys.executable, "-c", DRIVER, kind, str(ROOT / "experiments" / script), *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _toy_csv(path):
    values = np.arange(200, dtype=float)
    pd.DataFrame({"V1": values, "Class": [0] * 180 + [1] * 20}).to_csv(path, index=False)


CASES = {
    "benchmark-csv": ("csv", "run_benchmark.py"),
    "benchmark-table": ("text", "run_benchmark.py"),
    "benchmark-splits": ("bytes", "run_benchmark.py"),
    "generate-csv": ("csv", "generate_synthetic.py"),
    "synthetic-csv": ("csv", "run_synthetic_benchmark.py"),
    "synthetic-figure": ("figure", "run_synthetic_benchmark.py"),
    "severity-csv": ("csv", "run_severity.py"),
    "severity-figure": ("figure", "run_severity.py"),
    "curves-figure": ("figure", "run_curves.py"),
}


def _arguments(name, tmp_path, figure):
    out = tmp_path / "out"
    if name.startswith("benchmark"):
        csv = tmp_path / "toy.csv"
        _toy_csv(csv)
        return [
            *("--dataset", "credit_card", "--csv", csv, "--detectors", "zscore", "--seeds", 1),
            *("--results-dir", out),
        ]
    if name.startswith("generate"):
        return ["--rows", 300, "--output", tmp_path / "out" / "synthetic.csv"]
    if name.startswith("synthetic"):
        return [*("--rows", 300, "--seeds", 1), *("--results-dir", out, "--figure", figure)]
    if name.startswith("severity"):
        sev = ("--rows", 300, "--severities", 1, "--seeds", 1)
        return [*sev, *("--results-dir", out, "--figure", figure)]
    return [
        *("--datasets", "synthetic", "--rows", 300, "--seed", 1),
        *("--results-dir", out, "--figure", figure),
    ]


@pytest.mark.parametrize("name", sorted(CASES))
def test_an_interrupted_write_leaves_no_partial_result_and_no_run_record(tmp_path, name):
    kind, script = CASES[name]
    figure = tmp_path / "figure.png"
    figure.write_bytes(b"PREVIOUS-FIGURE")
    done = _run_broken(kind, script, *_arguments(name, tmp_path, figure))
    assert done.returncode != 0 and "disk full" in done.stderr
    out = tmp_path / "out"
    produced = [p for p in out.rglob("*") if p.is_file()] if out.exists() else []
    assert not [p for p in produced if p.name.startswith("run_")], "a record marks a finished run"
    assert not [p for p in produced if p.name.startswith(".")], "a partial file was left behind"
    for path in produced + [figure]:
        assert b"half" not in path.read_bytes(), path
    assert figure.read_bytes() == b"PREVIOUS-FIGURE"
