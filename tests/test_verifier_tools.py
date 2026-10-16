"""Command-line behavior of the tools under verification/, including their failures."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from tests.test_evidence_schema import ENVIRONMENT, SOURCE, _deep, _fast, _matrix
from verification import archive_evidence, evidence_schema, refresh_profile, release, scaling

ROOT = Path(__file__).resolve().parents[1]


def _git_repo(path):
    for args in (
        ["init", "-q"],
        ["config", "user.email", "t@example.org"],
        ["config", "user.name", "t"],
    ):
        subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)
    (path / "seed.txt").write_text("x\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=path, check=True, capture_output=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def test_archive_command_rehashes_the_manifest_with_the_current_revision(tmp_path, monkeypatch):
    revision = _git_repo(tmp_path)
    artifact = tmp_path / "evidence" / "table.csv"
    artifact.parent.mkdir()
    artifact.write_text("a,b\n1,2\n")
    manifest = artifact.parent / "manifest.json"
    manifest.write_text(json.dumps({"artifacts": {"evidence/table.csv": "stale"}}))
    monkeypatch.setattr(archive_evidence, "ROOT", tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["archive", "--manifest-only", "--evidence", str(artifact.parent)]
    )
    assert archive_evidence.main() == 0
    data = json.loads(manifest.read_text())
    assert (
        data["artifacts"]["evidence/table.csv"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    )
    assert data["source_revision"] == revision
    assert data["worktree_dirty"] is True  # evidence/ is untracked


def test_archive_command_copies_runs_only_when_not_manifest_only(tmp_path, monkeypatch):
    _git_repo(tmp_path)
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "manifest.json").write_text(json.dumps({"artifacts": {}}))
    calls = []
    monkeypatch.setattr(archive_evidence, "ROOT", tmp_path)
    monkeypatch.setattr(archive_evidence, "archive_real_runs", lambda *a: calls.append("real"))
    monkeypatch.setattr(archive_evidence, "archive_single_runs", lambda *a: calls.append("single"))
    argv = ["archive", "--results", str(tmp_path / "r"), "--evidence", str(evidence)]
    monkeypatch.setattr(sys, "argv", argv)
    assert archive_evidence.main() == 0
    assert calls == ["real", "single"]
    calls.clear()
    monkeypatch.setattr(sys, "argv", [*argv, "--manifest-only"])
    archive_evidence.main()
    assert calls == []


def test_archive_command_stops_on_a_missing_listed_artifact(tmp_path, monkeypatch):
    _git_repo(tmp_path)
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "manifest.json").write_text(json.dumps({"artifacts": {"gone.csv": "x"}}))
    monkeypatch.setattr(archive_evidence, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["archive", "--manifest-only", "--evidence", str(evidence)])
    with pytest.raises(FileNotFoundError):
        archive_evidence.main()
    assert "stale" not in (evidence / "manifest.json").read_text()


def test_profile_refresh_command_writes_the_profile_for_the_current_revision(tmp_path, monkeypatch):
    template = {"coverage": {"line": {}, "branch": {}, "per_unit": []}}
    coverage = {
        "totals": {
            "covered_lines": 3,
            "num_statements": 3,
            "covered_branches": 1,
            "num_branches": 1,
        },
        "files": {},
    }
    (tmp_path / "t.json").write_text(json.dumps(template))
    (tmp_path / "c.json").write_text(json.dumps(coverage))
    out = tmp_path / "deep" / "profile.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "refresh",
            "--coverage",
            str(tmp_path / "c.json"),
            "--template",
            str(tmp_path / "t.json"),
            "--output",
            str(out),
        ],
    )
    refresh_profile.main()
    profile = json.loads(out.read_text())
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert profile["source_revision"] == head
    assert profile["coverage"]["line"] == {"covered": 3, "coverable": 3}


def test_profile_refresh_command_rejects_a_missing_coverage_file(tmp_path, monkeypatch):
    (tmp_path / "t.json").write_text("{}")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "refresh",
            "--coverage",
            str(tmp_path / "none.json"),
            "--template",
            str(tmp_path / "t.json"),
            "--output",
            str(tmp_path / "o.json"),
        ],
    )
    with pytest.raises(OSError):
        refresh_profile.main()
    assert not (tmp_path / "o.json").exists()


def test_scaling_command_writes_csv_and_json_for_a_small_study(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scaling",
            "--sizes",
            "30",
            "--repeats",
            "1",
            "--methods",
            "isolation_forest",
            "--features",
            "3",
            "--results-dir",
            str(tmp_path),
        ],
    )
    scaling.main()
    record = json.loads((tmp_path / "scaling.json").read_text())
    assert [row["status"] for row in record["results"]] == ["PASS"]
    assert record["sizes"] == [30] and len(record["source_revision"]) == 40
    assert (tmp_path / "scaling.csv").read_text().startswith("method,")


def test_scaling_command_exits_nonzero_when_a_case_fails_but_still_records_it(
    tmp_path, monkeypatch
):
    class Broken:
        def fit(self, frame):
            raise RuntimeError("boom")

    monkeypatch.setitem(scaling.METHODS, "lof", Broken)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scaling",
            "--sizes",
            "30",
            "--repeats",
            "1",
            "--methods",
            "lof",
            "--results-dir",
            str(tmp_path),
        ],
    )
    with pytest.raises(SystemExit, match="scaling cases failed"):
        scaling.main()
    record = json.loads((tmp_path / "scaling.json").read_text())
    assert record["results"][0]["status"] == "FAIL" and "boom" in record["results"][0]["reason"]


@pytest.mark.parametrize("argv", [["--sizes", "10"], ["--repeats", "0"], ["--sizes", "9000"]])
def test_scaling_command_rejects_unbounded_or_tiny_studies(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["scaling", *argv])
    with pytest.raises(SystemExit) as stopped:
        scaling.main()
    assert stopped.value.code == 2


def test_collect_environment_reports_absent_packages_as_none(monkeypatch):
    monkeypatch.setattr(evidence_schema, "PACKAGES", ("numpy", "definitely-not-installed-xyz"))
    packages = evidence_schema.collect_environment()["packages"]
    assert packages["definitely-not-installed-xyz"] is None and packages["numpy"]


def test_a_fault_matrix_with_duplicate_rows_is_incomplete(tmp_path):
    doc = _matrix(tmp_path)
    doc["result"]["faults"].append(dict(doc["result"]["faults"][0]))
    doc["status"] = "PASS"
    assert any("status PASS" in p for p in evidence_schema.validate(doc))


def test_deep_stats_with_non_integer_counts_are_reported_as_malformed(tmp_path):
    doc = _deep(tmp_path)
    doc["result"]["stats"]["killed"] = 98.0
    problems = evidence_schema.validate(doc)
    assert any("malformed" in p or "status PASS" in p for p in problems)


def test_result_missing_its_fields_is_malformed_not_a_crash(tmp_path):
    doc = _fast(tmp_path)
    doc["result"] = {}
    assert any("malformed" in p for p in evidence_schema.validate(doc))


def test_archive_lineage_separates_legacy_records_from_broken_ones(tmp_path):
    good_v2 = {
        "fingerprint_recipe": 2,
        "scientific_fingerprint": __import__(
            "experiments.provenance", fromlist=["x"]
        ).scientific_fingerprint(),
    }
    (tmp_path / "run_new.json").write_text(json.dumps(good_v2))
    (tmp_path / "run_old.json").write_text(json.dumps({"source_fingerprint": "0" * 64}))
    result = release.archive_lineage(tmp_path)
    assert result["legacy"] == ["run_old"]
    assert "run_new" not in result["problems"]
    assert result["problems"]["run_old"]


def test_reference_hashes_read_the_manifest(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"datasets": {"a": {"sha256": "1" * 64}, "b": {}}})
    )
    assert release.reference_hashes(tmp_path) == {"a": "1" * 64, "b": None}


def test_release_command_certifies_nothing_on_an_unfinished_repository(tmp_path):
    assert ENVIRONMENT and SOURCE  # shared fixtures are importable
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "verification.release",
            "--evidence",
            str(tmp_path),
            "--output",
            str(tmp_path / "r.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 1
    assert json.loads((tmp_path / "r.json").read_text())["status"] != "CERTIFIED"


@pytest.mark.parametrize("module", ["archive_evidence", "refresh_profile", "scaling"])
def test_tools_run_as_modules_and_print_usage_on_help(module):
    done = subprocess.run(
        [sys.executable, "-m", f"verification.{module}", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0 and "usage:" in done.stdout


def test_run_case_rejects_unusable_workloads():
    for kwargs in (
        {"n_rows": 5, "n_features": 2, "fit_cap": None},
        {"n_rows": 30, "n_features": 0, "fit_cap": None},
        {"n_rows": 30, "n_features": 2, "fit_cap": 1},
    ):
        with pytest.raises(ValueError, match="usable"):
            scaling.run_case(scaling.METHODS["lof"], seed=1, **kwargs)
