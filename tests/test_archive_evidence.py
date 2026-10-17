import hashlib
import json

import pytest

from verification import archive_evidence


def _record(results, name, experiment, **fields):
    path = results / name
    hashes = {
        n: hashlib.sha256((results / n).read_bytes()).hexdigest()
        for n in fields.get("outputs", [])
        if (results / n).is_file()
    }
    path.write_text(json.dumps({"experiment": experiment, "output_sha256": hashes, **fields}))
    return path


def _benchmark(results, stamp, dataset, calibration):
    outputs = []
    for stem, suffix in (
        ("benchmark", ".csv"),
        ("benchmark", ".md"),
        ("split_ids", ".json.gz"),
    ):
        name = f"{stem}_{dataset}_{stamp}{suffix}"
        (results / name).write_text(f"{dataset} {stamp} {calibration}")
        outputs.append(name)
    _record(
        results,
        f"run_benchmark_{dataset}_{stamp}.json",
        "real_benchmark",
        dataset={"identity": dataset},
        settings={"calibration": calibration},
        outputs=outputs,
    )


def test_latest_run_of_each_calibration_gets_the_canonical_names(tmp_path):
    results, evidence = tmp_path / "results", tmp_path / "evidence"
    results.mkdir()
    evidence.mkdir()
    _benchmark(results, "20260101_000001", "cardio", "train_prevalence")
    _benchmark(results, "20260101_000002", "cardio", "fixed")
    _benchmark(results, "20260101_000003", "cardio", "train_prevalence")
    archive_evidence.archive_real_runs(results, evidence)
    names = sorted(path.name for path in evidence.iterdir())
    assert names == [
        "benchmark_cardio.csv",
        "benchmark_cardio.md",
        "fixed_benchmark_cardio.csv",
        "fixed_benchmark_cardio.md",
        "fixed_split_ids_cardio.json.gz",
        "run_benchmark_cardio.json",
        "run_fixed_benchmark_cardio.json",
        "split_ids_cardio.json.gz",
    ]
    assert (
        evidence / "benchmark_cardio.csv"
    ).read_text() == "cardio 20260101_000003 train_prevalence"
    assert (evidence / "fixed_benchmark_cardio.csv").read_text() == "cardio 20260101_000002 fixed"


def test_a_missing_output_stops_the_archive_instead_of_leaving_a_partial_copy(tmp_path):
    results, evidence = tmp_path / "results", tmp_path / "evidence"
    results.mkdir()
    evidence.mkdir()
    _benchmark(results, "20260101_000001", "cardio", "train_prevalence")
    (results / "benchmark_cardio_20260101_000001.md").unlink()
    with pytest.raises(FileNotFoundError):
        archive_evidence.archive_real_runs(results, evidence)
    assert not list(evidence.iterdir())


def test_single_runs_are_copied_under_their_fixed_names(tmp_path):
    results, evidence = tmp_path / "results", tmp_path / "evidence"
    results.mkdir()
    evidence.mkdir()
    (results / "severity_20260101_000001.csv").write_text("old")
    (results / "severity_20260101_000002.csv").write_text("new")
    _record(
        results,
        "run_severity_20260101_000002.json",
        "severity",
        outputs=["severity_20260101_000002.csv"],
    )
    runs = [("run_severity_*.json", "run_severity.json"), ("severity_*.csv", "severity.csv")]
    archive_evidence.archive_single_runs(results, evidence, runs)
    assert (evidence / "severity.csv").read_text() == "new"
    assert (evidence / "run_severity.json").is_file()
    with pytest.raises(FileNotFoundError):
        archive_evidence.archive_single_runs(results, evidence, [("absent_*.csv", "absent.csv")])


def test_every_kind_of_run_listed_for_the_thesis_has_a_distinct_target():
    targets = [name for _, name in archive_evidence.SINGLE_RUNS]
    assert len(targets) == len(set(targets))
    assert "synthetic.md" in targets and "contamination_sweep.csv" in targets


def test_manifest_refresh_rehashes_listed_artifacts_and_keeps_the_rest(tmp_path):
    (tmp_path / "a.txt").write_text("first")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"artifacts": {"a.txt": "stale"}, "datasets": {"d": 1}, "commands": {"c": "x"}})
    )
    archive_evidence.refresh_manifest(manifest, tmp_path, revision="abc", dirty=False)
    data = json.loads(manifest.read_text())
    assert data["artifacts"] == {"a.txt": hashlib.sha256(b"first").hexdigest()}
    assert data["datasets"] == {"d": 1} and data["commands"] == {"c": "x"}
    assert (data["source_revision"], data["worktree_dirty"]) == ("abc", False)
    (tmp_path / "a.txt").unlink()
    with pytest.raises(FileNotFoundError):
        archive_evidence.refresh_manifest(manifest, tmp_path, revision="abc", dirty=False)
