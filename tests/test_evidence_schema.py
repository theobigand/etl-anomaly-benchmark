"""Evidence envelopes: every kind validates, and every doctored one is rejected."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from verification import evidence_schema as evidence

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {"revision": "a" * 40, "worktree_dirty": False, "scientific_fingerprint": "b" * 64}
ENVIRONMENT = {"python": "3.11.0", "platform": "test", "packages": {"numpy": "2.0", "pyod": None}}
FAULT_NAMES = ["f1", "f2", "f3"]


def _fast(tmp_path, failures=0, covered=10):
    coverage = tmp_path / "coverage.json"
    coverage.write_text(
        json.dumps(
            {
                "totals": {
                    "covered_lines": covered,
                    "num_statements": 10,
                    "covered_branches": 4,
                    "num_branches": 4,
                },
                "files": {},
            }
        )
    )
    junit = tmp_path / "pytest.xml"
    junit.write_text(
        f'<testsuites><testsuite tests="5" failures="{failures}" errors="0" skipped="0"/>'
        "</testsuites>"
    )
    return evidence.build_fast(
        coverage, junit, root=tmp_path, source=SOURCE, environment=ENVIRONMENT
    )


def _stats(**changes):
    result = {key: 0 for key in evidence.OUTCOMES}
    result.update(total=100, killed=98, survived=2)
    result.update(changes)
    return result


def _deep(tmp_path, **changes):
    stats = tmp_path / "stats.json"
    stats.write_text(json.dumps(_stats(**changes)))
    return evidence.build_deep(
        stats, root=tmp_path, scope=["src/x.py"], source=SOURCE, environment=ENVIRONMENT
    )


def _matrix(tmp_path, names=FAULT_NAMES, caught=True, control=True):
    path = tmp_path / "fault_matrix.json"
    rows = [
        {"defect": name, "caught_by_expected_test": caught, "control_passed": control}
        for name in names
    ]
    path.write_text(json.dumps(rows))
    return evidence.build_faults(
        path, FAULT_NAMES, root=tmp_path, source=SOURCE, environment=ENVIRONMENT
    )


@pytest.fixture(autouse=True)
def _two_required_datasets(monkeypatch):
    monkeypatch.setattr(evidence, "REQUIRED_DATASETS", ("a", "b"))


def _real(tmp_path, datasets=None, required=("a", "b")):
    path = tmp_path / "real.json"
    datasets = (
        datasets
        if datasets is not None
        else [
            {"dataset": "a", "status": "PASS", "sha256": "1" * 64},
            {"dataset": "b", "status": "PASS", "sha256": "2" * 64},
        ]
    )
    path.write_text(
        json.dumps({"required": list(required), "status": "PASS", "datasets": datasets})
    )
    return evidence.build_real(path, root=tmp_path, source=SOURCE, environment=ENVIRONMENT)


def test_every_kind_builds_a_valid_passing_envelope(tmp_path):
    for doc in (_fast(tmp_path), _deep(tmp_path), _matrix(tmp_path), _real(tmp_path)):
        assert doc["status"] == "PASS", doc
        assert evidence.validate(doc, root=tmp_path) == []


def test_the_default_source_and_environment_describe_this_repository():
    source = evidence.collect_source(ROOT)
    assert len(source["revision"]) == 40
    assert isinstance(source["worktree_dirty"], bool)
    assert len(source["scientific_fingerprint"]) == 64
    environment = evidence.collect_environment()
    assert environment["python"].count(".") == 2
    assert "numpy" in environment["packages"]


@pytest.mark.parametrize(
    "key",
    [
        "schema_version",
        "kind",
        "status",
        "captured_at",
        "source",
        "environment",
        "artifacts",
        "result",
    ],
)
def test_a_missing_envelope_field_is_rejected(tmp_path, key):
    doc = _fast(tmp_path)
    del doc[key]
    assert evidence.validate(doc)


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), 1),
        (("schema_version",), "2"),
        (("kind",), "slow"),
        (("status",), "OK"),
        (("status",), True),
        (("captured_at",), "yesterday"),
        (("captured_at",), "2026-10-16T12:00:00"),  # no timezone
        (("source", "revision"), "abc"),
        (("source", "revision"), None),
        (("source", "worktree_dirty"), "no"),
        (("source", "scientific_fingerprint"), "z" * 64),
        (("environment", "python"), 3),
        (("environment", "packages"), []),
        (("artifacts",), []),
        (("artifacts", "coverage.json"), "short"),
        (("result",), []),
    ],
)
def test_a_malformed_envelope_field_is_rejected(tmp_path, path, value):
    doc = _fast(tmp_path)
    target = doc
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = value
    assert evidence.validate(doc), path


def test_a_non_mapping_document_is_rejected():
    assert evidence.validate([])
    assert evidence.validate(None)


def test_fast_status_is_recomputed_from_the_results(tmp_path):
    assert _fast(tmp_path, failures=1)["status"] == "FAIL"
    assert _fast(tmp_path, covered=9)["status"] == "FAIL"
    doc = _fast(tmp_path)
    doc["result"]["tests"]["failures"] = 1
    assert any("status PASS" in problem for problem in evidence.validate(doc))
    doc = _fast(tmp_path)
    doc["result"]["coverage"]["line"]["covered"] = 3
    assert any("status PASS" in problem for problem in evidence.validate(doc))
    doc = _fast(tmp_path)
    doc["result"]["tests"]["total"] = 0
    assert any("status PASS" in problem for problem in evidence.validate(doc))
    doc = _fast(tmp_path)
    doc["result"]["coverage"]["branch"] = {"covered": 0, "coverable": 0}
    assert any("status PASS" in problem for problem in evidence.validate(doc))


def test_fast_builder_rejects_missing_evidence(tmp_path):
    with pytest.raises(ValueError):
        evidence.build_fast(tmp_path / "no.json", tmp_path / "no.xml", root=tmp_path)


def test_deep_status_follows_the_mutation_gate(tmp_path):
    assert _deep(tmp_path, killed=94, survived=6)["status"] == "FAIL"
    interrupted = _deep(tmp_path, killed=99, survived=0, check_was_interrupted_by_user=1)
    assert interrupted["status"] == "INCOMPLETE"
    assert "interrupted" in interrupted["result"]["reason"]
    assert _deep(tmp_path, total=0, killed=0, survived=0)["status"] == "INCOMPLETE"


def test_deep_doctored_counts_cannot_keep_a_pass(tmp_path):
    doc = _deep(tmp_path)
    doc["result"]["stats"]["killed"] = 90
    doc["result"]["stats"]["survived"] = 10
    assert any("status PASS" in problem for problem in evidence.validate(doc))
    doc = _deep(tmp_path)
    doc["result"]["stats"]["survived"] = -2
    doc["result"]["stats"]["killed"] = 102
    assert evidence.validate(doc)
    doc = _deep(tmp_path)
    doc["result"]["scope"] = []
    assert any("scope" in problem for problem in evidence.validate(doc))


def test_deep_unreadable_stats_are_incomplete_not_a_crash(tmp_path):
    stats = tmp_path / "stats.json"
    stats.write_text("not json")
    doc = evidence.build_deep(
        stats, root=tmp_path, scope=["x"], source=SOURCE, environment=ENVIRONMENT
    )
    assert doc["status"] == "INCOMPLETE"
    missing = evidence.build_deep(
        tmp_path / "gone.json", root=tmp_path, scope=["x"], source=SOURCE, environment=ENVIRONMENT
    )
    assert missing["status"] == "INCOMPLETE"


def test_faults_require_every_fault_caught_with_a_passing_control(tmp_path):
    assert _matrix(tmp_path, names=FAULT_NAMES[:2])["status"] == "INCOMPLETE"
    assert _matrix(tmp_path, names=[])["status"] == "INCOMPLETE"
    assert _matrix(tmp_path, caught=False)["status"] == "FAIL"
    assert _matrix(tmp_path, control=False)["status"] == "FAIL"
    assert _matrix(tmp_path, names=[*FAULT_NAMES, "extra"])["status"] == "INCOMPLETE"


def test_faults_doctored_results_cannot_keep_a_pass(tmp_path):
    doc = _matrix(tmp_path)
    doc["result"]["faults"][0]["detected"] = False
    assert any("status PASS" in problem for problem in evidence.validate(doc))
    doc = _matrix(tmp_path)
    doc["result"]["faults"].pop()
    assert any("status PASS" in problem for problem in evidence.validate(doc))
    doc = _matrix(tmp_path)
    doc["result"]["control_passed"] = False
    assert any("status PASS" in problem for problem in evidence.validate(doc))


def test_faults_unreadable_matrix_is_incomplete(tmp_path):
    path = tmp_path / "fault_matrix.json"
    path.write_text('{"not": "a list"}')
    doc = evidence.build_faults(
        path, FAULT_NAMES, root=tmp_path, source=SOURCE, environment=ENVIRONMENT
    )
    assert doc["status"] == "INCOMPLETE"
    gone = evidence.build_faults(
        tmp_path / "gone.json", FAULT_NAMES, root=tmp_path, source=SOURCE, environment=ENVIRONMENT
    )
    assert gone["status"] == "INCOMPLETE"


def test_real_requires_the_exact_required_datasets_all_passing(tmp_path):
    assert _real(tmp_path, datasets=[])["status"] == "FAIL"
    only_a = [{"dataset": "a", "status": "PASS", "sha256": "1" * 64}]
    assert _real(tmp_path, datasets=only_a)["status"] == "FAIL"
    absent = [
        {"dataset": "a", "status": "PASS", "sha256": "1" * 64},
        {"dataset": "b", "status": "NOT_RUN"},
    ]
    assert _real(tmp_path, datasets=absent)["status"] == "NOT_RUN"
    # a report that claims fewer requirements does not lower the bar
    assert _real(tmp_path, datasets=only_a, required=("a",))["status"] == "FAIL"


def test_real_doctored_results_cannot_keep_a_pass(tmp_path):
    doc = _real(tmp_path)
    doc["result"]["datasets"].pop()
    assert any("status PASS" in problem for problem in evidence.validate(doc))
    doc = _real(tmp_path)
    doc["result"]["required"] = []
    assert any("status PASS" in problem for problem in evidence.validate(doc))
    doc = _real(tmp_path)
    doc["result"]["datasets"][0]["status"] = "FAIL"
    assert any("status PASS" in problem for problem in evidence.validate(doc))


def test_real_unreadable_report_is_not_a_pass(tmp_path):
    path = tmp_path / "real.json"
    path.write_text("[")
    doc = evidence.build_real(path, root=tmp_path, source=SOURCE, environment=ENVIRONMENT)
    assert doc["status"] == "INCOMPLETE"


def test_artifact_hashes_are_checked_against_the_files(tmp_path):
    doc = _fast(tmp_path)
    assert (
        doc["artifacts"]["coverage.json"]
        == hashlib.sha256((tmp_path / "coverage.json").read_bytes()).hexdigest()
    )
    (tmp_path / "coverage.json").write_text("{}")
    assert any("hash" in problem for problem in evidence.validate(doc, root=tmp_path))
    (tmp_path / "coverage.json").unlink()
    assert any("missing" in problem for problem in evidence.validate(doc, root=tmp_path))


def test_a_passing_envelope_must_list_its_artifacts(tmp_path):
    doc = _fast(tmp_path)
    doc["artifacts"] = {}
    assert any("artifact" in problem for problem in evidence.validate(doc))


def test_validation_does_not_mutate_its_input(tmp_path):
    doc = _fast(tmp_path)
    before = copy.deepcopy(doc)
    evidence.validate(doc, root=tmp_path)
    assert doc == before


def test_command_line_validate_and_write(tmp_path):
    doc = _fast(tmp_path)
    good = tmp_path / "good.json"
    good.write_text(json.dumps(doc))
    bad = tmp_path / "bad.json"
    doc["status"] = "OK"
    bad.write_text(json.dumps(doc))

    def run(path):
        return subprocess.run(
            [sys.executable, "-m", "verification.evidence_schema", "validate", str(path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    assert run(good).returncode == 0
    failed = run(bad)
    assert failed.returncode == 1 and "status" in failed.stdout
    garbage = tmp_path / "garbage.json"
    garbage.write_text("{")
    assert run(garbage).returncode == 1
    assert run(tmp_path / "gone.json").returncode == 1


def test_command_line_builders_write_validated_envelopes(tmp_path):
    def run(*args):
        return subprocess.run(
            [sys.executable, "-m", "verification.evidence_schema", *args, "--root", str(tmp_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def p(name):
        return str(tmp_path / name)

    _fast(tmp_path)
    done = run(
        "fast",
        "--coverage",
        p("coverage.json"),
        "--junit",
        p("pytest.xml"),
        "--output",
        p("o/fast.json"),
    )
    assert done.returncode == 0 and "fast evidence: PASS" in done.stdout
    assert json.loads((tmp_path / "o/fast.json").read_text())["kind"] == "fast"

    _deep(tmp_path)
    done = run("deep", "--stats", p("stats.json"), "--output", p("d.json"))
    assert done.returncode == 0
    assert json.loads((tmp_path / "d.json").read_text())["result"]["scope"]  # from pyproject

    _real(tmp_path)
    done = run("real", "--report", p("real.json"), "--output", p("r.json"))
    assert done.returncode == 1  # required set {a, b} is not the real one, but it was recorded
    assert json.loads((tmp_path / "r.json").read_text())["kind"] == "real"

    (tmp_path / "fault_matrix.json").write_text("[]")
    done = run("faults", "--matrix", p("fault_matrix.json"), "--output", p("f.json"))
    assert done.returncode == 1
    assert json.loads((tmp_path / "f.json").read_text())["status"] == "INCOMPLETE"

    done = run("fast", "--coverage", p("x.json"), "--junit", p("y.xml"), "--output", p("z.json"))
    assert done.returncode == 1 and "INVALID" in done.stdout
    assert not (tmp_path / "z.json").exists()


def test_fault_names_are_the_twenty_three_scientific_defects():
    names = evidence.fault_names()
    assert len(names) == 23 and len(set(names)) == 23
    # the original fourteen stay in the matrix
    assert {"fit_on_evaluation_data", "dropped_detector_run"} <= set(names)


def test_relative_artifact_paths_are_recorded_relative_to_the_root(tmp_path, monkeypatch):
    _real(tmp_path)
    monkeypatch.chdir(tmp_path)
    doc = evidence.build_real(
        Path("real.json"), root=tmp_path, source=SOURCE, environment=ENVIRONMENT
    )
    assert list(doc["artifacts"]) == ["real.json"]
