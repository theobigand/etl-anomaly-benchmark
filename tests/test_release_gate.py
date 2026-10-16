"""The release gate certifies only complete, consistent, clean evidence."""

import copy
import json
import subprocess
import sys

import pytest

from tests.test_evidence_schema import ENVIRONMENT, SOURCE, _deep, _fast, _matrix, _real
from verification import evidence_schema, release

KINDS = ("fast", "deep", "faults", "real")


@pytest.fixture(autouse=True)
def _two_required_datasets(monkeypatch):
    monkeypatch.setattr(evidence_schema, "REQUIRED_DATASETS", ("a", "b"))
    # the verdict must not depend on whether the suite itself runs under CI
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)


def _docs(tmp_path):
    return {
        "fast": _fast(tmp_path),
        "deep": _deep(tmp_path),
        "faults": _matrix(tmp_path),
        "real": _real(tmp_path),
    }


def _assess(tmp_path, docs=None, current=None, **kwargs):
    kwargs.setdefault("manifest", {"a": "1" * 64, "b": "2" * 64})
    kwargs.setdefault("lineage", {"legacy": [], "problems": {}})
    return release.assess(
        docs if docs is not None else _docs(tmp_path),
        current=current or copy.deepcopy(SOURCE),
        root=tmp_path,
        **kwargs,
    )


def test_complete_consistent_evidence_is_certified_but_not_independently_attested(tmp_path):
    report = _assess(tmp_path)
    assert report["status"] == "CERTIFIED", report["reasons"]
    assert report["reasons"] == []
    assert report["attestation"] == "local-unattested"
    assert set(report["profiles"]) == set(KINDS)


def test_ci_run_is_recorded_but_never_called_independent(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    report = _assess(tmp_path)
    assert report["attestation"] == "ci-run:42 (not independently attested)"


@pytest.mark.parametrize("kind", KINDS)
def test_missing_evidence_is_incomplete(tmp_path, kind):
    docs = _docs(tmp_path)
    docs[kind] = None
    report = _assess(tmp_path, docs)
    assert report["status"] == "INCOMPLETE"
    assert any(kind in reason and "missing" in reason for reason in report["reasons"])


@pytest.mark.parametrize("kind", KINDS)
def test_a_malformed_document_is_rejected(tmp_path, kind):
    docs = _docs(tmp_path)
    docs[kind]["status"] = "OK"
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    assert any(kind in reason for reason in report["reasons"])


def test_failed_profiles_reject_and_unfinished_ones_are_incomplete(tmp_path):
    docs = _docs(tmp_path)
    docs["deep"] = _deep(tmp_path, killed=90, survived=10)
    assert _assess(tmp_path, docs)["status"] == "REJECTED"
    docs = _docs(tmp_path)
    docs["deep"] = _deep(tmp_path, killed=99, survived=0, check_was_interrupted_by_user=1)
    assert _assess(tmp_path, docs)["status"] == "INCOMPLETE"
    docs = _docs(tmp_path)
    docs["faults"] = _matrix(tmp_path, names=["f1"])
    assert _assess(tmp_path, docs)["status"] == "INCOMPLETE"


def test_evidence_from_another_revision_is_rejected(tmp_path):
    docs = _docs(tmp_path)
    docs["deep"]["source"]["revision"] = "c" * 40
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    assert any("revision" in reason for reason in report["reasons"])


def test_evidence_must_match_the_current_head_and_science(tmp_path):
    other = {**SOURCE, "revision": "d" * 40}
    assert _assess(tmp_path, current=other)["status"] == "REJECTED"
    other = {**SOURCE, "scientific_fingerprint": "e" * 64}
    report = _assess(tmp_path, current=other)
    assert report["status"] == "REJECTED"
    assert any("fingerprint" in reason for reason in report["reasons"])


def test_a_dirty_worktree_rejects_certification(tmp_path):
    report = _assess(tmp_path, current={**SOURCE, "worktree_dirty": True})
    assert report["status"] == "REJECTED"
    assert any("dirty" in reason for reason in report["reasons"])
    docs = _docs(tmp_path)
    docs["fast"]["source"]["worktree_dirty"] = True
    assert any("dirty" in r for r in _assess(tmp_path, docs)["reasons"])


def test_a_changed_artifact_is_rejected(tmp_path):
    docs = _docs(tmp_path)
    (tmp_path / "coverage.json").write_text("{}")
    report = _assess(tmp_path, docs)
    assert report["status"] == "REJECTED"
    assert any("hash" in reason for reason in report["reasons"])


def test_dataset_hashes_must_match_the_reference_manifest(tmp_path):
    report = _assess(tmp_path, manifest={"a": "1" * 64, "b": "9" * 64})
    assert report["status"] == "REJECTED"
    assert any("dataset b" in reason for reason in report["reasons"])
    assert _assess(tmp_path, manifest={"a": "1" * 64})["status"] == "REJECTED"


def test_legacy_experiment_records_keep_the_release_incomplete(tmp_path):
    report = _assess(tmp_path, lineage={"legacy": ["run_synthetic"], "problems": {}})
    assert report["status"] == "INCOMPLETE"
    assert any("clean replay" in reason for reason in report["reasons"])


def test_broken_lineage_rejects(tmp_path):
    report = _assess(tmp_path, lineage={"legacy": [], "problems": {"run_curves": ["stale"]}})
    assert report["status"] == "REJECTED"
    assert any("run_curves" in reason for reason in report["reasons"])


def test_rejection_outranks_incomplete(tmp_path):
    docs = _docs(tmp_path)
    docs["faults"] = None
    docs["deep"]["status"] = "OK"
    assert _assess(tmp_path, docs)["status"] == "REJECTED"


def test_command_writes_a_report_and_fails_unless_certified(tmp_path):
    out = tmp_path / "release.json"
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "verification.release",
            "--evidence",
            str(tmp_path / "none"),
            "--output",
            str(out),
        ],
        cwd=release.ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 1
    report = json.loads(out.read_text())
    assert report["status"] in ("INCOMPLETE", "REJECTED")
    assert "release: " in done.stdout
    assert ENVIRONMENT  # fixtures imported for the shared builders


def test_dirty_worktree_runs_are_kept_as_history_but_block_certification(tmp_path):
    report = _assess(tmp_path, lineage={"legacy": [], "dirty": ["run_curves"], "problems": {}})
    assert report["status"] == "INCOMPLETE"
    assert any(
        "dirty worktree" in reason and "run_curves" in reason for reason in report["reasons"]
    )
