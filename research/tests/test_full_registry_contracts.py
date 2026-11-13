"""Hypothesis limits, file formats and the three commands of the complete-registry study."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from test_full_registry import _classical, _deep

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import full_registry as fr  # noqa: E402


def test_h3_accepts_a_marginal_recall_of_exactly_two_tenths_and_a_gap_of_exactly_one_half():
    zero = _classical(ecod=0.0, copod=0.0, hbos=0.0, isolation_forest=0.5)
    out = fr.hypotheses(zero, _deep())["H3"]
    assert out == {
        "supported": True,
        "marginal_recall": {"ecod": 0.0, "copod": 0.0, "hbos": 0.0},
        "isolation_forest": 0.5,
    }
    at_limit = _classical(ecod=0.2, copod=0.0, hbos=0.0, isolation_forest=0.75)
    assert fr.hypotheses(at_limit, _deep())["H3"]["supported"] is True
    over = _classical(ecod=0.25, copod=0.0, hbos=0.0, isolation_forest=0.9)
    assert fr.hypotheses(over, _deep())["H3"]["supported"] is False
    short = _classical(ecod=0.0, copod=0.0, hbos=0.0, isolation_forest=0.4375)
    assert fr.hypotheses(short, _deep())["H3"]["supported"] is False


def test_h4_and_h5_report_the_values_they_decided_on_with_exact_names():
    classical = _classical(pca=0.5)
    classical["temporal_drift"] = 0.25
    classical.loc["lof", "temporal_drift"] = 0.5
    out = fr.hypotheses(classical, _deep(drift=0.5, autoencoder=0.5625))
    assert out["H4"] == {"supported": True, "pca": 0.5, "autoencoder": 0.5625}
    assert out["H5"]["best_earlier"] == {"method": "lof", "recall": 0.5}
    assert set(out["H5"]["new_drift_recall"]) == set(fr.NEW_CLASSICAL) | set(fr.NEW_DEEP)
    assert out["H5"]["supported"] is True
    wide = fr.hypotheses(classical, _deep(drift=0.5, autoencoder=0.625))
    assert wide["H4"]["supported"] is False
    assert set(out) == {"H3", "H4", "H5"}


def test_h4_needs_the_pca_and_the_autoencoder_to_differ_by_less_than_a_tenth_exactly():
    classical = _classical(pca=0.1)
    classical["temporal_drift"] = 0.25
    classical.loc["lof", "temporal_drift"] = 0.5
    at_the_limit = fr.hypotheses(classical, _deep(drift=0.5, autoencoder=0.0))
    assert at_the_limit["H4"]["supported"] is False
    inside = fr.hypotheses(classical, _deep(drift=0.5, autoencoder=0.0625))
    assert inside["H4"]["supported"] is True


def test_the_settings_of_a_detector_are_stored_as_plain_json_text():
    detector = SimpleNamespace(settings=lambda: {"path": Path("/x"), "n": 3})
    assert fr._settings(detector) == {"path": "/x", "n": 3}


def test_a_json_file_is_written_sorted_indented_by_one_space_and_newline_terminated(tmp_path):
    target = tmp_path / "a.json"
    fr._write(target, {"b": [1], "a": 2})
    assert target.read_text() == json.dumps({"b": [1], "a": 2}, indent=1, sort_keys=True) + "\n"


def test_the_published_matrix_keeps_the_mean_columns_under_the_type_names(tmp_path):
    columns = {f"{t}_mean": [0.5] for t in fr.ANOMALY_TYPES} | {"x_std": [9.0]}
    frame = pd.DataFrame(columns, index=pd.Index(["zscore"], name="method"))
    path = tmp_path / "p.csv"
    frame.to_csv(path)
    out = fr._published(path)
    assert list(out.columns) == list(fr.ANOMALY_TYPES) and out.index.tolist() == ["zscore"]


def _seed_file(folder, seed, errors=None):
    frame = pd.DataFrame(0.25, index=["vae"], columns=fr.ANOMALY_TYPES)
    payload = {
        "seed": seed,
        "recall": json.loads(frame.to_json(orient="split")),
        "errors": errors or {},
    }
    (folder / f"synthetic_seed_{seed}.json").write_text(json.dumps(payload))


def _classical_csv(path):
    frame = pd.DataFrame(0.5, index=pd.Index(["pca", "isolation_forest"], name="method"),
                         columns=[f"{t}_mean" for t in fr.ANOMALY_TYPES])  # fmt: skip
    frame.to_csv(path)


def test_the_summary_command_writes_the_deep_matrix_the_hypotheses_and_the_seed_errors(
    tmp_path, monkeypatch
):
    runs = tmp_path / "runs"
    runs.mkdir()
    _seed_file(runs, 2, errors={"vae": "boom"})
    _seed_file(runs, 1)
    csv = tmp_path / "c.csv"
    _classical_csv(csv)
    monkeypatch.setattr(fr, "hypotheses", lambda classical, deep: {"seen": list(deep.index)})
    out = tmp_path / "new" / "out"
    argv = ["summary", "--output", str(out), "--deep-runs", str(runs), "--classical", str(csv)]
    assert fr.main(argv) == 0
    text = (out / "synthetic_results.json").read_text()
    results = json.loads(text)
    assert text == json.dumps(results, indent=1, sort_keys=True) + "\n"
    assert results["seeds"] == [1, 2] and results["errors"] == {"2": {"vae": "boom"}}
    assert results["hypotheses"] == {"seen": ["vae"]}
    assert results["deep"]["index"] == ["vae"]
    lines = (out / "synthetic_results.md").read_text().splitlines()
    assert lines[0] == "| method | " + " | ".join(fr.ANOMALY_TYPES) + " |"
    assert lines[1] == "|---|" + "---|" * len(fr.ANOMALY_TYPES)
    assert lines[2] == "| vae | " + " | ".join(["0.25"] * 6) + " |"


def test_the_summary_reads_the_seed_runs_of_the_output_folder_when_none_is_given(
    tmp_path, monkeypatch
):
    _seed_file(tmp_path, 7)
    csv = tmp_path / "c.csv"
    _classical_csv(csv)
    monkeypatch.setattr(fr, "hypotheses", lambda classical, deep: {})
    fr.main(["summary", "--output", str(tmp_path), "--classical", str(csv)])
    assert json.loads((tmp_path / "synthetic_results.json").read_text())["seeds"] == [7]
    assert json.loads((tmp_path / "synthetic_results.json").read_text())["errors"] == {}


def test_the_synthetic_command_runs_every_seed_with_the_row_count_and_names_each_file(
    tmp_path, monkeypatch, capsys
):
    calls = []
    monkeypatch.setattr(
        fr, "synthetic_seed", lambda seed, rows: calls.append((seed, rows)) or {"seed": seed}
    )
    out = tmp_path / "o"
    assert fr.main(["synthetic", "--output", str(out), "--rows", "500"]) == 0
    assert calls == [(seed, 500) for seed in fr.SEEDS]
    assert sorted(p.name for p in out.iterdir()) == sorted(
        f"synthetic_seed_{s}.json" for s in fr.SEEDS
    )
    assert capsys.readouterr().out.splitlines() == [f"seed {s}" for s in fr.SEEDS]
    calls.clear()
    fr.main(["synthetic", "--output", str(out)])
    assert {rows for _, rows in calls} == {None}


def test_the_real_command_writes_each_dataset_with_its_table_of_mean_and_deviation(
    tmp_path, monkeypatch, capsys
):
    spec = SimpleNamespace(load=lambda: "frame")
    monkeypatch.setattr(fr, "DATASETS", {"toy": spec, "other": spec})
    seen = []
    monkeypatch.setattr(
        fr, "real_seed", lambda s, df, seed: seen.append((s, df, seed)) or {"seed": seed}
    )
    table = pd.DataFrame(
        {f"{m}_mean": [0.5] for m in fr.METRICS} | {f"{m}_std": [0.125] for m in fr.METRICS},
        index=["vae"],
    )
    monkeypatch.setattr(fr, "real_summary", lambda runs: table)
    out = tmp_path / "o"
    assert fr.main(["real", "--output", str(out), "--datasets", "toy"]) == 0
    assert [(s is spec, df, seed) for s, df, seed in seen] == [
        (True, "frame", seed) for seed in fr.SEEDS
    ]
    assert json.loads((out / "real_toy.json").read_text())["dataset"] == "toy"
    lines = (out / "real_toy.md").read_text().splitlines()
    assert lines[0] == "| detector | " + " | ".join(fr.METRICS) + " |"
    assert lines[1] == "|---|" + "---|" * len(fr.METRICS)
    assert lines[2] == "| vae | " + " | ".join(["0.500 ± 0.125"] * len(fr.METRICS)) + " |"
    assert capsys.readouterr().out.splitlines() == [f"toy seed {s}" for s in fr.SEEDS]
    assert not (out / "real_other.json").exists()
    seen.clear()
    fr.main(["real", "--output", str(tmp_path / "all")])
    assert len(seen) == 2 * len(fr.SEEDS) and all(s is spec for s, _, _ in seen)
    with pytest.raises(SystemExit) as stop:
        fr.main([])
    assert stop.value.code == 2
    with pytest.raises(SystemExit) as stop:
        fr.main(["real", "--output", str(out), "--datasets", "nope"])
    assert stop.value.code == 2
