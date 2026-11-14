"""Behavioural contracts of the partition recovery command that the main tests leave open."""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import labelled_benchmark as lb  # noqa: E402
import normalise as nm  # noqa: E402
import recover_partitions as rp  # noqa: E402
from test_recover_partitions import _archive, _data, _run  # noqa: E402


def test_the_help_text_is_the_module_description(capsys):
    with pytest.raises(SystemExit) as stop:
        rp.main(["--help"])
    assert stop.value.code == 0
    assert "Recover the train/validation/test memberships" in capsys.readouterr().out


def test_the_output_directory_is_required():
    with pytest.raises(SystemExit) as stop:
        rp.main([])
    assert stop.value.code == 2


def test_the_archive_default_is_the_repository_labelled_pool_runs(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(lb, "jobs", lambda *a: [{"problem": "p:1", "source": "x"}])
    monkeypatch.setattr(Path, "is_file", lambda self: seen.setdefault("path", self) and False)
    rp.main(["--output", str(tmp_path / "o")])
    root = Path(rp.__file__).resolve().parents[1]
    assert seen["path"] == root / "verification/evidence/labelled_pool/runs" / "p_1.json"


def test_an_existing_output_directory_is_accepted_and_missing_parents_are_created(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(lb, "jobs", lambda *a: [])
    existing = tmp_path / "there"
    existing.mkdir()
    assert rp.main(["--output", str(existing)]) == 0
    assert rp.main(["--output", str(tmp_path / "a" / "b")]) == 0
    assert (tmp_path / "a" / "b").is_dir()


def test_a_problem_that_cannot_be_recovered_does_not_stop_the_following_ones(tmp_path, capsys):
    first = "adbench:annthyroid"
    code, output = _run(tmp_path, drop=first)
    lines = capsys.readouterr().out.splitlines()
    assert code == 1
    assert lines == [f"{first} no archived run", "uci:7 ok", "1 problems not confirmed"]
    assert (output / "uci_7.json").exists()

    (tmp_path / "failed").mkdir()
    code, output = _run(tmp_path / "failed", lambda p, a: {"failed": "x"} if p == first else a)
    lines = capsys.readouterr().out.splitlines()
    assert lines == [f"{first} archived run failed; not recoverable", "uci:7 ok",
                     "1 problems not confirmed"]  # fmt: skip


def test_every_unconfirmed_problem_is_counted_once(tmp_path, capsys):
    def edit(problem, archive):
        archive["metrics"]["zscore"][0]["f1"] += 1.0
        return archive

    code, _ = _run(tmp_path, edit)
    lines = capsys.readouterr().out.splitlines()
    assert code == 1 and lines[-1] == "2 problems not confirmed"
    (tmp_path / "mixed").mkdir()
    code, _ = _run(tmp_path / "mixed", edit, drop="uci:7")
    assert capsys.readouterr().out.splitlines()[-1] == "2 problems not confirmed"


def test_the_written_record_is_the_recovered_record_and_progress_is_flushed(tmp_path, monkeypatch):
    flushed = []
    monkeypatch.setattr(rp, "print", lambda *a, **k: flushed.append(k.get("flush")), raising=False)
    code, output = _run(tmp_path)
    written = json.loads((output / "uci_7.json").read_text())
    assert written["problem"] == "uci:7" and written["format"] == 1
    assert written["archive_replay"]["all"] is True
    assert flushed[:2] == [True, True]


def _fake_loader(rows_out=7):
    x = np.arange(40, dtype=float).reshape(20, 2)
    y = np.array([0.0, 1.0] * 10)
    return x, y, {"rows_out": rows_out}


def test_the_record_carries_the_report_row_count_and_integer_label_digest(monkeypatch, tmp_path):
    seen = {}

    def load(name, path):
        seen["args"] = (name, path)
        return _fake_loader()

    monkeypatch.setattr(lb, "load_adbench", load)
    monkeypatch.setattr(rp, "replay_matches", lambda x, y, a: [True])
    source = tmp_path / "data.npz"
    source.write_bytes(b"abc")
    job = {"problem": "adbench:n", "source": "adbench", "name": "n", "path": str(source)}
    record = rp.recover(job, {"seeds": [1], "rows": 20})
    assert seen["args"] == ("n", source)
    assert record["report_rows_out"] == 7
    labels = np.array([0, 1] * 10, dtype=np.int64)
    assert record["labels_sha256"] == hashlib.sha256(labels.tobytes()).hexdigest()
    assert "report_rows_out" in record and "XXreport_rows_outXX" not in record
    assert set(record) == {
        "format", "problem", "source", "recovery", "input_sha256", "cleaned_rows",
        "cleaned_sha256", "labels_sha256", "seeds", "partitions", "archived_rows",
        "archive_replay", "report_rows_out",
    }  # fmt: skip


def test_partition_digests_use_64_bit_indices_whatever_the_split_returns(monkeypatch):
    x, y = _data()
    expected = rp.partitions(x, y, (7,))
    real = nm.split

    def narrow(x, y, seed):
        part = real(x, y, seed)
        return {k: (v.astype(np.int32) if k.startswith("idx_") else v) for k, v in part.items()}

    monkeypatch.setattr(nm, "split", narrow)
    assert rp.partitions(x, y, (7,)) == expected


def test_the_replay_asks_only_for_the_zscore_detector_and_requires_one_row_per_seed(monkeypatch):
    x, y = _data()
    archive = _archive(x, y)
    calls = []
    real = lb.run_problem

    def spy(x, y, seeds, methods=None):
        calls.append(methods)
        return real(x, y, seeds=seeds, methods=methods)

    monkeypatch.setattr(lb, "run_problem", spy)
    assert rp.replay_matches(x, y, archive) == [True, True]
    assert calls == [["zscore"]]

    monkeypatch.setattr(
        lb, "run_problem", lambda *a, **k: {"metrics": {"zscore": archive["metrics"]["zscore"][:1]}}
    )
    with pytest.raises(ValueError):
        rp.replay_matches(x, y, archive)


def test_a_difference_exactly_at_the_tolerance_still_matches():
    assert rp._same({"a": 0.0}, {"a": rp.TOLERANCE}) is True
    assert rp._same({"a": 0.0}, {"a": 2 * rp.TOLERANCE}) is False
