"""The mutation scope must cover every eligible module, whatever the score."""

import json
from pathlib import Path

import pytest

from verification import mutation_scope

ROOT = Path(__file__).resolve().parents[1]


def _tree(tmp_path, files=("src/pkg/a.py", "src/pkg/b.py", "scripts/run.py"), exclusions=None):
    for name in files:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x = 1\n")
    (tmp_path / "src/pkg/__pycache__").mkdir(exist_ok=True)
    (tmp_path / "src/pkg/__pycache__/junk.py").write_text("")
    config = {
        "version": 2,
        "roots": ["src/pkg", "scripts"],
        "exclusions": exclusions or {},
    }
    path = tmp_path / "scope.json"
    path.write_text(json.dumps(config))
    return path


def test_the_inventory_lists_every_python_file_below_the_roots(tmp_path):
    config = mutation_scope.load(_tree(tmp_path))
    assert mutation_scope.inventory(tmp_path, config) == [
        "scripts/run.py",
        "src/pkg/a.py",
        "src/pkg/b.py",
    ]


def test_justified_exclusions_leave_the_inventory_and_are_listed(tmp_path):
    config = mutation_scope.load(_tree(tmp_path, exclusions={"src/pkg/b.py": "constants only"}))
    assert mutation_scope.inventory(tmp_path, config) == ["scripts/run.py", "src/pkg/a.py"]


def test_patterns_resolve_to_the_files_they_match(tmp_path):
    _tree(tmp_path)
    assert mutation_scope.resolve(["src/pkg/*.py", "scripts/*.py"], tmp_path) == [
        "scripts/run.py",
        "src/pkg/a.py",
        "src/pkg/b.py",
    ]


def test_a_complete_scope_has_no_problem(tmp_path):
    config = mutation_scope.load(_tree(tmp_path))
    assert mutation_scope.check(["src/pkg/*.py", "scripts/*.py"], tmp_path, config) == []


def test_a_shrunk_scope_is_reported_by_file(tmp_path):
    config = mutation_scope.load(_tree(tmp_path))
    problems = mutation_scope.check(["src/pkg/a.py"], tmp_path, config)
    assert any("src/pkg/b.py" in p and "not mutated" in p for p in problems)
    assert any("scripts/run.py" in p for p in problems)


def test_a_new_module_fails_until_it_is_included_or_justified(tmp_path):
    config = mutation_scope.load(_tree(tmp_path))
    patterns = ["src/pkg/a.py", "src/pkg/b.py", "scripts/run.py"]
    assert mutation_scope.check(patterns, tmp_path, config) == []
    (tmp_path / "scripts/new_result.py").write_text("x = 1\n")
    problems = mutation_scope.check(patterns, tmp_path, config)
    assert any("scripts/new_result.py" in p for p in problems)


def test_an_exclusion_needs_a_reason_and_an_existing_file(tmp_path):
    config = mutation_scope.load(_tree(tmp_path, exclusions={"src/pkg/b.py": " "}))
    assert any("reason" in p for p in mutation_scope.check(["*"], tmp_path, config))
    config = mutation_scope.load(_tree(tmp_path, exclusions={"src/pkg/gone.py": "old"}))
    assert any(
        "gone.py" in p and "does not exist" in p for p in mutation_scope.check([], tmp_path, config)
    )


def test_a_scope_naming_an_excluded_or_unknown_file_is_reported(tmp_path):
    config = mutation_scope.load(_tree(tmp_path, exclusions={"src/pkg/b.py": "constants"}))
    problems = mutation_scope.check(["src/pkg/*.py", "scripts/*.py"], tmp_path, config)
    assert any("src/pkg/b.py" in p and "excluded" in p for p in problems)
    problems = mutation_scope.check(["src/pkg/a.py", "src/pkg/ghost.py"], tmp_path, config)
    assert any("ghost.py" in p and "matches no file" in p for p in problems)


def test_the_load_rejects_an_unknown_version(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"version": 9, "roots": [], "exclusions": {}}))
    with pytest.raises(ValueError, match="version"):
        mutation_scope.load(path)


def test_the_load_rejects_the_superseded_two_root_scope_version(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"version": 1, "roots": [], "exclusions": {}}))
    with pytest.raises(ValueError, match="version"):
        mutation_scope.load(path)


def test_inventory_excludes_test_modules_below_a_production_root(tmp_path):
    config = mutation_scope.load(
        _tree(
            tmp_path,
            files=("src/pkg/a.py", "src/pkg/tests/test_a.py", "scripts/run.py"),
        )
    )
    assert mutation_scope.inventory(tmp_path, config) == ["scripts/run.py", "src/pkg/a.py"]


def test_mutants_are_mapped_back_to_their_source_files(tmp_path):
    _tree(tmp_path, files=("src/pkg/a.py", "src/pkg/q/__init__.py", "scripts/run.py"))
    text = (
        "    pkg.a.x_f__mutmut_1: killed\n"
        "    pkg.q.x_g__mutmut_2: survived\n"
        "    scripts.run.xǁCǁm__mutmut_3: killed\n"
        "noise\n"
    )
    found = mutation_scope.mutated_files(text, tmp_path, ["src", "."])
    assert found == ["scripts/run.py", "src/pkg/a.py", "src/pkg/q/__init__.py"]


def test_the_repository_mutation_scope_equals_its_eligible_inventory():
    config = mutation_scope.load()
    patterns = mutation_scope.configured_patterns(ROOT / "pyproject.toml")
    exclude = mutation_scope.configured_exclusions(ROOT / "pyproject.toml")
    assert mutation_scope.check(patterns, ROOT, config, exclude) == []
    # without the configured exclusion, fnmatch pulls the research test files into the scope
    assert any(
        "research/tests/" in p and "outside the eligible roots" in p
        for p in mutation_scope.check(patterns, ROOT, config)
    )


def test_every_recorded_exclusion_of_this_repository_has_a_reason():
    config = mutation_scope.load()
    assert config["exclusions"] == {}
    assert set(config["no_mutants"]) == {
        "src/etl_benchmark/__init__.py",
        "src/etl_benchmark/config.py",
        "src/etl_benchmark/quality/__init__.py",
    }
    assert all(reason.strip() for reason in config["exclusions"].values())
    assert all(reason.strip() for reason in config["no_mutants"].values())


def test_files_that_received_no_mutant_must_be_declared(tmp_path):
    config = mutation_scope.load(_tree(tmp_path))
    scope = ["src/pkg/a.py", "src/pkg/b.py", "scripts/run.py"]
    assert mutation_scope.check_mutated(scope, scope, config) == []
    problems = mutation_scope.check_mutated(scope, scope[:2], config)
    assert any("scripts/run.py" in p and "no mutant" in p for p in problems)
    config["no_mutants"] = {"scripts/run.py": "re-exports"}
    assert mutation_scope.check_mutated(scope, scope[:2], config) == []
    problems = mutation_scope.check_mutated(scope[:2], scope, config)
    assert any("scripts/run.py" in p and "outside" in p for p in problems)


def test_a_recorded_deep_scope_is_compared_with_the_current_tree(tmp_path):
    config = mutation_scope.load(_tree(tmp_path))
    full = ["scripts/run.py", "src/pkg/a.py", "src/pkg/b.py"]
    result = {"scope_files": full, "mutated_files": full}
    assert mutation_scope.check_evidence(result, full, config) == []
    shrunk = {"scope_files": full[:2], "mutated_files": full[:2]}
    problems = mutation_scope.check_evidence(shrunk, full, config)
    assert problems == ["src/pkg/b.py is eligible but not mutated"]
    extra = {"scope_files": [*full, "src/pkg/z.py"], "mutated_files": full}
    assert any("z.py" in p for p in mutation_scope.check_evidence(extra, full, config))
    assert mutation_scope.check_evidence({"scope": ["x"]}, full, config) == [
        "the files that were mutated are not recorded"
    ]


def test_mutation_selection_excludes_tests_that_read_files_outside_the_sandbox():
    """The native stats run executes in a sandbox that holds no remediation documents."""
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    args = tomllib.loads((root / "pyproject.toml").read_text())["tool"]["mutmut"][
        "pytest_add_cli_args_test_selection"
    ]
    ignored = {a.removeprefix("--ignore=") for a in args if a.startswith("--ignore=")}
    for path in sorted((root / "tests").glob("test_*.py")):
        if "docs/thesis-remediation" in path.read_text():
            assert f"tests/{path.name}" in ignored, path.name
    assert "tests/verifier" not in ignored


def test_patterns_follow_mutmut_fnmatch_where_a_star_crosses_directories(tmp_path):
    _tree(tmp_path)
    nested = tmp_path / "src/pkg/tests"
    nested.mkdir()
    (nested / "test_a.py").write_text("def test():\n    pass\n")
    assert mutation_scope.resolve(["src/pkg/*.py"], tmp_path) == [
        "src/pkg/a.py",
        "src/pkg/b.py",
        "src/pkg/tests/test_a.py",
    ]
    assert mutation_scope.resolve(["src/pkg/*.py"], tmp_path, exclude=["src/pkg/tests/*"]) == [
        "src/pkg/a.py",
        "src/pkg/b.py",
    ]


def test_a_pattern_that_would_mutate_test_code_is_reported_by_the_check(tmp_path):
    config = mutation_scope.load(_tree(tmp_path))
    nested = tmp_path / "src/pkg/tests"
    nested.mkdir()
    (nested / "test_a.py").write_text("def test():\n    pass\n")
    patterns = ["src/pkg/*.py", "scripts/*.py"]
    assert any(
        "src/pkg/tests/test_a.py" in p and "outside the eligible roots" in p
        for p in mutation_scope.check(patterns, tmp_path, config)
    )
    assert mutation_scope.check(patterns, tmp_path, config, exclude=["src/pkg/tests/*"]) == []
