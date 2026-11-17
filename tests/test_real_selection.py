"""The REAL profile collects only the modules that hold real tests.

The hash-locked REAL environment has no PyTorch. ``pytest -m real`` over the whole tree imports
every test module first, so a single module that needs PyTorch makes the profile fail before a
test runs; the first hosted release verification failed that way.
"""

import ast
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARK = re.compile(r"pytest\.mark\.real|pytestmark.*\breal\b")


def _real_modules():
    paths = [*ROOT.joinpath("tests").glob("*.py"), *ROOT.joinpath("research/tests").glob("*.py")]
    return sorted(p.relative_to(ROOT).as_posix() for p in paths if MARK.search(p.read_text()))


def _dry_run():
    out = subprocess.run(
        ["make", "-n", "verify-real"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return next(line for line in out.splitlines() if line.startswith("pytest -m real"))


def test_the_real_profile_collects_exactly_the_modules_that_hold_real_tests():
    command = _dry_run().split()
    assert command[:3] == ["pytest", "-m", "real"]
    assert sorted(command[3:]) == _real_modules()
    assert len(command) > 3


def test_no_module_the_real_profile_collects_needs_pytorch_at_import():
    for name in _real_modules():
        tree = ast.parse((ROOT / name).read_text())
        imported = {
            alias.name.split(".")[0]
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            (node.module or "").split(".")[0]
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
        }
        assert "torch" not in imported, name
