"""The v2 fingerprint binds result-affecting code; the v1 recipe stays as it was."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import provenance  # noqa: E402

from verification import lineage  # noqa: E402

PYPROJECT = b'[project]\nname = "p"\ndependencies = ["pandas"]\n\n[tool.mutmut]\nx = 1\n'
PROVENANCE = (
    b"def write_split_ids():\n    return 1\n\n"
    b"def read_split_ids():\n    return 2\n\n"
    b"def write_record():\n    return 3\n"
)


def _files(changes=None):
    files = {
        "src/pkg/mod.py": b"a = 1\n",
        "experiments/run_benchmark.py": b"b = 2\n",
        "experiments/provenance.py": PROVENANCE,
        "experiments/verify_real.py": b"gate = 1\n",
        "experiments/check_mutation.py": b"gate = 2\n",
        "experiments/verification_report.py": b"gate = 3\n",
        "environment.yml": b"name: e\n",
        "pyproject.toml": PYPROJECT,
    }
    files.update(changes or {})
    return files


def _fp(changes=None):
    return provenance.scientific_fingerprint_of(_files(changes))


@pytest.mark.parametrize(
    "path",
    [
        "experiments/verify_real.py",
        "experiments/check_mutation.py",
        "experiments/verification_report.py",
    ],
)
def test_verification_only_scripts_do_not_change_the_scientific_fingerprint(path):
    assert provenance.scientific_fingerprint_of({**_files(), path: b"edited\n"}) == _fp()


def test_tests_and_documentation_do_not_change_the_scientific_fingerprint():
    extra = {**_files(), "tests/test_x.py": b"x\n", "README.md": b"y\n"}
    assert provenance.scientific_fingerprint_of(extra) == _fp()


@pytest.mark.parametrize(
    "path", ["src/pkg/mod.py", "experiments/run_benchmark.py", "environment.yml"]
)
def test_result_affecting_files_change_the_scientific_fingerprint(path):
    assert provenance.scientific_fingerprint_of({**_files(), path: b"edited\n"}) != _fp()


def test_a_new_result_producing_script_changes_the_scientific_fingerprint():
    assert provenance.scientific_fingerprint_of({**_files(), "experiments/new.py": b"z\n"}) != _fp()


def test_project_dependencies_count_but_tool_settings_do_not():
    assert _fp({"pyproject.toml": PYPROJECT.replace(b"x = 1", b"x = 2")}) == _fp()
    assert _fp({"pyproject.toml": PYPROJECT.replace(b"pandas", b"pandas>=2")}) != _fp()


def test_provenance_module_contributes_only_the_split_id_functions():
    assert _fp({"experiments/provenance.py": PROVENANCE + b"\n# note\n"}) == _fp()
    assert _fp({"experiments/provenance.py": PROVENANCE.replace(b"return 3", b"return 4")}) == _fp()
    assert _fp({"experiments/provenance.py": PROVENANCE.replace(b"return 1", b"return 9")}) != _fp()
    assert _fp({"experiments/provenance.py": PROVENANCE.replace(b"return 2", b"return 9")}) != _fp()


def test_the_recipe_is_versioned_and_differs_from_v1():
    assert provenance.SCIENTIFIC_RECIPE == 2
    assert {
        "experiments/verify_real.py",
        "experiments/check_mutation.py",
        "experiments/verification_report.py",
    } == provenance.VERIFICATION_ONLY


def test_worktree_fingerprint_matches_the_mapping_form(tmp_path, monkeypatch):
    for path, content in _files().items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    monkeypatch.setattr(provenance, "ROOT", tmp_path)
    assert provenance.scientific_fingerprint() == _fp()


def test_v1_fingerprint_is_left_untouched_by_the_verification_scripts(tmp_path, monkeypatch):
    for path, content in _files().items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    monkeypatch.setattr(provenance, "ROOT", tmp_path)
    base = provenance._source_fingerprint()
    assert lineage.fingerprint_v1_of(_files()) == base
    (tmp_path / "experiments/verify_real.py").write_bytes(b"edited\n")
    assert provenance._source_fingerprint() != base  # v1 still binds the gates


def test_new_records_carry_both_recipes(tmp_path):
    output = tmp_path / "run.json"
    provenance.write_record(
        output, experiment="e", seeds=[1], dataset="toy", data_path=None, settings={}, outputs=[]
    )
    record = json.loads(output.read_text())
    assert record["fingerprint_recipe"] == 2
    assert record["scientific_fingerprint"] == provenance.scientific_fingerprint()
    assert record["source_fingerprint"] == provenance._source_fingerprint()


def _legacy(files):
    return {"source_fingerprint": lineage.fingerprint_v1_of(files)}


def test_legacy_record_is_valid_when_the_anchor_matches_and_science_is_unchanged():
    anchor = _files()
    current = _files({"experiments/verify_real.py": b"edited gate\n"})
    assert lineage.check_record(_legacy(anchor), anchor, current) == []


def test_legacy_record_is_rejected_when_science_changed_since_the_anchor():
    anchor = _files()
    current = _files({"src/pkg/mod.py": b"a = 2\n"})
    problems = lineage.check_record(_legacy(anchor), anchor, current)
    assert any("result-affecting source changed" in item for item in problems)


def test_legacy_record_is_rejected_when_the_anchor_does_not_reproduce_it():
    anchor = _files()
    record = {"source_fingerprint": "0" * 64}
    problems = lineage.check_record(record, anchor, anchor)
    assert any("anchor" in item and "reproduce" in item for item in problems)


def test_v2_record_must_match_the_current_scientific_source():
    current = _files()
    good = {"fingerprint_recipe": 2, "scientific_fingerprint": _fp()}
    assert lineage.check_record(good, current, current) == []
    stale = {"fingerprint_recipe": 2, "scientific_fingerprint": "0" * 64}
    assert lineage.check_record(stale, current, current)


def test_unknown_recipe_and_missing_fields_are_rejected():
    current = _files()
    assert lineage.check_record({"fingerprint_recipe": 3}, current, current)
    assert lineage.check_record({"fingerprint_recipe": 2}, current, current)
    assert lineage.check_record({}, current, current)


def test_lineage_anchor_is_a_commit_that_reproduces_the_archived_recipe_1_fingerprint():
    anchor = lineage.files_at(lineage.anchor_revision())
    stored = json.loads((ROOT / "verification/evidence/run_benchmark_cardio.json").read_text())
    assert stored.get("fingerprint_recipe", 1) == 1
    assert lineage.fingerprint_v1_of(anchor) == stored["source_fingerprint"]


def test_files_at_reads_a_committed_tree_not_the_worktree(tmp_path):
    import subprocess

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.org")
    git("config", "user.name", "t")
    for path, content in _files().items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (tmp_path / "README.md").write_text("ignored\n")
    git("add", ".")
    git("commit", "-qm", "tree")
    (tmp_path / "src/pkg/mod.py").write_bytes(b"uncommitted\n")
    committed = lineage.files_at("HEAD", root=tmp_path)
    assert committed["src/pkg/mod.py"] == b"a = 1\n"
    assert "README.md" not in committed
    assert provenance.scientific_fingerprint_of(committed) == _fp()
    assert lineage.worktree_files(tmp_path)["src/pkg/mod.py"] == b"uncommitted\n"
