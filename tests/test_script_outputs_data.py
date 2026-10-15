"""Files, log lines and options of the two data-preparation scripts, run in-process."""

import io
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import fetch_cardio  # noqa: E402
import generate_synthetic  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.synthetic import ANOMALY_TYPES, make_synthetic  # noqa: E402


def _messages(caplog, name):
    return [record.getMessage() for record in caplog.records if record.name.endswith(name)]


def test_generation_writes_the_requested_population_and_reports_its_composition(
    tmp_path, monkeypatch, caplog
):
    output = tmp_path / "nested" / "deeper" / "synthetic.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_synthetic", "--output", str(output), "--rows", "1000", "--rate", "0.05"]
        + ["--seed", "9"],
    )
    with caplog.at_level(logging.INFO):
        generate_synthetic.main()
    expected = make_synthetic(n_rows=1000, anomaly_rate=0.05, seed=9)
    assert output.read_text() == expected.to_csv(index=False)
    counts = expected["anomaly_type"].value_counts()
    messages = _messages(caplog, "generate_synthetic")
    assert messages[0] == f"wrote {len(expected)} rows x {expected.shape[1]} cols -> {output}"
    assert messages[1] == f"clean: {counts['clean']}"
    assert messages[2:] == [f"  {name:<22} {counts[name]}" for name in ANOMALY_TYPES]


def test_a_population_without_anomalies_reports_zero_for_every_type(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_synthetic", "--output", str(tmp_path / "clean.csv"), "--rows", "100"]
        + ["--rate", "0"],
    )
    with caplog.at_level(logging.INFO):
        generate_synthetic.main()
    messages = _messages(caplog, "generate_synthetic")
    assert messages[1] == "clean: 100"
    assert messages[2:] == [f"  {name:<22} 0" for name in ANOMALY_TYPES]


def test_generation_defaults_come_from_the_configuration(tmp_path, monkeypatch):
    target = tmp_path / "default.csv"
    monkeypatch.setattr(config, "SYNTHETIC_CSV", target)
    monkeypatch.setattr(config, "SYNTHETIC_ROWS", 130)
    monkeypatch.setattr(config, "SYNTHETIC_ANOMALY_RATE", 0.04)
    monkeypatch.setattr(config, "RANDOM_SEED", 5)
    monkeypatch.setattr(sys, "argv", ["generate_synthetic"])
    generate_synthetic.main()
    expected = make_synthetic(n_rows=130, anomaly_rate=0.04, seed=5)
    assert target.read_text() == expected.to_csv(index=False)


def test_generation_help_describes_the_script(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["generate_synthetic", "--help"])
    with pytest.raises(SystemExit):
        generate_synthetic.main()
    out = capsys.readouterr().out
    assert "Write the controlled synthetic dataset" in out
    for option in ("--output", "--rows", "--rate", "--seed"):
        assert option in out


def test_cardio_download_uses_the_declared_source_and_reports_the_result(
    tmp_path, monkeypatch, caplog
):
    payload = io.BytesIO()
    x = np.arange(12.0).reshape(4, 3)
    np.savez(payload, X=x, y=np.array([0.0, 1.0, 0.0, 0.0]))
    seen = {}

    def fake_urlopen(url, timeout):
        seen.update(url=url, timeout=timeout)
        return io.BytesIO(payload.getvalue())

    monkeypatch.setattr(fetch_cardio.urllib.request, "urlopen", fake_urlopen)
    target = tmp_path / "deep" / "er" / "cardio.csv"
    monkeypatch.setattr(config, "CARDIO_CSV", target)
    with caplog.at_level(logging.INFO):
        fetch_cardio.main()
    url = "https://raw.githubusercontent.com/Minqi824/ADBench/main/adbench/datasets/Classical/6_cardio.npz"
    assert seen == {"url": url, "timeout": 30}
    frame = pd.read_csv(target)
    assert frame.columns.tolist() == ["f00", "f01", "f02", "label"]
    assert frame["label"].tolist() == [0, 1, 0, 0]
    assert target.read_text().splitlines()[2].endswith(",1")  # integer labels, no index column
    assert frame[["f00", "f01", "f02"]].to_numpy().tolist() == x.tolist()
    assert _messages(caplog, "fetch_cardio") == [
        f"downloading {url}",
        f"wrote 4 rows x 4 cols -> {target} (1 anomalies, 25.0%)",
    ]


def test_cardio_download_accepts_an_existing_directory(tmp_path, monkeypatch):
    payload = io.BytesIO()
    np.savez(payload, X=np.zeros((2, 1)), y=np.array([0, 1]))
    monkeypatch.setattr(
        fetch_cardio.urllib.request, "urlopen", lambda url, timeout: io.BytesIO(payload.getvalue())
    )
    monkeypatch.setattr(config, "CARDIO_CSV", tmp_path / "cardio.csv")
    fetch_cardio.main()
    fetch_cardio.main()
    assert (tmp_path / "cardio.csv").is_file()
