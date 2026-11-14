# ruff: noqa: E501
"""Exact refusals, record detection, manifest text and command wiring of the evidence archiver."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

from verification import archive_evidence as ae


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def test_a_listed_output_that_is_not_on_disk_is_reported_by_its_path(tmp_path):
    record = tmp_path / "run_x_1.json"
    record.write_text(
        json.dumps({"outputs": ["gone.csv"], "output_sha256": {"gone.csv": "0" * 64}})
    )
    with pytest.raises(FileNotFoundError) as missing:
        ae.verify_run(record, tmp_path)
    assert missing.value.args == (tmp_path / "gone.csv",)


def test_a_record_without_hashes_or_with_an_unhashed_output_is_incomplete_with_its_reason(tmp_path):
    record = tmp_path / "run_x_1.json"
    record.write_text(json.dumps({"outputs": []}))
    with pytest.raises(ae.IncompleteRun) as bare:
        ae.verify_run(record, tmp_path)
    assert str(bare.value) == "run_x_1.json has no output_sha256: the run is not proven complete"
    record.write_text(json.dumps({"outputs": ["a.csv"], "output_sha256": {}}))
    with pytest.raises(ae.IncompleteRun) as unlisted:
        ae.verify_run(record, tmp_path)
    assert str(unlisted.value) == "run_x_1.json has no output_sha256 entry for a.csv"
    (tmp_path / "a.csv").write_text("changed")
    record.write_text(
        json.dumps({"outputs": ["a.csv"], "output_sha256": {"a.csv": _sha("original")}})
    )
    with pytest.raises(ae.IncompleteRun) as changed:
        ae.verify_run(record, tmp_path)
    assert str(changed.value) == "a.csv hash differs from run_x_1.json: partial or changed"


def test_the_newest_file_is_the_last_by_name_and_none_is_reported_with_pattern_and_folder(tmp_path):
    (tmp_path / "f_20260101_000001.csv").write_text("1")
    (tmp_path / "f_20260101_000002.csv").write_text("2")
    assert ae._newest(tmp_path, "f_*.csv").name == "f_20260101_000002.csv"
    with pytest.raises(FileNotFoundError) as none:
        ae._newest(tmp_path, "g_*.csv")
    assert str(none.value) == f"no file matches g_*.csv in {tmp_path}"


def test_a_missing_source_stops_the_copy_before_anything_is_written(tmp_path):
    present = tmp_path / "a.txt"
    present.write_text("a")
    with pytest.raises(FileNotFoundError) as missing:
        ae._copy_all([(present, tmp_path / "out_a"), (tmp_path / "none", tmp_path / "out_b")])
    assert missing.value.args == (tmp_path / "none",)
    assert not (tmp_path / "out_a").exists()
    assert not list(tmp_path.glob("*.tmp-*"))


def test_stable_names_drop_the_timestamp():
    assert ae._stable("benchmark_cardio_20260101_120000.csv") == "benchmark_cardio.csv"
    assert ae._stable("plain.csv") == "plain.csv"


def _single(results, name, text="x"):
    (results / name).write_text(text)


def test_a_json_that_is_not_a_run_record_is_archived_when_a_record_lists_it(tmp_path):
    results, evidence = tmp_path / "r", tmp_path / "e"
    results.mkdir()
    evidence.mkdir()
    _single(results, "data_1.json", '{"k": 1}')
    record = {"outputs": ["data_1.json"], "output_sha256": {"data_1.json": _sha('{"k": 1}')}}
    _single(results, "run_x_1.json", json.dumps(record))
    runs = [("run_x_*.json", "run_x.json"), ("data_*.json", "data.json")]
    ae.archive_single_runs(results, evidence, runs)
    assert (evidence / "data.json").read_text() == '{"k": 1}' and (
        evidence / "run_x.json"
    ).is_file()


def test_a_run_prefixed_file_that_is_not_json_is_not_a_record_and_must_be_listed(tmp_path):
    results, evidence = tmp_path / "r", tmp_path / "e"
    results.mkdir()
    evidence.mkdir()
    _single(results, "run_table_1.csv", "a,b\n")
    runs = [("run_table_*.csv", "run_table.csv")]
    with pytest.raises(ae.IncompleteRun) as unlisted:
        ae.archive_single_runs(results, evidence, runs)
    assert str(unlisted.value) == "run_table_1.csv is not listed by the newest run record"
    assert not (evidence / "run_table.csv").exists()


def test_a_listed_run_prefixed_csv_is_archived_without_being_read_as_a_record(tmp_path):
    results, evidence = tmp_path / "r", tmp_path / "e"
    results.mkdir()
    evidence.mkdir()
    _single(results, "run_table_1.csv", "a,b\n")
    record = {"outputs": ["run_table_1.csv"], "output_sha256": {"run_table_1.csv": _sha("a,b\n")}}
    _single(results, "run_y_1.json", json.dumps(record))
    runs = [("run_y_*.json", "run_y.json"), ("run_table_*.csv", "run_table.csv")]
    ae.archive_single_runs(results, evidence, runs)
    assert (evidence / "run_table.csv").read_text() == "a,b\n"


def test_the_manifest_is_rewritten_with_fresh_hashes_the_revision_and_the_dirty_flag(tmp_path):
    (tmp_path / "a.txt").write_text("alpha")
    (tmp_path / "é.txt").write_text("beta")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"artifacts": {"é.txt": "old", "a.txt": "old"}, "keep": "é"}))
    ae.refresh_manifest(manifest, tmp_path, revision="abc", dirty=True)
    text = manifest.read_text()
    document = json.loads(text)
    assert text == json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert "é" in text and "\\u00e9" not in text
    assert document["artifacts"] == {"a.txt": _sha("alpha"), "é.txt": _sha("beta")}
    assert (document["source_revision"], document["worktree_dirty"], document["keep"]) == (
        "abc",
        True,
        "é",
    )
    assert not list(tmp_path.glob("*.tmp-*"))


def test_a_missing_artifact_stops_the_refresh_and_leaves_the_manifest_alone(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"artifacts": {"gone.txt": "x"}}))
    before = manifest.read_text()
    with pytest.raises(FileNotFoundError):
        ae.refresh_manifest(manifest, tmp_path, revision="r", dirty=False)
    assert manifest.read_text() == before


@pytest.fixture
def wired(monkeypatch, tmp_path):
    seen = {"calls": []}
    monkeypatch.setattr(ae, "archive_real_runs", lambda *a: seen["calls"].append(("real", a)))
    monkeypatch.setattr(ae, "archive_single_runs", lambda *a: seen["calls"].append(("single", a)))
    monkeypatch.setattr(
        ae,
        "refresh_manifest",
        lambda manifest, root, **kw: seen["calls"].append(("manifest", manifest, root, kw)),
    )

    def git(*args):
        seen.setdefault("git", []).append(args)
        return "abc" if args[0] == "rev-parse" else " M x"

    monkeypatch.setattr(ae, "_git", git)
    return seen


def test_the_defaults_read_experiments_results_and_write_verification_evidence(monkeypatch, wired):
    monkeypatch.setattr(sys, "argv", ["archive"])
    assert ae.main() == 0
    results, evidence = ae.ROOT / "experiments" / "results", ae.ROOT / "verification" / "evidence"
    assert wired["calls"] == [
        ("real", (results, evidence)),
        ("single", (results, evidence)),
        ("manifest", evidence / "manifest.json", ae.ROOT, {"revision": "abc", "dirty": True}),
    ]
    assert wired["git"] == [("rev-parse", "HEAD"), ("status", "--porcelain")]
    assert all(isinstance(p, Path) for p in wired["calls"][0][1])


def test_the_options_choose_the_folders_and_manifest_only_skips_the_archiving(
    monkeypatch, wired, tmp_path
):
    argv = ["archive", "--results", str(tmp_path / "r"), "--evidence", str(tmp_path / "e")]
    monkeypatch.setattr(sys, "argv", argv)
    ae.main()
    assert wired["calls"][0] == ("real", (tmp_path / "r", tmp_path / "e"))
    wired["calls"].clear()
    monkeypatch.setattr(sys, "argv", [*argv, "--manifest-only"])
    ae.main()
    assert [call[0] for call in wired["calls"]] == ["manifest"]
    assert wired["calls"][0][1] == tmp_path / "e" / "manifest.json"


def test_a_clean_worktree_is_passed_as_not_dirty(monkeypatch, wired):
    monkeypatch.setattr(ae, "_git", lambda *args: "abc" if args[0] == "rev-parse" else "")
    monkeypatch.setattr(sys, "argv", ["archive", "--manifest-only"])
    ae.main()
    assert wired["calls"][0][3] == {"revision": "abc", "dirty": False}


def test_the_help_describes_the_archiver_and_its_options(monkeypatch, capsys):
    monkeypatch.setenv("COLUMNS", "300")
    monkeypatch.setattr(sys, "argv", ["archive", "--help"])
    with pytest.raises(SystemExit):
        ae.main()
    text = " ".join(capsys.readouterr().out.split())
    assert "Copy the latest experiment outputs into ``evidence/`` and refresh the manifest." in text
    assert (
        "--results RESULTS" in text and "--evidence EVIDENCE" in text and "--manifest-only" in text
    )
