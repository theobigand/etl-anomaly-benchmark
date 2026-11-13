"""The chronological pool command: month dating, dataset jobs, stored files and printed lines."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pool_chrono as pc  # noqa: E402


def test_a_month_alone_is_dated_the_first_of_that_month_of_2017_plus_one_minute_per_earlier_row():
    frame = pd.DataFrame({"Month": ["Jan", "feb", "MARCH", "Apr", "May", "Jun", "Jul", "Aug"]})
    frame = pd.concat([frame, pd.DataFrame({"Month": ["Sep", "Oct", "Nov", "Dec", "Dec", "Jan"]})])
    times = pc.read_times(frame.reset_index(drop=True), 468)
    assert str(times.dt.tz) == "UTC"
    expected = [pd.Timestamp(2017, m, 1, tz="UTC") for m in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)]
    assert times.iloc[:12].tolist() == expected
    assert times.iloc[12] == pd.Timestamp("2017-12-01 00:01", tz="UTC")
    assert times.iloc[13] == pd.Timestamp("2017-01-01 00:01", tz="UTC")


def _stub_jobs(monkeypatch, tmp_path, excluded=None):
    seen = {"loaded": [], "ran": []}

    def frame():
        return pd.DataFrame({"a": [1.0, 2.0]}), np.array([0, 1]), pd.Series([1, 2])

    monkeypatch.setattr(
        pc.td, "credit_card", lambda: seen["loaded"].append("credit_card") or frame()
    )
    monkeypatch.setattr(
        pc.td,
        "bank_marketing",
        lambda path: seen["loaded"].append(("bank", path)) or frame(),
    )

    def load(meta, path, uci_id):
        seen["loaded"].append((meta["uci_id"], path, uci_id))
        return (*frame(), 3)

    monkeypatch.setattr(pc, "load_pool_dataset", load)

    def run(x, y, times):
        seen["ran"].append((x, y, times))
        return {"b": 1, "a": 2, **({"excluded": excluded} if excluded else {})}

    monkeypatch.setattr(pc, "run_dataset", run)
    return seen


def test_each_dataset_is_loaded_from_its_pool_file_run_and_stored_sorted_with_its_dropped_rows(
    monkeypatch, tmp_path, capsys
):
    seen = _stub_jobs(monkeypatch, tmp_path)
    out = tmp_path / "out"
    assert pc.main(["--output", str(out)]) == 0
    names = sorted(p.name for p in out.iterdir())
    assert "credit_card.json" in names and "bank_marketing.json" in names and len(names) == 5
    assert ("bank", pc.ROOT / "data" / "pool" / "222.csv") in seen["loaded"]
    assert {entry[0] for entry in seen["loaded"] if isinstance(entry[0], int)} == {357, 864, 468}
    assert all(
        entry[1] == pc.ROOT / "data" / "pool" / f"{entry[0]}.csv" and entry[0] == entry[2]
        for entry in seen["loaded"]
        if isinstance(entry[0], int)
    )
    text = (out / "credit_card.json").read_text()
    assert text == json.dumps({"a": 2, "b": 1}, indent=1, sort_keys=True) + "\n"
    dropped = [
        n
        for n in names
        if json.loads((out / n).read_text()).get("rows_without_a_readable_time") == 3
    ]
    assert len(dropped) == 3
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 5 and all(line.endswith(" ok") for line in lines)


def test_an_excluded_dataset_is_printed_with_its_reason_and_every_line_is_flushed(
    monkeypatch, tmp_path
):
    _stub_jobs(monkeypatch, tmp_path, excluded="too few anomalies")
    printed = []
    monkeypatch.setattr(pc, "print", lambda *a, **k: printed.append((a, k)), raising=False)
    pc.main(["--output", str(tmp_path / "out"), "--only", "credit_card"])
    assert printed == [(("credit_card", "too few anomalies"), {"flush": True})]


def test_only_the_named_datasets_are_run_and_the_output_folder_may_exist(monkeypatch, tmp_path):
    seen = _stub_jobs(monkeypatch, tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    pc.main(["--output", str(out), "--only", "credit_card", "bank_marketing"])
    assert sorted(p.name for p in out.iterdir()) == ["bank_marketing.json", "credit_card.json"]
    assert len(seen["ran"]) == 2
    x, y, times = seen["ran"][0]
    assert x["a"].tolist() == [1.0, 2.0] and y.tolist() == [0, 1] and times.tolist() == [1, 2]


def test_the_output_option_is_required_and_the_help_describes_the_command(capsys, monkeypatch):
    with pytest.raises(SystemExit) as stop:
        pc.main([])
    assert stop.value.code == 2
    monkeypatch.setenv("COLUMNS", "300")
    with pytest.raises(SystemExit):
        pc.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "--only [ONLY ...] dataset names, for a quick check" in text
    assert pc.__doc__.strip().splitlines()[0] in text
