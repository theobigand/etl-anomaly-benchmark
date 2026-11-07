"""Recovered memberships are deterministic, complete, bound to their inputs and replay-checked."""

import copy
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
from test_pipeline_entry_points import FILE, NAME, _pool  # noqa: E402


def _data(n=300, anomalies=30):
    rng = np.random.default_rng(3)
    x = rng.normal(size=(n, 4))
    y = np.zeros(n, dtype=int)
    y[::10] = 1
    x[y == 1] += 4
    return x, y


def test_the_split_exposes_the_validation_and_test_rows_beside_the_training_rows():
    x, y = _data()
    part = nm.split(x, y, 7)
    rows = np.concatenate([part["idx_train"], part["idx_val"], part["idx_test"]])
    assert sorted(rows.tolist()) == list(range(len(y)))
    assert np.array_equal(part["y_test"], y[part["idx_test"]])
    assert np.array_equal(part["y_val"], y[part["idx_val"]])


def test_partition_records_hold_sizes_prevalence_and_digests_for_every_seed():
    x, y = _data()
    record = rp.partitions(x, y, (7, 8))
    assert list(record) == ["7", "8"]
    part = nm.split(x, y, 7)
    for name in ("train", "val", "test"):
        rows = np.asarray(part[f"idx_{name}"], dtype=np.int64)
        item = record["7"][name]
        assert item["rows"] == len(rows) and item["anomalies"] == int(y[rows].sum())
        assert item["prevalence"] == pytest.approx(y[rows].mean())
        assert item["sha256"] == hashlib.sha256(rows.tobytes()).hexdigest()
    assert sum(record["7"][name]["rows"] for name in ("train", "val", "test")) == len(y)
    assert record["7"]["train"]["sha256"] != record["8"]["train"]["sha256"]
    assert rp.partitions(x, y, (7,)) == {"7": record["7"]}


def _archive(x, y, seeds=(42, 1)):
    return {
        "seeds": list(seeds),
        "metrics": lb.run_problem(x, y, seeds=seeds, methods=["zscore"])["metrics"],
        "rows": len(y),
    }


def test_the_replay_confirms_an_archive_made_by_the_same_split_and_rejects_a_changed_one():
    x, y = _data()
    archive = _archive(x, y)
    assert rp.replay_matches(x, y, archive) == [True, True]
    changed = copy.deepcopy(archive)
    changed["metrics"]["zscore"][1]["f1"] += 1e-6
    assert rp.replay_matches(x, y, changed) == [True, False]
    tiny = copy.deepcopy(archive)
    tiny["metrics"]["zscore"][0]["f1"] += 1e-12
    assert rp.replay_matches(x, y, tiny)[0] is True


def test_an_archive_without_one_row_per_seed_is_never_confirmed():
    x, y = _data()
    archive = _archive(x, y)
    archive["metrics"]["zscore"] = archive["metrics"]["zscore"][:1]
    assert rp.replay_matches(x, y, archive) == [False, False]
    archive["metrics"] = {}
    assert rp.replay_matches(x, y, archive) == [False, False]
    assert rp._same({"a": 1.0}, {"a": 1.0, "b": 2.0}) is False
    assert rp._same({"a": 1.0}, {"a": 1.0 + 1e-6}) is False


def test_a_recovered_record_binds_the_source_the_cleaned_table_and_the_split(tmp_path):
    registry, adbench, pool = _pool(tmp_path)
    job = lb.jobs(registry, adbench, pool)[0]
    x, y, _ = lb.load_adbench(NAME, adbench / FILE)
    record = rp.recover(job, _archive(x, y, (42, 1)))
    assert record["format"] == 1 and record["problem"] == f"adbench:{NAME}"
    assert record["recovery"].startswith("recomputed")
    assert record["input_sha256"] == hashlib.sha256((adbench / FILE).read_bytes()).hexdigest()
    assert record["cleaned_rows"] == len(y) == record["archived_rows"]
    assert record["cleaned_sha256"] == rp._digest(x) and record["labels_sha256"] == rp._digest(y)
    assert record["seeds"] == [42, 1] and record["partitions"] == rp.partitions(x, y, (42, 1))
    assert record["archive_replay"] == {
        "detector": "zscore",
        "seeds_matching": [True, True],
        "all": True,
    }


def test_a_uci_problem_is_recovered_through_its_metadata(tmp_path):
    registry, adbench, pool = _pool(tmp_path)
    job = lb.jobs(registry, adbench, pool)[1]
    x, y, _ = lb.load_uci(job["meta"], Path(job["path"]))
    record = rp.recover(job, _archive(x, y, (42,)))
    assert record["source"] == "uci" and record["archive_replay"]["all"] is True


def _run(tmp_path, archive_edit=None, drop=None):
    registry, adbench, pool = _pool(tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    for job in lb.jobs(registry, adbench, pool):
        loader = lb.load_adbench if job["source"] == "adbench" else lb.load_uci
        arguments = (
            (job["name"], Path(job["path"]))
            if job["source"] == "adbench"
            else (job["meta"], Path(job["path"]))
        )  # noqa: E501
        x, y, _ = loader(*arguments)
        archive = _archive(x, y, (42, 1))
        stem = job["problem"].replace(":", "_")
        if archive_edit:
            archive = archive_edit(job["problem"], archive)
        if drop != job["problem"]:
            (runs / f"{stem}.json").write_text(json.dumps(archive))
    output = tmp_path / "out" / "nested"
    code = rp.main(["--registry", str(registry), "--adbench", str(adbench), "--pool", str(pool),
                    "--archive", str(runs), "--output", str(output)])  # fmt: skip
    return code, output


def test_the_command_writes_one_record_per_problem_and_succeeds_when_all_replays_match(
    tmp_path, capsys
):
    code, output = _run(tmp_path)
    assert code == 0
    assert sorted(path.name for path in output.iterdir()) == [
        "adbench_annthyroid.json",
        "uci_7.json",
    ]
    text = (output / "uci_7.json").read_text()
    assert text == json.dumps(json.loads(text), indent=1, sort_keys=True) + "\n"
    assert capsys.readouterr().out.splitlines() == [
        "adbench:annthyroid ok", "uci:7 ok", "0 problems not confirmed",
    ]  # fmt: skip


def test_a_replay_that_differs_is_flagged_and_fails_the_command(tmp_path, capsys):
    def edit(problem, archive):
        if problem == "uci:7":
            archive["metrics"]["zscore"][0]["recall"] = 0.0
        return archive

    code, output = _run(tmp_path, edit)
    lines = capsys.readouterr().out.splitlines()
    assert code == 1 and "uci:7 REPLAY DIFFERS" in lines and lines[-1] == "1 problems not confirmed"
    assert (output / "uci_7.json").exists()


def test_a_problem_without_a_usable_archive_is_reported_and_not_recovered(tmp_path, capsys):
    code, output = _run(tmp_path, drop="uci:7")
    lines = capsys.readouterr().out.splitlines()
    assert code == 1 and "uci:7 no archived run" in lines
    assert not (output / "uci_7.json").exists()

    (tmp_path / "again").mkdir()
    code, output = _run(tmp_path / "again", lambda p, a: {"failed": "boom"} if p == "uci:7" else a)
    lines = capsys.readouterr().out.splitlines()
    assert code == 1 and "uci:7 archived run failed; not recoverable" in lines
    assert not (output / "uci_7.json").exists()


def test_the_command_defaults_point_at_the_repository_evidence(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(lb, "jobs", lambda registry, adbench, pool: seen.update(
        paths=(registry, adbench, pool)) or [])  # fmt: skip
    root = Path(__file__).resolve().parents[2]
    assert rp.main(["--output", str(tmp_path / "o")]) == 0
    assert seen["paths"] == (
        root / "verification/evidence/dataset_registry",
        root / "data" / "adbench",
        root / "data" / "pool",
    )
    assert rp.TOLERANCE == 1e-9
