"""Exact files, walks, messages and defaults of the mutation scope inventory."""

import json

import pytest

from verification import mutation_scope as ms


def _write(root, *names):
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x = 1\n")


def test_the_scope_is_read_from_the_pyproject_mutmut_table_with_no_exclusion_by_default(tmp_path):
    only = tmp_path / "a.toml"
    only.write_text('[tool.mutmut]\nonly_mutate = ["src/*.py", "scripts/*.py"]\n')
    assert ms.configured_patterns(only) == ["src/*.py", "scripts/*.py"]
    assert ms.configured_exclusions(only) == []
    both = tmp_path / "b.toml"
    both.write_text('[tool.mutmut]\nonly_mutate = ["x"]\ndo_not_mutate = ["t/*"]\n')
    assert ms.configured_exclusions(both) == ["t/*"]


def test_the_default_pyproject_and_scope_file_are_the_repository_ones():
    assert ms.CONFIG == ms.ROOT / "verification" / "mutation_scope.json"
    assert ms.ROOT.joinpath("pyproject.toml").is_file()
    assert ms.configured_patterns()
    assert ms.load()["version"] == ms.VERSION == 2


def test_a_wrong_version_is_refused_with_the_expected_number(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"version": 3}))
    with pytest.raises(ValueError) as refused:
        ms.load(path)
    assert str(refused.value) == "mutation scope version must be 2"
    path.write_text("{}")
    with pytest.raises(ValueError):
        ms.load(path)


@pytest.mark.parametrize("skipped", ["__pycache__", "mutants", ".git", ".venv", "node_modules"])
def test_the_walk_never_enters_cache_vcs_environment_or_package_directories(tmp_path, skipped):
    _write(tmp_path, "src/a.py", f"src/{skipped}/b.py", f"src/deep/{skipped}/c.py", "src/deep/d.py")
    assert ms._walk(tmp_path, ["src/*.py"]) == ["src/a.py", "src/deep/d.py"]


def test_the_walk_lists_only_python_files_as_posix_paths(tmp_path):
    _write(tmp_path, "src/a.py", "src/a.pyc", "src/notes.txt", "src/pkg/b.py")
    assert ms._walk(tmp_path, ["src/*.py"]) == ["src/a.py", "src/pkg/b.py"]


@pytest.mark.parametrize(
    "pattern", ["src/pkg/a*.py", "src/pkg/a?.py", "src/pkg/[ab]*.py", "src/pkg/ab.py"]
)
def test_the_walk_starts_below_the_literal_directory_prefix_of_a_pattern(tmp_path, pattern):
    _write(tmp_path, "src/pkg/ab.py", "src/other/z.py", "top.py")
    assert ms._walk(tmp_path, [pattern]) == ["src/pkg/ab.py"]


def test_a_pattern_without_a_directory_walks_the_whole_root(tmp_path):
    _write(tmp_path, "top.py", "src/a.py")
    assert ms._walk(tmp_path, ["*.py"]) == ["src/a.py", "top.py"]


def test_the_walk_is_the_sorted_union_of_the_walks_of_every_pattern(tmp_path):
    _write(tmp_path, "b/x.py", "a/y.py", "a/z.py")
    assert ms._walk(tmp_path, ["b/*.py", "a/*.py", "a/z.py"]) == ["a/y.py", "a/z.py", "b/x.py"]


def test_a_file_is_selected_when_a_pattern_matches_it_and_no_exclusion_does(tmp_path):
    _write(tmp_path, "src/a.py", "src/b.py", "src/tests/test_c.py")
    assert ms.resolve(["src/*.py"], tmp_path, ["src/tests/*"]) == ["src/a.py", "src/b.py"]
    assert ms.resolve(["src/*.py"], tmp_path, ("src/b.py",)) == ["src/a.py", "src/tests/test_c.py"]


def _config(**over):
    return {"version": 2, "roots": ["src"], "exclusions": {}, **over}


def test_every_scope_problem_has_its_own_exact_message(tmp_path):
    _write(tmp_path, "src/a.py", "src/b.py", "other/c.py")
    config = _config(exclusions={"src/b.py": "constants", "src/gone.py": " "})
    problems = ms.check(["src/*.py", "other/*.py", "ghost/*.py"], tmp_path, config)
    assert problems == [
        "exclusion src/gone.py has no reason",
        "exclusion src/gone.py does not exist",
        "src/b.py is mutated although it is excluded",
        "other/c.py is mutated but is outside the eligible roots",
        "pattern ghost/*.py matches no file",
    ]


def test_an_eligible_file_that_is_not_mutated_is_named(tmp_path):
    _write(tmp_path, "src/a.py", "src/b.py")
    assert ms.check(["src/a.py"], tmp_path, _config()) == ["src/b.py is eligible but not mutated"]


def test_a_pattern_is_checked_without_the_exclusions_so_an_excluded_match_still_counts(tmp_path):
    _write(tmp_path, "src/a.py", "src/tests/test_a.py")
    assert ms.check(["src/*.py"], tmp_path, _config(), ["src/tests/*"]) == []
    assert ms.check(["src/tests/*.py"], tmp_path, _config(), ["src/tests/*"]) == [
        "src/a.py is eligible but not mutated"
    ]


def test_the_mutant_listing_is_split_at_its_first_separator_and_only_mutant_lines_count(tmp_path):
    _write(tmp_path, "src/pkg/a.py", "src/pkg/b.py", "src/pkg/c.py")
    text = "\n".join(
        [
            "pkg.a.x_f__mutmut_1: killed: by tests",
            "pkg.b.x_g__mutmut_1 killed",
            "pkg.c.helper: survived",
            "  pkg.c.x_h__mutmut_1: survived  ",
        ]
    )
    assert ms.mutated_files(text, tmp_path) == ["src/pkg/a.py", "src/pkg/c.py"]


def test_a_non_mutant_line_does_not_stop_the_reading_of_the_following_ones(tmp_path):
    _write(tmp_path, "src/pkg/a.py")
    text = "header\npkg.zzz.helper: x\npkg.a.x_f__mutmut_1: killed\n"
    assert ms.mutated_files(text, tmp_path) == ["src/pkg/a.py"]


def test_a_package_initialiser_and_the_given_bases_are_searched(tmp_path):
    _write(tmp_path, "src/pkg/__init__.py", "tools/run.py")
    text = "pkg.x_f__mutmut_1: killed\ntools.run.x_g__mutmut_1: killed\n"
    assert ms.mutated_files(text, tmp_path) == ["src/pkg/__init__.py", "tools/run.py"]
    assert ms.mutated_files(text, tmp_path, ("src",)) == ["src/pkg/__init__.py"]


def test_the_default_bases_are_the_source_tree_then_the_repository_root(tmp_path):
    _write(tmp_path, "src/pkg/a.py", "scripts/run.py")
    text = "pkg.a.x_f__mutmut_1: killed\nscripts.run.x_g__mutmut_1: killed\n"
    assert ms.mutated_files(text, tmp_path) == ["scripts/run.py", "src/pkg/a.py"]


def test_the_comparison_of_mutated_files_names_each_gap_exactly():
    config = {"no_mutants": {"c.py": "re-exports"}}
    assert ms.check_mutated(["a.py", "c.py"], ["a.py", "z.py"], config) == [
        "z.py received mutants but is outside the recorded scope"
    ]
    assert ms.check_mutated(["a.py", "b.py", "c.py"], ["a.py"], config) == [
        "b.py is in the scope but received no mutant"
    ]
    assert ms.check_mutated(["a.py"], ["a.py"], {}) == []


def test_a_recorded_scope_is_judged_exactly_on_each_side():
    config = {}
    result = {"scope_files": ["a.py", "z.py"], "mutated_files": ["a.py", "z.py"]}
    assert ms.check_evidence(result, ["a.py", "b.py"], config) == [
        "b.py is eligible but not mutated",
        "z.py was mutated but is not an eligible file",
    ]


@pytest.mark.parametrize(
    "result",
    [
        {"scope_files": "a.py", "mutated_files": ["a.py"]},
        {"scope_files": ["a.py"], "mutated_files": "a.py"},
        {"scope_files": ["a.py"]},
        {"mutated_files": ["a.py"]},
        {},
    ],
)
def test_a_scope_record_missing_or_malformed_on_either_side_is_not_accepted(result):
    assert ms.check_evidence(result, ["a.py"], {}) == [
        "the files that were mutated are not recorded"
    ]
