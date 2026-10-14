"""Rules that stop a green report from hiding a weakened check.

Each rule is a small function over source text, tried on offending snippets
first so that the rule itself is known to fail, then applied to the repository.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.protocol

ROOT = Path(__file__).resolve().parents[1]
TEST_FILES = sorted((ROOT / "tests").glob("*.py"))
PRODUCTION_FILES = sorted([*(ROOT / "src").rglob("*.py"), *(ROOT / "experiments").glob("*.py")])

# Scientific computation that tests must run for real rather than replace.
LIBRARY_ROOTS = {"sklearn", "pyod", "scipy", "numpy", "np", "pandas", "pd", "gx"}
PROTECTED_FUNCTIONS = {"compute_metrics", "roc_auc_score", "average_precision_score"}
MOCK_MODULES = {"unittest.mock", "mock"}

# Behaviour areas that must keep at least one dedicated test module.
REQUIRED_TEST_MODULES = {
    "split integrity": "test_split.py",
    "leakage and held-out isolation": "test_scientific_contracts.py",
    "metric definitions": "test_metric_contract.py",
    "detector protocol": "test_detector_protocol.py",
    "dataset contract": "test_dataset_contract.py",
    "pipeline persistence": "test_pipeline_integration.py",
    "synthetic ground truth": "test_synthetic_contracts.py",
    "artifact lineage": "test_artifact_lineage.py",
    "temporal protocol": "test_temporal_protocol.py",
}


def _is_real_marker(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "real"


def _marks_real(decorators: list[ast.expr]) -> bool:
    return any(_is_real_marker(getattr(d, "func", d)) for d in decorators)


def _module_is_real(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
        ):
            return any(_is_real_marker(n) for n in ast.walk(node.value))
    return False


def skip_violations(source: str) -> list[str]:
    """Skips and expected failures are allowed only in tests marked ``real``."""
    tree = ast.parse(source)
    module_real = _module_is_real(tree)
    found = []
    forbidden = {"skip", "skipif", "xfail", "importorskip"}

    def visit(node: ast.AST, real: bool) -> None:
        for child in ast.iter_child_nodes(node):
            child_real = real
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                child_real = real or _marks_real(child.decorator_list)
                for decorator in child.decorator_list:
                    target = getattr(decorator, "func", decorator)
                    if (
                        isinstance(target, ast.Attribute)
                        and target.attr in forbidden
                        and not child_real
                    ):
                        found.append(f"line {decorator.lineno}: {target.attr}")
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr in forbidden
                and not child_real
            ):
                found.append(f"line {child.lineno}: {child.func.attr}")
            visit(child, child_real)

    visit(tree, module_real)
    return found


def suppressed_error_violations(source: str) -> list[str]:
    """Bare handlers, handlers that only pass, and ``contextlib.suppress``."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ExceptHandler):
            only_noop = all(
                isinstance(stmt, ast.Pass | ast.Continue)
                or (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))
                for stmt in node.body
            )
            if node.type is None or only_noop:
                found.append(f"line {node.lineno}: handler hides the error")
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            if name == "suppress":
                found.append(f"line {node.lineno}: suppress()")
    return found


def coverage_exclusion_violations(pyproject_text: str, sources: dict[str, str]) -> list[str]:
    found = []
    coverage = tomllib.loads(pyproject_text).get("tool", {}).get("coverage", {})
    for section, body in coverage.items():
        for key in ("omit", "exclude_lines", "exclude_also"):
            if key in body:
                found.append(f"[tool.coverage.{section}] sets {key}")
    for name, text in sources.items():
        if re.search(r"#\s*pragma:\s*no (cover|branch)", text):
            found.append(f"{name}: coverage pragma")
    return found


def mock_violations(source: str) -> list[str]:
    """Tests may swap seams of the project, never the libraries that do the maths."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import) and any(a.name in MOCK_MODULES for a in node.names):
            found.append(f"line {node.lineno}: imports a mock library")
        if isinstance(node, ast.ImportFrom) and node.module in MOCK_MODULES:
            found.append(f"line {node.lineno}: imports a mock library")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"setattr", "setitem"}
            and node.args
        ):
            target = node.args[0]
            root = target
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in LIBRARY_ROOTS:
                found.append(f"line {node.lineno}: patches {root.id}")
            name = node.args[1] if len(node.args) > 1 else None
            if isinstance(name, ast.Constant) and name.value in PROTECTED_FUNCTIONS:
                found.append(f"line {node.lineno}: patches {name.value}")
    return found


def test_skips_are_confined_to_real_data_tests():
    assert skip_violations("import pytest\n\ndef test_a():\n    pytest.skip('later')\n")
    assert skip_violations("import pytest\n\n@pytest.mark.xfail\ndef test_a():\n    pass\n")
    assert skip_violations(
        "import pytest\n\n@pytest.mark.skipif(True, reason='x')\ndef test_a(): ...\n"
    )
    allowed = "import pytest\n\n@pytest.mark.real\ndef test_a():\n    pytest.skip('absent data')\n"
    assert not skip_violations(allowed)
    module = (
        "import pytest\n\npytestmark = pytest.mark.real\n\ndef test_a():\n    pytest.skip('x')\n"
    )
    assert not skip_violations(module)
    for path in TEST_FILES:
        assert not skip_violations(path.read_text()), path.name


def test_production_code_does_not_swallow_errors():
    assert suppressed_error_violations("try:\n    f()\nexcept ValueError:\n    pass\n")
    assert suppressed_error_violations("try:\n    f()\nexcept:\n    raise\n")
    assert suppressed_error_violations(
        "import contextlib\nwith contextlib.suppress(OSError):\n    f()\n"
    )
    assert not suppressed_error_violations(
        "try:\n    f()\nexcept ValueError as exc:\n    raise X from exc\n"
    )
    for path in PRODUCTION_FILES:
        assert not suppressed_error_violations(path.read_text()), path.name


def test_coverage_has_no_exclusions():
    assert coverage_exclusion_violations('[tool.coverage.run]\nomit = ["a.py"]\n', {})
    assert coverage_exclusion_violations("[tool.coverage.report]\nexclude_lines = ['x']\n", {})
    assert coverage_exclusion_violations("", {"a.py": "x = 1  # pragma: no cover\n"})
    assert not coverage_exclusion_violations('[tool.coverage.run]\npatch = ["subprocess"]\n', {})
    assert not (ROOT / ".coveragerc").exists()
    sources = {path.name: path.read_text() for path in PRODUCTION_FILES}
    assert not coverage_exclusion_violations((ROOT / "pyproject.toml").read_text(), sources)


def test_tests_do_not_replace_the_scientific_libraries():
    assert mock_violations("from unittest import mock\nfrom unittest.mock import patch\n")
    assert mock_violations(
        "def t(monkeypatch):\n    monkeypatch.setattr(sklearn.metrics, 'f', g)\n"
    )
    assert mock_violations(
        "def t(monkeypatch):\n    monkeypatch.setattr(m, 'compute_metrics', g)\n"
    )
    assert not mock_violations(
        "def t(monkeypatch):\n    monkeypatch.setattr(run_benchmark, 'all_detectors', g)\n"
    )
    for path in TEST_FILES:
        if path.name != Path(__file__).name:
            assert not mock_violations(path.read_text()), path.name


def test_mandatory_scientific_test_modules_still_exist_and_contain_tests():
    for area, name in REQUIRED_TEST_MODULES.items():
        path = ROOT / "tests" / name
        assert path.is_file(), f"{area}: {name} is missing"
        tree = ast.parse(path.read_text())
        count = sum(
            isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
            for node in ast.walk(tree)
        )
        assert count >= 1, f"{area}: {name} has no test"
