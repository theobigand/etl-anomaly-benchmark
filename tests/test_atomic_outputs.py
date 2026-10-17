"""An interrupted or incomplete run must never look like a finished experiment."""

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import provenance  # noqa: E402

from verification import archive_evidence  # noqa: E402


def _record(directory, name="run_x.json", outputs=("a.csv",), **extra):
    args = {
        "experiment": "e",
        "seeds": [1],
        "dataset": "d",
        "data_path": None,
        "settings": {},
        "outputs": list(outputs),
    }
    args.update(extra)
    return provenance.write_record(directory / name, **args)


@pytest.fixture(autouse=True)
def _fixed_source(monkeypatch):
    monkeypatch.setattr(provenance, "_git", lambda *a: "")
    monkeypatch.setattr(provenance, "scientific_fingerprint", lambda: "f" * 64)
    monkeypatch.setattr(provenance, "measurement_fingerprint", lambda: "m" * 64)
    monkeypatch.setattr(provenance, "_source_fingerprint", lambda: "s" * 64)


# --- the record is the completion marker ---


def test_the_record_hashes_every_output_it_lists(tmp_path):
    (tmp_path / "a.csv").write_text("x\n1\n")
    (tmp_path / "split.json.gz").write_bytes(b"abc")
    record = json.loads(_record(tmp_path, outputs=("a.csv", "split.json.gz")).read_text())
    assert record["output_sha256"] == {
        "a.csv": hashlib.sha256(b"x\n1\n").hexdigest(),
        "split.json.gz": hashlib.sha256(b"abc").hexdigest(),
    }


def test_an_output_outside_the_results_directory_is_hashed_by_its_path(tmp_path):
    figure = tmp_path / "paper" / "fig.png"
    figure.parent.mkdir()
    figure.write_bytes(b"png")
    results = tmp_path / "results"
    results.mkdir()
    record = json.loads(_record(results, outputs=(str(figure),)).read_text())
    assert record["output_sha256"] == {str(figure): hashlib.sha256(b"png").hexdigest()}


def test_a_listed_output_that_does_not_exist_prevents_the_record(tmp_path):
    (tmp_path / "a.csv").write_text("1")
    with pytest.raises(FileNotFoundError, match="b.csv"):
        _record(tmp_path, outputs=("a.csv", "b.csv"))
    assert not (tmp_path / "run_x.json").exists()
    assert list(tmp_path.glob("*.tmp*")) == []


def test_an_empty_listed_output_prevents_the_record(tmp_path):
    (tmp_path / "a.csv").write_text("")
    with pytest.raises(ValueError, match="empty"):
        _record(tmp_path)
    assert not (tmp_path / "run_x.json").exists()


def test_an_interrupted_write_keeps_the_previous_valid_record(tmp_path, monkeypatch):
    (tmp_path / "a.csv").write_text("old")
    first = _record(tmp_path)
    before = first.read_text()
    (tmp_path / "a.csv").write_text("new")

    def interrupted(source, target):
        raise OSError("disk full")

    monkeypatch.setattr(provenance.os, "replace", interrupted)
    with pytest.raises(OSError, match="disk full"):
        _record(tmp_path)
    assert first.read_text() == before
    assert list(tmp_path.glob("*.tmp*")) == []


def test_a_crash_while_serialising_leaves_no_partial_record(tmp_path, monkeypatch):
    (tmp_path / "a.csv").write_text("1")

    def broken(*args, **kwargs):
        raise RuntimeError("serialiser died")

    monkeypatch.setattr(provenance.json, "dumps", broken)
    with pytest.raises(RuntimeError):
        _record(tmp_path)
    assert list(tmp_path.iterdir()) == [tmp_path / "a.csv"]


def test_a_read_only_destination_prevents_the_record(tmp_path, monkeypatch):
    out = tmp_path / "ro"
    out.mkdir()
    (out / "a.csv").write_text("1")
    real = Path.open

    def refuse(self, *args, **kwargs):
        if ".tmp-" in self.name:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", refuse)
    with pytest.raises(PermissionError):
        _record(out)
    monkeypatch.undo()
    assert sorted(p.name for p in out.iterdir()) == ["a.csv"]


def test_the_record_is_written_through_a_temporary_file_in_the_same_directory(
    tmp_path, monkeypatch
):
    (tmp_path / "a.csv").write_text("1")
    seen = []
    real = os.replace
    monkeypatch.setattr(
        provenance.os,
        "replace",
        lambda source, target: (seen.append((source, target)), real(source, target))[1],
    )
    _record(tmp_path)
    ((source, target),) = seen
    assert Path(target) == tmp_path / "run_x.json"
    assert Path(source).parent == tmp_path and Path(source) != Path(target)


# --- the archive refuses incomplete or inconsistent runs ---


def _benchmark(results, stamp="20260101_000001", dataset="cardio", hashes=True, content=None):
    names = [f"benchmark_{dataset}_{stamp}.csv", f"split_ids_{dataset}_{stamp}.json.gz"]
    for name in names:
        (results / name).write_text(content or f"{dataset} {stamp}")
    record = {
        "experiment": "real_benchmark",
        "dataset": {"identity": dataset},
        "settings": {"calibration": "train_prevalence"},
        "outputs": names,
    }
    if hashes:
        record["output_sha256"] = {
            n: hashlib.sha256((results / n).read_bytes()).hexdigest() for n in names
        }
    (results / f"run_benchmark_{dataset}_{stamp}.json").write_text(json.dumps(record))
    return names


def _dirs(tmp_path):
    results, evidence = tmp_path / "results", tmp_path / "evidence"
    results.mkdir()
    evidence.mkdir()
    return results, evidence


def test_a_complete_hashed_run_is_archived(tmp_path):
    results, evidence = _dirs(tmp_path)
    _benchmark(results)
    archive_evidence.archive_real_runs(results, evidence)
    assert (evidence / "benchmark_cardio.csv").read_text() == "cardio 20260101_000001"


def test_a_record_without_output_hashes_is_not_archived(tmp_path):
    results, evidence = _dirs(tmp_path)
    _benchmark(results, hashes=False)
    with pytest.raises(archive_evidence.IncompleteRun, match="output_sha256"):
        archive_evidence.archive_real_runs(results, evidence)
    assert list(evidence.iterdir()) == []


def test_an_output_changed_after_the_record_is_not_archived(tmp_path):
    results, evidence = _dirs(tmp_path)
    names = _benchmark(results)
    (results / names[0]).write_text("truncated")
    with pytest.raises(archive_evidence.IncompleteRun, match="hash"):
        archive_evidence.archive_real_runs(results, evidence)
    assert list(evidence.iterdir()) == []


def test_a_failed_copy_leaves_previously_archived_files_untouched(tmp_path, monkeypatch):
    results, evidence = _dirs(tmp_path)
    _benchmark(results)
    (evidence / "benchmark_cardio.csv").write_text("previous")
    real = archive_evidence.shutil.copyfile
    calls = []

    def flaky(source, target, **kwargs):
        calls.append(target)
        if len(calls) == 2:
            raise OSError("no space left")
        return real(source, target, **kwargs)

    monkeypatch.setattr(archive_evidence.shutil, "copyfile", flaky)
    with pytest.raises(OSError, match="no space"):
        archive_evidence.archive_real_runs(results, evidence)
    assert (evidence / "benchmark_cardio.csv").read_text() == "previous"
    assert sorted(p.name for p in evidence.iterdir()) == ["benchmark_cardio.csv"]


def test_single_runs_come_from_the_newest_complete_record_not_from_a_newer_orphan_file(tmp_path):
    results, evidence = _dirs(tmp_path)
    old = results / "severity_20260101_000001.csv"
    old.write_text("complete")
    record = {
        "experiment": "severity",
        "outputs": [old.name],
        "output_sha256": {old.name: hashlib.sha256(b"complete").hexdigest()},
    }
    (results / "run_severity_20260101_000001.json").write_text(json.dumps(record))
    (results / "severity_20260101_000002.csv").write_text("half written")
    runs = [("run_severity_*.json", "run_severity.json"), ("severity_*.csv", "severity.csv")]
    with pytest.raises(archive_evidence.IncompleteRun, match="not listed"):
        archive_evidence.archive_single_runs(results, evidence, runs)
    assert list(evidence.iterdir()) == []


def test_single_runs_with_a_matching_record_are_archived(tmp_path):
    results, evidence = _dirs(tmp_path)
    csv = results / "severity_20260101_000002.csv"
    csv.write_text("new")
    record = {
        "experiment": "severity",
        "outputs": [csv.name],
        "output_sha256": {csv.name: hashlib.sha256(b"new").hexdigest()},
    }
    (results / "run_severity_20260101_000002.json").write_text(json.dumps(record))
    runs = [("run_severity_*.json", "run_severity.json"), ("severity_*.csv", "severity.csv")]
    archive_evidence.archive_single_runs(results, evidence, runs)
    assert (evidence / "severity.csv").read_text() == "new"


def test_the_manifest_is_replaced_atomically(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("first")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"artifacts": {"a.txt": "stale"}}))
    before = manifest.read_text()

    def interrupted(source, target):
        raise OSError("interrupted")

    monkeypatch.setattr(archive_evidence.os, "replace", interrupted)
    with pytest.raises(OSError):
        archive_evidence.refresh_manifest(manifest, tmp_path, revision="abc", dirty=False)
    assert manifest.read_text() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.txt", "manifest.json"]


# --- the real script, end to end ---


def _run_script(monkeypatch, tmp_path, results):
    import run_benchmark

    from tests.test_script_outputs_benchmark import _argv, _toy

    csv = _toy(tmp_path)
    _argv(
        monkeypatch,
        *("--dataset", "credit_card", "--csv", csv, "--detectors", "zscore", "iqr"),
        *("--seeds", 1, 2, "--results-dir", results),
    )
    run_benchmark.main()


def test_a_script_that_dies_before_the_record_is_never_archived(tmp_path, monkeypatch):
    import run_benchmark

    def dies(*args, **kwargs):
        raise RuntimeError("killed before the record")

    monkeypatch.setattr(run_benchmark, "write_record", dies)
    results, evidence = tmp_path / "results", tmp_path / "evidence"
    evidence.mkdir()
    with pytest.raises(RuntimeError):
        _run_script(monkeypatch, tmp_path, results)
    assert list(results.glob("benchmark_*.csv")), "the table was written"
    assert list(results.glob("run_benchmark_*.json")) == []
    with pytest.raises(archive_evidence.IncompleteRun, match="no run record"):
        archive_evidence.archive_real_runs(results, evidence)
    assert list(evidence.iterdir()) == []


def test_a_finished_script_run_is_proven_complete_and_archives(tmp_path, monkeypatch):
    results, evidence = tmp_path / "results", tmp_path / "evidence"
    evidence.mkdir()
    _run_script(monkeypatch, tmp_path, results)
    (record_path,) = results.glob("run_benchmark_*.json")
    record = json.loads(record_path.read_text())
    assert set(record["output_sha256"]) == set(record["outputs"]) and len(record["outputs"]) == 3
    archive_evidence.archive_real_runs(results, evidence)
    assert (evidence / "benchmark_credit_card.csv").is_file()


def test_a_table_truncated_after_the_record_is_refused(tmp_path, monkeypatch):
    results, evidence = tmp_path / "results", tmp_path / "evidence"
    evidence.mkdir()
    _run_script(monkeypatch, tmp_path, results)
    table = next(results.glob("benchmark_*.csv"))
    table.write_text(table.read_text()[:20])
    with pytest.raises(archive_evidence.IncompleteRun, match="hash"):
        archive_evidence.archive_real_runs(results, evidence)


def test_a_record_that_does_not_hash_one_of_its_outputs_is_refused(tmp_path):
    results, evidence = _dirs(tmp_path)
    names = _benchmark(results)
    path = next(results.glob("run_benchmark_*.json"))
    record = json.loads(path.read_text())
    del record["output_sha256"][names[1]]
    path.write_text(json.dumps(record))
    with pytest.raises(archive_evidence.IncompleteRun, match=names[1]):
        archive_evidence.archive_real_runs(results, evidence)


def test_an_output_that_vanished_after_the_record_is_refused(tmp_path):
    results, evidence = _dirs(tmp_path)
    names = _benchmark(results)
    (results / names[0]).unlink()
    with pytest.raises(FileNotFoundError):
        archive_evidence.archive_real_runs(results, evidence)
    assert list(evidence.iterdir()) == []


def test_archiving_a_chosen_file_that_vanished_before_the_copy_stops_without_a_trace(tmp_path):
    source = tmp_path / "gone.csv"
    with pytest.raises(FileNotFoundError):
        archive_evidence._copy_all([(source, tmp_path / "target.csv")])
    assert list(tmp_path.iterdir()) == []
