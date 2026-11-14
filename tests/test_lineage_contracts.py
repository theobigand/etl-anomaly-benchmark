"""Exact verdicts, messages and file selection of the lineage checks."""

import hashlib
import json
import subprocess

import pytest

from experiments import provenance
from verification import lineage

PYPROJECT = b'[project]\nname = "x"\nversion = "1"\n'


def _sources():
    return {
        "src/pkg/a.py": b"A = 1\n",
        "src/pkg/readme.txt": b"not python",
        "experiments/run.py": b"RUN = 1\n",
        "experiments/sub/deep.py": b"DEEP = 1\n",
        "experiments/notes.txt": b"notes",
        "other/c.py": b"C = 1\n",
        "environment.yml": b"name: e\n",
        "pyproject.toml": PYPROJECT,
    }


def test_recipe_one_covers_python_in_src_top_level_experiments_and_the_environment_file():
    files = _sources()
    digest = hashlib.sha256()
    for name in ("environment.yml", "experiments/run.py", "src/pkg/a.py"):
        digest.update(name.encode())
        digest.update(files[name])
    digest.update(json.dumps({"name": "x", "version": "1"}, sort_keys=True).encode())
    assert lineage.fingerprint_v1_of(files) == digest.hexdigest()


def test_a_record_without_any_measurement_field_is_legacy_and_one_with_a_field_is_not():
    assert lineage.check_measurement({}, {}) == ("LEGACY", [])
    only_recipe = lineage.check_measurement(
        {"measurement_recipe": provenance.MEASUREMENT_RECIPE}, {}
    )
    assert only_recipe == ("STALE", ["the measurement fingerprint is missing or malformed"])
    only_fingerprint = lineage.check_measurement({"measurement_fingerprint": "abc"}, {})
    assert only_fingerprint == ("STALE", ["unknown measurement recipe None"])


def test_an_unknown_or_unreadable_measurement_stamp_is_stale_with_its_exact_reason():
    assert lineage.check_measurement({"measurement_recipe": 99}, {}) == (
        "STALE",
        ["unknown measurement recipe 99"],
    )
    recipe = provenance.MEASUREMENT_RECIPE
    malformed = ("STALE", ["the measurement fingerprint is missing or malformed"])
    for stored in (5, "", None, ["x"]):
        record = {"measurement_recipe": recipe, "measurement_fingerprint": stored}
        assert lineage.check_measurement(record, {}) == malformed


def test_a_measurement_stamp_is_bound_only_while_the_method_is_unchanged():
    files = {"verification/scaling.py": b"def timing(): pass\n"}
    stamp = provenance.measurement_fingerprint_of(files)
    record = {
        "measurement_recipe": provenance.MEASUREMENT_RECIPE,
        "measurement_fingerprint": stamp,
    }
    assert lineage.check_measurement(record, files) == ("BOUND", [])
    changed = {"verification/scaling.py": b"def timing(): return 1\n"}
    assert lineage.check_measurement(record, changed) == (
        "STALE",
        ["the measurement method changed since this record was produced"],
    )


def test_a_recipe_one_record_reports_each_of_its_two_possible_problems_exactly():
    anchor = _sources()
    good = {"source_fingerprint": lineage.fingerprint_v1_of(anchor)}
    assert lineage.check_record(good, anchor, anchor) == []
    bad = {"source_fingerprint": "0" * 64}
    assert lineage.check_record(bad, anchor, anchor) == [
        "the anchor tree does not reproduce the recipe-1 fingerprint"
    ]
    moved = {**anchor, "src/pkg/a.py": b"A = 2\n"}
    assert lineage.check_record(good, anchor, moved) == [
        "result-affecting source changed since the anchor revision"
    ]
    assert lineage.check_record(bad, anchor, moved) == [
        "the anchor tree does not reproduce the recipe-1 fingerprint",
        "result-affecting source changed since the anchor revision",
    ]


def test_a_recipe_two_record_is_checked_against_the_current_source_and_other_recipes_are_unknown():
    files = _sources()
    record = {
        "fingerprint_recipe": provenance.SCIENTIFIC_RECIPE,
        "scientific_fingerprint": provenance.scientific_fingerprint_of(files),
    }
    assert lineage.check_record(record, files, files) == []
    moved = {**files, "src/pkg/a.py": b"A = 2\n"}
    assert lineage.check_record(record, files, moved) == [
        "scientific fingerprint differs from the current source"
    ]
    assert lineage.check_record({"fingerprint_recipe": 7}, files, files) == [
        "unknown fingerprint recipe 7"
    ]


@pytest.fixture
def repository(tmp_path):
    files = _sources() | {"verification/scaling.py": b"S = 1\n", "docs/x.py": b"X = 1\n"}
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    for command in (
        ["init", "-q"],
        ["add", "-A"],
        ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c"],
    ):
        subprocess.run(["git", *command], cwd=tmp_path, check=True)
    return tmp_path


def test_a_committed_tree_yields_python_in_src_and_experiments_plus_the_named_files(repository):
    got = lineage.files_at("HEAD", repository)
    assert set(got) == {
        "src/pkg/a.py",
        "experiments/run.py",
        "experiments/sub/deep.py",
        "environment.yml",
        "pyproject.toml",
        "verification/scaling.py",
    }
    assert got["src/pkg/a.py"] == b"A = 1\n"


def test_the_working_tree_yields_the_same_kinds_of_files_with_relative_names(repository):
    got = lineage.worktree_files(repository)
    assert set(got) == {
        "src/pkg/a.py",
        "experiments/run.py",
        "environment.yml",
        "pyproject.toml",
        "verification/scaling.py",
    }
