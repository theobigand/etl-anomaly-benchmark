"""Train-only statistics for the typed injection and its paired comparison with the archive."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
import injection as inj  # noqa: E402
import typed_benchmark as tb  # noqa: E402

from research import typed_train_only as tt  # noqa: E402


def _carrier(n=3000):
    rng = np.random.default_rng(0)
    a = rng.normal(50, 10, n)
    return pd.DataFrame(
        {"a": a, "b": 0.8 * a + rng.normal(0, 4, n), "c": rng.gamma(4, 5, n), "d": rng.normal(0, 1, n)}
    )


def test_the_reference_is_made_of_unmodified_training_rows_only():
    carrier = _carrier()
    reference = tt.train_reference(carrier, seed=1)
    layout = inj.inject(carrier, seed=1)
    train, _val, test = tb.split(layout, 1)
    clean_train = train[train["anomaly_type"] == "clean"]
    assert len(reference) == len(clean_train) and 0 < len(reference) < len(carrier)
    assert list(reference.columns) == list(carrier.columns)
    assert reference.sum().sum() == pytest.approx(clean_train[list(carrier.columns)].sum().sum())
    held_out = test[test["anomaly_type"] == "clean"][list(carrier.columns)]
    assert not reference.merge(held_out).shape[0]


def test_train_only_injection_keeps_layout_and_partitions_but_changes_the_fault_values():
    carrier = _carrier()
    default = inj.inject(carrier, seed=2)
    frame = tt.inject_train_only(carrier, seed=2)
    keys = ["group_id", "anomaly_type", "t"]
    assert frame[keys].equals(default[keys])
    cols = list(carrier.columns)
    assert not frame[cols].equals(default[cols])
    unchanged = frame["anomaly_type"] == "clean"
    assert frame.loc[unchanged, cols].equals(default.loc[unchanged, cols])


def test_a_reference_that_moves_the_partitions_is_rejected(monkeypatch):
    carrier = _carrier()
    real = inj.inject

    def shifted(clean, seed, **kwargs):
        out = real(clean, seed, **kwargs)
        if "reference" in kwargs:
            out["group_id"] = out["group_id"].iloc[::-1].to_numpy()
        return out

    monkeypatch.setattr(tt.inj, "inject", shifted)
    with pytest.raises(AssertionError, match="layout"):
        tt.inject_train_only(carrier, seed=2)


def _result(uci_id, values):
    frame = pd.DataFrame(values, index=["m1", "m2"], columns=["missing_value", "duplicate"])
    return {"uci_id": uci_id, "recall_mean": json.loads(frame.to_json(orient="split"))}


def test_the_comparison_pairs_carriers_and_reports_replay_minus_archive():
    archive = {i: _result(i, [[0.5, 0.5], [0.2, 0.2]]) for i in (1, 2, 3)}
    replay = {
        1: _result(1, [[0.6, 0.5], [0.2, 0.0]]),
        2: _result(2, [[0.6, 0.5], [0.2, 0.0]]),
        3: _result(3, [[0.6, 0.5], [0.2, 0.0]]),
        9: _result(9, [[0.0, 0.0], [0.0, 0.0]]),  # no archived counterpart
    }
    out = tt.compare(archive, replay)
    cells = {(c["method"], c["type"]): c for c in out["cells"]}
    assert out["carriers"] == 3 and len(cells) == 4
    assert cells[("m1", "missing_value")]["median_difference"] == pytest.approx(0.1)
    assert cells[("m2", "duplicate")]["mean_difference"] == pytest.approx(-0.2)
    assert cells[("m1", "duplicate")]["median_difference"] == 0.0
    assert cells[("m1", "missing_value")]["share_over_0.1"] == 0.0  # 0.1 is not above 0.1 ...
    assert cells[("m2", "duplicate")]["share_over_0.1"] == 1.0
    assert cells[("m1", "missing_value")]["ci_low"] == pytest.approx(0.1)
    assert cells[("m1", "missing_value")]["ci_high"] == pytest.approx(0.1)
    assert out["bootstrap"] == {"draws": 2000, "seed": 0}


def test_the_comparison_needs_a_carrier_in_both_archives():
    with pytest.raises(ValueError, match="common"):
        tt.compare({1: _result(1, [[0, 0], [0, 0]])}, {2: _result(2, [[0, 0], [0, 0]])})


def test_runs_are_loaded_by_uci_id(tmp_path):
    (tmp_path / "7.json").write_text(json.dumps(_result(7, [[0, 0], [0, 0]])))
    assert list(tt.load_runs(tmp_path)) == [7]


def test_run_one_averages_the_five_seeds_and_records_the_protocol(monkeypatch, tmp_path):
    carrier = _carrier()
    seen = []

    def fake_evaluate(df, cols, seed, names):
        seen.append(seed)
        recall = pd.DataFrame({t: [float(seed)] for t in inj.ANOMALY_TYPES}, index=["m"])
        return {"recall": recall, "precision": recall / 2, "fpr": pd.Series({"m": 0.1 * seed})}

    monkeypatch.setattr(tb, "evaluate", fake_evaluate)
    monkeypatch.setattr(tt.tr, "load_carrier", lambda meta, path, seed: (carrier, {"rows_out": 3000}))
    out = tt.run_one(({"uci_id": 5, "name": "x"}, str(tmp_path), "abc"))
    assert seen == [42, 1, 2, 3, 4] and out["protocol"] == tt.PROTOCOL
    assert out["recall_mean"]["data"][0][0] == pytest.approx(np.mean([42, 1, 2, 3, 4]))
    assert out["precision_mean"]["data"][0][0] == pytest.approx(np.mean([42, 1, 2, 3, 4]) / 2)
    assert out["fpr_mean"]["m"] == pytest.approx(0.1 * np.mean([42, 1, 2, 3, 4]))
    assert out["uci_id"] == 5 and out["sha256"] == "abc" and out["seeds"] == [42, 1, 2, 3, 4]


def test_the_command_compares_two_run_directories(tmp_path):
    archive, runs = tmp_path / "archive", tmp_path / "out" / "runs"
    archive.mkdir()
    runs.mkdir(parents=True)
    for directory in (archive, runs):
        (directory / "1.json").write_text(json.dumps(_result(1, [[0.5, 0.5], [0.2, 0.2]])))
    assert tt.main(["--output", str(runs), "--compare", str(archive)]) == 0
    report = json.loads((runs.parent / "comparison_classical.json").read_text())
    assert report["carriers"] == 1 and report["protocol"] == tt.PROTOCOL


def test_runs_are_keyed_by_uci_id_or_by_the_adbench_identifier(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"id": "adbench:cover", **_result(0, [[0, 0], [0, 0]])} | {"uci_id": None}))
    (tmp_path / "b.json").write_text(json.dumps({"id": "adbench:wilt", "recall_mean": _result(0, [[0, 0], [0, 0]])["recall_mean"]}))
    assert sorted(tt.load_runs(tmp_path)) == ["adbench:cover", "adbench:wilt"]


def test_an_adbench_job_is_averaged_over_the_seeds_with_its_identifier(monkeypatch):
    carrier = _carrier()
    monkeypatch.setattr(tt.pt, "load_carrier", lambda job: (carrier, {"rows_out": 3000}))

    def fake_evaluate(df, cols, seed, names):
        recall = pd.DataFrame({t: [float(seed)] for t in inj.ANOMALY_TYPES}, index=["m"])
        return {"recall": recall, "precision": recall, "fpr": pd.Series({"m": 0.1})}

    monkeypatch.setattr(tb, "evaluate", fake_evaluate)
    out = tt.run_adbench({"id": "adbench:cover", "name": "cover", "source": "adbench"})
    assert out["id"] == "adbench:cover" and out["protocol"] == tt.PROTOCOL
    assert out["recall_mean"]["data"][0][0] == pytest.approx(np.mean([42, 1, 2, 3, 4]))


class _Pool:
    """A synchronous stand-in for the process pool that records how it was built."""

    made: list = []

    def __init__(self, max_workers):
        type(self).made.append(max_workers)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def map(self, fn, items):
        return [fn(item) for item in items]


@pytest.fixture
def pool(monkeypatch):
    _Pool.made = []
    monkeypatch.setattr(tt, "ProcessPoolExecutor", _Pool)
    return _Pool


def _uci_jobs():
    return [({"uci_id": i, "name": f"t{i}"}, f"/p/{i}.csv", f"d{i}") for i in (1, 2, 3)]


def test_the_uci_replay_writes_one_file_per_carrier_and_reports_the_count(pool, monkeypatch, tmp_path, capsys):
    seen = {}
    monkeypatch.setattr(tt.tr, "jobs", lambda *a: seen.setdefault("args", a) and _uci_jobs())
    monkeypatch.setattr(tt, "run_one", lambda job, names=None: {"uci_id": job[0]["uci_id"], "name": job[0]["name"], "names": names})
    out = tmp_path / "runs"
    assert tt.main(["--output", str(out), "--workers", "7"]) == 0
    assert sorted(p.name for p in out.glob("*.json")) == ["1.json", "2.json", "3.json"]
    assert json.loads((out / "2.json").read_text())["names"] is None
    assert capsys.readouterr().out.splitlines() == ["t1", "t2", "t3", "3 datasets"]
    assert pool.made == [7]
    registry = tt.HERE.parent / "verification" / "evidence" / "dataset_registry"
    assert seen["args"] == (registry / "uci_curated.json", registry / "uci_pool.json", tt.HERE.parent / "data" / "pool")
    assert (out / "1.json").read_text().endswith("}\n")


def test_the_uci_replay_selects_by_id_resumes_and_passes_the_neural_names(pool, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(tt.tr, "jobs", lambda *a: _uci_jobs())
    monkeypatch.setattr(tt, "run_one", lambda job, names=None: {"uci_id": job[0]["uci_id"], "name": job[0]["name"], "names": names})
    out = tmp_path / "runs"
    assert tt.main(["--output", str(out), "--only", "2", "3", "--methods", "deep"]) == 0
    assert json.loads((out / "2.json").read_text())["names"] == list(tt.DEEP_NAMES)
    assert not (out / "1.json").exists() and pool.made == [4]
    capsys.readouterr()
    assert tt.main(["--output", str(out), "--resume"]) == 0
    assert capsys.readouterr().out.splitlines() == ["t1", "1 datasets"]


def _adbench_jobs():
    return [
        {"id": "uci:9", "source": "uci", "name": "u"},
        {"id": "adbench:cover", "source": "adbench", "name": "cover"},
        {"id": "adbench:wilt", "source": "adbench", "name": "wilt"},
        {"id": "adbench:bad", "source": "adbench", "name": "bad"},
    ]


def test_the_adbench_replay_runs_the_eligible_adbench_carriers_only(pool, monkeypatch, tmp_path, capsys):
    seen = {}
    monkeypatch.setattr(tt.pt, "jobs", lambda *a: seen.setdefault("args", a) and _adbench_jobs())
    monkeypatch.setattr(tt.pt, "eligibility", lambda job: {"eligible": job["name"] != "bad"})
    monkeypatch.setattr(tt, "run_adbench", lambda job, names=None: {"id": job["id"], "name": job["name"], "names": names})
    out = tmp_path / "runs"
    assert tt.main(["--adbench", "--output", str(out), "--workers", "2"]) == 0
    assert sorted(p.name for p in out.glob("*.json")) == ["adbench_cover.json", "adbench_wilt.json"]
    assert capsys.readouterr().out.splitlines() == ["cover", "wilt", "2 datasets"]
    assert pool.made == [2]
    root = tt.HERE.parent
    registry = root / "verification" / "evidence" / "dataset_registry"
    assert seen["args"] == (registry, root / "data" / "pool", root / "data" / "adbench")


def test_the_adbench_replay_selects_by_identifier_resumes_and_passes_the_neural_names(pool, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(tt.pt, "jobs", lambda *a: _adbench_jobs())
    monkeypatch.setattr(tt.pt, "eligibility", lambda job: {"eligible": True})
    monkeypatch.setattr(tt, "run_adbench", lambda job, names=None: {"id": job["id"], "name": job["name"], "names": names})
    out = tmp_path / "runs"
    assert tt.main(["--adbench", "--output", str(out), "--only-ids", "adbench:wilt", "--methods", "deep"]) == 0
    assert json.loads((out / "adbench_wilt.json").read_text())["names"] == list(tt.DEEP_NAMES)
    assert not (out / "adbench_cover.json").exists()
    capsys.readouterr()
    assert tt.main(["--adbench", "--output", str(out), "--resume", "--only-ids", "adbench:wilt", "adbench:cover"]) == 0
    assert capsys.readouterr().out.splitlines() == ["cover", "1 datasets"]


def test_the_comparison_is_named_after_the_methods_and_written_next_to_the_runs(tmp_path, capsys):
    archive, runs = tmp_path / "archive", tmp_path / "o" / "runs"
    archive.mkdir()
    runs.mkdir(parents=True)
    for directory in (archive, runs):
        (directory / "1.json").write_text(json.dumps(_result(1, [[0.5, 0.5], [0.2, 0.2]])))
    assert tt.main(["--output", str(runs), "--compare", str(archive), "--methods", "deep"]) == 0
    assert (runs.parent / "comparison_deep.json").read_text().endswith("}\n")
    assert capsys.readouterr().out == "1 carriers compared\n"


def test_the_help_describes_every_option(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "300")
    with pytest.raises(SystemExit) as stop:
        tt.main(["--help"])
    assert stop.value.code == 0
    text = " ".join(capsys.readouterr().out.split())
    for expected in (
        "Train-only replay of the typed-injection study",
        "--curated CURATED", "--pool POOL", "--data DATA", "--output OUTPUT", "--workers WORKERS",
        "--only-ids [ONLY_IDS ...] ADBench identifiers, for a quick check",
        "--only [ONLY ...] UCI ids, for a quick check", "--resume",
        "--methods {classical,deep}", "--compare COMPARE archived runs directory to pair with",
        "--adbench replay the ADBench carriers", "--adbench-dir ADBENCH_DIR",
    ):
        assert expected in text, expected


def test_the_stem_of_an_identifier_has_no_colon():
    assert tt._stem("adbench:magic.gamma") == "adbench_magic.gamma"


def _recording_evaluate(monkeypatch, seen):
    def fake(df, cols, seed, names):
        seen.append((seed, names, list(cols), len(df)))
        recall = pd.DataFrame({t: [float(seed)] for t in inj.ANOMALY_TYPES}, index=["m"])
        return {"recall": recall, "precision": recall / 2, "fpr": pd.Series({"m": 0.01 * seed})}

    monkeypatch.setattr(tb, "evaluate", fake)


def test_run_one_hands_the_carrier_columns_and_names_to_every_seed(monkeypatch, tmp_path):
    carrier = _carrier()
    seen = []
    _recording_evaluate(monkeypatch, seen)
    monkeypatch.setattr(tt.tr, "load_carrier", lambda meta, path, seed: (carrier, {"rows_out": 1}) if seed == 0 else None)
    out = tt.run_one(({"uci_id": 4, "name": "x"}, str(tmp_path), "h"), names=["m"])
    assert [s[0] for s in seen] == [42, 1, 2, 3, 4] and all(s[1] == ["m"] and s[2] == list(carrier.columns) for s in seen)
    assert all(s[3] > len(carrier) for s in seen)  # the injected table is evaluated, with its duplicates
    assert out["carrier"] == {"rows_out": 1} and out["name"] == "x"
    assert out["recall_mean"]["index"] == ["m"] and out["recall_mean"]["columns"] == list(inj.ANOMALY_TYPES)


def test_run_adbench_hands_the_carrier_columns_and_names_to_every_seed(monkeypatch):
    carrier = _carrier()
    seen = []
    _recording_evaluate(monkeypatch, seen)
    monkeypatch.setattr(tt.pt, "load_carrier", lambda job: (carrier, {"rows_out": 2}))
    out = tt.run_adbench({"id": "adbench:x", "name": "x"}, names=["m"])
    assert [s[0] for s in seen] == [42, 1, 2, 3, 4] and all(s[1] == ["m"] and s[2] == list(carrier.columns) for s in seen)
    assert out["carrier"] == {"rows_out": 2} and out["name"] == "x" and out["seeds"] == [42, 1, 2, 3, 4]
    assert out["precision_mean"]["data"][0][0] == pytest.approx(np.mean([42, 1, 2, 3, 4]) / 2)
    assert out["fpr_mean"]["m"] == pytest.approx(0.01 * np.mean([42, 1, 2, 3, 4]))
    assert out["recall_mean"]["index"] == ["m"]


def test_a_reference_that_moves_only_the_partitions_is_rejected(monkeypatch):
    carrier = _carrier()
    real = tb.split
    calls = []

    def shifted(df, seed):
        parts = real(df, seed)
        calls.append(1)
        return parts if len(calls) <= 2 else (parts[1], parts[0], parts[2])

    monkeypatch.setattr(tb, "split", shifted)
    with pytest.raises(AssertionError, match="^the reference changed the partitions$"):
        tt.inject_train_only(carrier, seed=2)


def test_the_reference_has_only_the_carrier_columns_and_a_fresh_index():
    carrier = _carrier()
    reference = tt.train_reference(carrier, seed=3)
    assert list(reference.index) == list(range(len(reference))) and list(reference.columns) == list(carrier.columns)


def test_the_comparison_ignores_missing_cells_and_reports_signs_and_shares():
    def result(i, values):
        return _result(i, values)

    nan = float("nan")
    archive = {i: result(i, [[0.5, 0.5], [0.5, nan]]) for i in range(1, 6)}
    shifts = [-0.3, 0.0, 0.05, 0.2, -0.15]
    replay = {i: result(i, [[0.5 + shifts[i - 1], 0.5], [0.5, nan]]) for i in range(1, 6)}
    cells = {(c["method"], c["type"]): c for c in tt.compare(archive, replay)["cells"]}
    first = cells[("m1", "missing_value")]
    assert first["median_difference"] == pytest.approx(0.0) and first["mean_difference"] == pytest.approx(-0.04)
    assert first["share_over_0.1"] == pytest.approx(0.6)
    assert first["ci_low"] < 0 < first["ci_high"] and first["ci_low"] >= -0.3 and first["ci_high"] <= 0.2
    assert np.isnan(cells[("m2", "duplicate")]["median_difference"]) or cells[("m2", "duplicate")]["share_over_0.1"] == 0.0


def test_json_is_written_sorted_with_one_space_indent_and_a_final_newline(tmp_path):
    tt.write_json(tmp_path / "x.json", {"b": [1], "a": 2})
    assert (tmp_path / "x.json").read_text() == '{\n "a": 2,\n "b": [\n  1\n ]\n}\n'


def test_a_nested_output_directory_is_created(pool, monkeypatch, tmp_path):
    monkeypatch.setattr(tt.tr, "jobs", lambda *a: [])
    assert tt.main(["--output", str(tmp_path / "a" / "b")]) == 0 and (tmp_path / "a" / "b").is_dir()


def test_paths_are_parsed_as_paths_and_the_output_is_required(pool, monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(tt.tr, "jobs", lambda *a: seen.setdefault("args", a) and [])
    tt.main(["--output", str(tmp_path), "--curated", "c", "--pool", "p", "--data", "d"])
    assert seen["args"] == (Path("c"), Path("p"), Path("d")) and all(isinstance(a, Path) for a in seen["args"])
    with pytest.raises(SystemExit) as stop:
        tt.main([])
    assert stop.value.code == 2
    seen.clear()
    monkeypatch.setattr(tt.pt, "jobs", lambda *a: seen.setdefault("adb", a) and [])
    tt.main(["--output", str(tmp_path), "--adbench", "--adbench-dir", "x"])
    assert seen["adb"][2] == Path("x") and isinstance(seen["adb"][2], Path)


def test_the_default_comparison_is_the_classical_one_and_the_default_replay_uses_no_names(pool, monkeypatch, tmp_path):
    monkeypatch.setattr(tt.pt, "jobs", lambda *a: _adbench_jobs())
    monkeypatch.setattr(tt.pt, "eligibility", lambda job: {"eligible": True})
    monkeypatch.setattr(tt, "run_adbench", lambda job, names=None: {"id": job["id"], "name": job["name"], "names": names})
    tt.main(["--adbench", "--output", str(tmp_path / "r")])
    assert json.loads((tmp_path / "r" / "adbench_cover.json").read_text())["names"] is None
    runs, archive = tmp_path / "o" / "runs", tmp_path / "ar"
    archive.mkdir()
    runs.mkdir(parents=True)
    for d in (archive, runs):
        (d / "1.json").write_text(json.dumps(_result(1, [[0.5, 0.5], [0.2, 0.2]])))
    tt.main(["--output", str(runs), "--compare", str(archive)])
    assert (runs.parent / "comparison_classical.json").exists()


def test_the_loaders_receive_the_job_the_path_and_the_carrier_seed_zero(monkeypatch, tmp_path):
    got = {}
    monkeypatch.setattr(tt.tr, "load_carrier", lambda meta, path, seed: got.setdefault("uci", (meta, path, seed)) and (_carrier(), {}))
    monkeypatch.setattr(tt.pt, "load_carrier", lambda job: got.setdefault("adb", job) and (_carrier(), {}))
    _recording_evaluate(monkeypatch, [])
    tt.run_one(({"uci_id": 1, "name": "n"}, str(tmp_path), "h"))
    tt.run_adbench({"id": "adbench:z", "name": "z"})
    assert got["uci"] == ({"uci_id": 1, "name": "n"}, tmp_path, 0) and got["adb"] == {"id": "adbench:z", "name": "z"}


def test_the_method_order_of_the_registry_is_kept_in_the_means(monkeypatch):
    def fake(df, cols, seed, names):
        recall = pd.DataFrame({t: [1.0, 2.0] for t in inj.ANOMALY_TYPES}, index=["zeta", "alpha"])
        return {"recall": recall, "precision": recall, "fpr": pd.Series({"zeta": 0.1, "alpha": 0.2})}

    monkeypatch.setattr(tb, "evaluate", fake)
    monkeypatch.setattr(tt.pt, "load_carrier", lambda job: (_carrier(), {}))
    monkeypatch.setattr(tt.tr, "load_carrier", lambda meta, path, seed: (_carrier(), {}))
    adb = tt.run_adbench({"id": "a:b", "name": "b"})
    uci = tt.run_one(({"uci_id": 1, "name": "n"}, "p", "h"))
    for out in (adb, uci):
        assert out["recall_mean"]["index"] == ["zeta", "alpha"] and out["precision_mean"]["index"] == ["zeta", "alpha"]


def test_the_injection_of_a_seed_is_reproducible_and_uses_that_seed_for_its_reference():
    carrier = _carrier()
    assert tt.inject_train_only(carrier, 2).equals(tt.inject_train_only(carrier, 2))
    expected = inj.inject(carrier, seed=2, reference=tt.train_reference(carrier, 2))
    assert tt.inject_train_only(carrier, 2).equals(expected)


def test_the_bootstrap_is_two_thousand_draws_of_seed_zero_with_a_95_percent_interval():
    shifts = [-0.3, 0.0, 0.05, 0.2, -0.15, 0.4, -0.02]
    archive = {i: _result(i, [[0.5, 0.5], [0.5, 0.5]]) for i in range(len(shifts))}
    replay = {i: _result(i, [[0.5 + d, 0.5], [0.5, 0.5]]) for i, d in enumerate(shifts)}
    cell = {(c["method"], c["type"]): c for c in tt.compare(archive, replay)["cells"]}[("m1", "missing_value")]
    column = np.array(shifts)
    draws = np.random.default_rng(0).integers(0, len(shifts), size=(2000, len(shifts)))
    low, high = np.percentile(np.median(column[draws], axis=1), [2.5, 97.5])
    assert cell["ci_low"] == pytest.approx(low) and cell["ci_high"] == pytest.approx(high)


def test_the_error_messages_name_the_violated_condition(monkeypatch):
    with pytest.raises(ValueError) as none:
        tt.compare({1: _result(1, [[0, 0], [0, 0]])}, {2: _result(2, [[0, 0], [0, 0]])})
    assert str(none.value) == "no carrier in common"
    real = inj.inject

    def moved(clean, seed, **kwargs):
        out = real(clean, seed, **kwargs)
        if "reference" in kwargs:
            out["group_id"] = out["group_id"].iloc[::-1].to_numpy()
        return out

    monkeypatch.setattr(tt.inj, "inject", moved)
    with pytest.raises(AssertionError) as layout:
        tt.inject_train_only(_carrier(), 2)
    assert str(layout.value) == "the reference changed the group or type layout"
