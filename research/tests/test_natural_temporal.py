"""Naturally labelled chronological study: labels, time order, causal features, eligibility."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import natural_temporal as nt  # noqa: E402


def _nab_root(tmp_path, values, stamps, windows, family="realTraffic", name="s"):
    folder = tmp_path / "nab" / "data" / family
    folder.mkdir(parents=True)
    pd.DataFrame({"timestamp": stamps, "value": values}).to_csv(folder / f"{name}.csv", index=False)
    labels = tmp_path / "nab" / "labels"
    labels.mkdir(parents=True)
    (labels / "combined_windows.json").write_text(json.dumps({f"{family}/{name}.csv": windows}))
    return {
        "id": f"nab/{family}/{name}",
        "source": "nab",
        "group": "nab_traffic",
        "path": f"nab/data/{family}/{name}.csv",
    }


def test_window_labels_include_both_ends_and_nothing_outside():
    times = pd.Series(pd.date_range("2020-01-01", periods=10, freq="h", tz="UTC"))
    y = nt.window_labels(times, [["2020-01-01 02:00:00", "2020-01-01 04:00:00"]])
    assert y.tolist() == [0, 0, 1, 1, 1, 0, 0, 0, 0, 0]


def test_causal_features_never_read_the_current_or_a_future_value_in_the_spread():
    values = pd.Series(np.r_[np.zeros(30), 100.0, np.zeros(10)])
    f = nt.causal_features(values)
    # the spike is not in the spread of its own row, and enters the spread of the next rows only
    assert f["spread"].iloc[30] == 0.0 and f["spread"].iloc[31] > 0.0
    assert f["deviation"].iloc[30] == 100.0 and f["diff"].iloc[30] == 100.0


def test_unsorted_series_is_sorted_by_time_with_labels_and_features_following(tmp_path):
    stamps = pd.date_range("2020-01-01", periods=60, freq="h").astype(str).tolist()
    values = np.arange(60.0)
    order = np.r_[np.arange(30, 60), np.arange(30)]  # second half first
    spec = _nab_root(
        tmp_path,
        values[order],
        np.array(stamps)[order],
        [[stamps[40], stamps[45]]],
    )
    loaded = nt.load_series(spec, tmp_path)
    assert loaded["info"]["file_in_time_order"] is False
    assert loaded["times"].is_monotonic_increasing
    # the first 24 rows are dropped, the rest are in time order with matching values and labels
    assert loaded["x"]["value"].tolist() == list(range(24, 60))
    assert loaded["y"].tolist() == [1 if 40 <= v <= 45 else 0 for v in range(24, 60)]
    assert loaded["info"]["rows_dropped"] == 24


def test_skab_columns_other_than_sensors_never_reach_the_detectors(tmp_path):
    folder = tmp_path / "skab" / "data" / "other"
    folder.mkdir(parents=True)
    pd.DataFrame(
        {
            "datetime": pd.date_range("2020-03-09", periods=5, freq="s").astype(str),
            "a": [1.0, 2, 3, 4, 5],
            "b": [1.0, 1, 1, 1, 1],
            "anomaly": [0.0, 0, 1, 1, 0],
            "changepoint": [0.0, 0, 1, 0, 0],
        }
    ).to_csv(folder / "1.csv", sep=";", index=False)
    spec = {
        "id": "skab/other/1",
        "source": "skab",
        "group": "skab",
        "path": "skab/data/other/1.csv",
    }
    loaded = nt.load_series(spec, tmp_path)
    assert list(loaded["x"].columns) == ["a"]  # constant column and truth columns are gone
    assert loaded["y"].tolist() == [0, 0, 1, 1, 0]


def test_a_series_needs_anomalous_and_normal_rows_in_the_test_partition():
    times = pd.Series(pd.date_range("2020-01-01", periods=1000, freq="h", tz="UTC"))
    y = np.zeros(1000, dtype=int)
    y[850:] = 1  # the whole test partition is anomalous
    ok, reason = nt.eligible(y, times)
    assert not ok and "normal rows" in reason
    y[:] = 0
    y[850:880] = 1
    assert nt.eligible(y, times) == (True, "")
    y[850:880] = 0
    y[850:860] = 1
    ok, reason = nt.eligible(y, times)
    assert not ok and "anomalies" in reason


def test_source_groups_follow_the_protocol(tmp_path):
    for sub, name in (("valve1", "0"), ("other", "3")):
        folder = tmp_path / "skab" / "data" / sub
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.csv").write_text("x")
    for family, name in (("realKnownCause", "nyc_taxi"), ("realTweets", "Twitter_volume_KO")):
        folder = tmp_path / "nab" / "data" / family
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.csv").write_text("x")
    groups = {s["id"]: s["group"] for s in nt.series_files(tmp_path)}
    assert groups == {
        "skab/valve1/0": "skab",
        "skab/other/3": "skab",
        "nab/realTweets/Twitter_volume_KO": "nab_tweets",
        "nab/realKnownCause/nyc_taxi": "nab_taxi",
    }


def test_a_changed_file_is_reported_by_the_manifest_check(tmp_path):
    (tmp_path / "a.csv").write_text("1")
    (tmp_path / "b.csv").write_text("2")
    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps(
            {
                "files": {
                    "a.csv": nt.digest(tmp_path / "a.csv"),
                    "b.csv": nt.digest(tmp_path / "b.csv"),
                }
            }
        )
    )
    assert nt.check_manifest(tmp_path, manifest) == []
    (tmp_path / "b.csv").write_text("changed")
    assert nt.check_manifest(tmp_path, manifest) == ["b.csv"]
    (tmp_path / "a.csv").unlink()
    assert nt.check_manifest(tmp_path, manifest) == ["a.csv", "b.csv"]


def test_run_series_reports_the_reason_when_a_series_is_not_evaluated(tmp_path):
    stamps = pd.date_range("2020-01-01", periods=300, freq="h").astype(str).tolist()
    spec = _nab_root(tmp_path, np.random.default_rng(0).normal(size=300), stamps, [])
    result = nt.run_series(spec, tmp_path)
    assert "anomalies in the test partition" in result["excluded"]
    assert result["group"] == "nab_traffic" and result["rows"] == 276


def test_an_evaluated_series_carries_both_arms_and_a_clean_fit_period_does_not_break_it(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(nt, "DEEP_NAMES", ())  # the neural detectors are not needed for this check
    rng = np.random.default_rng(1)
    n = 700
    values = rng.normal(0, 1, n)
    stamps = pd.date_range("2020-01-01", periods=n, freq="h").astype(str).tolist()
    window = [stamps[600], stamps[660]]  # anomalies only in the last 15 %
    values[600:661] += 8
    spec = _nab_root(tmp_path, values, stamps, [window])
    result = nt.run_series(spec, tmp_path)
    assert result["partitions"]["train"]["positives"] == 0
    assert "isolation_forest" in result["chronological"]
    assert result["chronological"]["isolation_forest"]["pr_auc"] > 0.5
    assert len(result["stratified"]) == len(result["chronological"])
    assert 0.0 <= result["chronological"]["zscore"]["policies"]["P0"]["recall"] <= 1.0
    pytest.approx(result["partitions"]["test"]["prevalence"], abs=0.5)


# ---------------------------------------------------------------------------------------------
# Exact values: constants, download, file listing and manifest, features, series, wiring, command
# ---------------------------------------------------------------------------------------------
import hashlib  # noqa: E402
import io  # noqa: E402
import zipfile  # noqa: E402


def test_the_constants_are_the_registered_ones():
    assert nt.WINDOW == 24 and nt.PI_FLOOR == 0.01 and nt.MAX_BYTES == 100 * 1024 * 1024
    assert nt.SEEDS == (42, 1, 2, 3, 4, 5, 6, 7, 8, 9)
    assert nt.MIN_TEST == 20 and nt.SKAB_DIRS == ("valve1", "valve2", "other")
    assert nt.DATA_DIR == nt.ROOT / "data" / "temporal"
    assert nt.MANIFEST == nt.ROOT / "verification/evidence/natural_temporal/manifest.json"
    assert set(nt.SOURCES) == {"skab", "nab"}
    assert nt.SOURCES["skab"]["repository"] == "waico/SKAB"
    assert nt.SOURCES["nab"]["commit"] == "ea702d75cc2258d9d7dd35ca8e5e2539d71f3140"
    assert nt.NAB_KNOWN_CAUSE["nyc_taxi"] == "nab_taxi" and len(nt.NAB_FAMILIES) == 4


def _zip(members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class _Response:
    def __init__(self, blob):
        self.blob, self.limit = blob, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, limit):
        self.limit = limit
        return self.blob[:limit]


def test_the_download_keeps_only_the_data_labels_and_licence_files_of_each_pinned_snapshot(
    tmp_path, monkeypatch
):
    blob = _zip(
        {
            "R-abc/data/valve1/0.csv": "a",
            "R-abc/labels/x.csv": "b",
            "R-abc/labels/combined_windows.json": "{}",
            "R-abc/LICENSE": "lic",
            "R-abc/LICENSE.txt": "lic2",
            "R-abc/README.md": "no",
            "R-abc/data/notes.txt": "no",
            "R-abc/docs/data/y.csv": "no",
            "R-abc/other.json": "no",
            "toplevel.csv": "no",
        }
    )
    seen = []

    def urlopen(url, timeout):
        seen.append((url, timeout))
        return _Response(blob)

    monkeypatch.setattr(nt.urllib.request, "urlopen", urlopen)
    nt.fetch(tmp_path / "dest")
    assert seen == [
        (f"https://codeload.github.com/{s['repository']}/zip/{s['commit']}", 120)
        for s in nt.SOURCES.values()
    ]
    for key in nt.SOURCES:
        kept = sorted(
            str(p.relative_to(tmp_path / "dest" / key))
            for p in (tmp_path / "dest" / key).rglob("*")
            if p.is_file()
        )
        assert kept == [
            "LICENSE",
            "LICENSE.txt",
            "data/valve1/0.csv",
            "labels/combined_windows.json",
            "labels/x.csv",
        ]
    assert (tmp_path / "dest" / "skab" / "data" / "valve1" / "0.csv").read_text() == "a"


def test_a_snapshot_larger_than_the_limit_is_refused_by_name(tmp_path, monkeypatch):
    holder = {}

    def urlopen(url, timeout):
        holder["response"] = _Response(b"x" * 20)
        return holder["response"]

    monkeypatch.setattr(nt.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(nt, "MAX_BYTES", 10)
    with pytest.raises(ValueError, match=r"^skab: snapshot larger than 10 bytes$"):
        nt.fetch(tmp_path)
    assert holder["response"].limit == 11
    monkeypatch.setattr(nt, "MAX_BYTES", len(_zip({"R/LICENSE": "x"})))
    monkeypatch.setattr(
        nt.urllib.request, "urlopen", lambda url, timeout: _Response(_zip({"R/LICENSE": "x"}))
    )
    nt.fetch(tmp_path)  # a snapshot of exactly the limit is accepted


def test_a_file_digest_is_its_sha256(tmp_path):
    path = tmp_path / "f.csv"
    path.write_bytes(b"abc")
    assert nt.digest(path) == hashlib.sha256(b"abc").hexdigest()


def test_series_are_listed_in_the_protocol_order_with_relative_paths(tmp_path):
    layout = [
        ("skab", "other", "2"),
        ("skab", "valve2", "1"),
        ("skab", "valve1", "9"),
        ("skab", "valve1", "0"),
        ("nab", "realKnownCause", "rogue_agent_key_hold"),
        ("nab", "realTweets", "b"),
        ("nab", "realAWSCloudwatch", "z"),
        ("nab", "realAWSCloudwatch", "a"),
        ("nab", "realAdExchange", "m"),
        ("nab", "realTraffic", "t"),
    ]
    for source, sub, name in layout:
        folder = tmp_path / source / "data" / sub
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.csv").write_text("x")
    listed = nt.series_files(tmp_path)
    assert [s["id"] for s in listed] == [
        "skab/valve1/0", "skab/valve1/9", "skab/valve2/1", "skab/other/2",
        "nab/realAWSCloudwatch/a", "nab/realAWSCloudwatch/z", "nab/realAdExchange/m",
        "nab/realTraffic/t", "nab/realTweets/b", "nab/realKnownCause/rogue_agent_key_hold",
    ]  # fmt: skip
    first, last = listed[0], listed[-1]
    assert first == {
        "id": "skab/valve1/0", "source": "skab", "group": "skab", "path": "skab/data/valve1/0.csv"
    }  # fmt: skip
    assert last == {
        "id": "nab/realKnownCause/rogue_agent_key_hold", "source": "nab", "group": "nab_rogue",
        "path": "nab/data/realKnownCause/rogue_agent_key_hold.csv",
    }  # fmt: skip
    assert listed[4]["group"] == "nab_aws" and listed[6]["group"] == "nab_adexchange"
    assert nt.series_files(tmp_path / "nowhere") == []


def test_the_manifest_hashes_every_series_and_the_label_file_in_sorted_order(tmp_path):
    for sub, name in (("valve1", "b"), ("valve1", "a")):
        folder = tmp_path / "skab" / "data" / sub
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.csv").write_text(name)
    labels = tmp_path / "nab" / "labels"
    labels.mkdir(parents=True)
    (labels / "combined_windows.json").write_text("{}")
    manifest = nt.build_manifest(tmp_path)
    assert manifest["sources"] == nt.SOURCES
    assert list(manifest["files"]) == [
        "nab/labels/combined_windows.json", "skab/data/valve1/a.csv", "skab/data/valve1/b.csv",
    ]  # fmt: skip
    assert manifest["files"]["skab/data/valve1/a.csv"] == hashlib.sha256(b"a").hexdigest()
    assert (
        manifest["files"]["nab/labels/combined_windows.json"] == hashlib.sha256(b"{}").hexdigest()
    )


def test_labelled_windows_may_overlap_and_are_read_in_utc():
    times = pd.Series(pd.date_range("2020-01-01", periods=10, freq="h", tz="UTC"))
    y = nt.window_labels(
        times,
        [
            ["2020-01-01 01:00:00", "2020-01-01 02:00:00"],
            ["2020-01-01 02:00:00", "2020-01-01 03:00:00"],
        ],
    )
    assert y.tolist() == [0, 1, 1, 1, 0, 0, 0, 0, 0, 0]
    assert y.dtype == int and nt.window_labels(times, []).tolist() == [0] * 10
    naive = pd.Series(pd.date_range("2020-01-01", periods=3, freq="h").astype(str))
    assert nt.window_labels(naive, [["2020-01-01 01:00:00", "2020-01-01 01:00:00"]]).tolist() == [
        0,
        1,
        0,
    ]


def test_causal_features_are_the_value_the_step_the_deviation_and_the_spread_of_the_past():
    values = pd.Series([1.0, 2.0, 4.0, 8.0, 16.0])
    f = nt.causal_features(values, window=3)
    assert list(f.columns) == ["value", "diff", "deviation", "spread"]
    assert f["value"].tolist() == values.tolist()
    assert f["diff"].iloc[1:].tolist() == [1.0, 2.0, 4.0, 8.0] and np.isnan(f["diff"].iloc[0])
    assert f["deviation"].iloc[3] == pytest.approx(8 - (1 + 2 + 4) / 3)
    assert f["deviation"].iloc[4] == pytest.approx(16 - (2 + 4 + 8) / 3)
    assert f["spread"].iloc[3] == pytest.approx(np.std([1, 2, 4], ddof=1))
    assert f["deviation"].iloc[:3].isna().all()
    assert nt.causal_features(pd.Series(np.arange(30.0)))["deviation"].isna().sum() == 24


def _skab(tmp_path, frame, name="1"):
    folder = tmp_path / "skab" / "data" / "valve1"
    folder.mkdir(parents=True, exist_ok=True)
    frame.to_csv(folder / f"{name}.csv", sep=";", index=False)
    return {
        "id": f"skab/valve1/{name}",
        "source": "skab",
        "group": "skab",
        "path": f"skab/data/valve1/{name}.csv",
    }


def test_a_skab_series_reports_its_facts_drops_unusable_rows_and_sorts_by_time(tmp_path):
    stamps = pd.date_range("2020-03-09 10:00:00", periods=6, freq="s").astype(str).tolist()
    frame = pd.DataFrame(
        {
            "datetime": [stamps[i] for i in (2, 0, 1, 3, 4, 5)],
            "a": [3.0, 1.0, 2.0, 4.0, np.nan, 6.0],
            "const": 1.0,
            "anomaly": [0, 0, 1, 1, 0, 0],
            "changepoint": [0.0] * 6,
        }
    )
    loaded = nt.load_series(_skab(tmp_path, frame), tmp_path)
    assert loaded["x"]["a"].tolist() == [1.0, 2.0, 3.0, 4.0, 6.0]
    assert loaded["y"].tolist() == [0, 1, 0, 1, 0]
    assert list(loaded["x"].index) == list(range(5)) and list(loaded["times"].index) == list(
        range(5)
    )
    assert loaded["info"] == {
        "rows": 5,
        "rows_dropped": 1,
        "file_in_time_order": False,
        "features": ["a"],
        "start": "2020-03-09 10:00:00+00:00",
        "end": "2020-03-09 10:00:05+00:00",
    }
    ordered = frame.sort_values("datetime").drop(columns="changepoint")
    again = nt.load_series(_skab(tmp_path, ordered, "2"), tmp_path)
    assert again["info"]["file_in_time_order"] is True
    assert again["y"].dtype == int


def test_a_nab_series_loses_its_first_window_to_the_causal_features(tmp_path):
    stamps = pd.date_range("2020-01-01", periods=40, freq="h").astype(str).tolist()
    spec = _nab_root(tmp_path, np.arange(40.0) ** 2, stamps, [[stamps[30], stamps[32]]])
    loaded = nt.load_series(spec, tmp_path)
    assert loaded["info"]["rows"] == 16 and loaded["info"]["rows_dropped"] == 24
    assert loaded["info"]["features"] == ["value", "diff", "deviation", "spread"]
    assert loaded["info"]["start"] == "2020-01-02 00:00:00+00:00"
    assert loaded["y"].sum() == 3 and len(loaded["y"]) == 16
    assert list(loaded["x"].index) == list(range(16))


def test_the_test_partition_needs_twenty_normal_rows_as_well_as_twenty_anomalies():
    times = pd.Series(pd.date_range("2020-01-01", periods=1000, freq="h", tz="UTC"))
    y = np.zeros(1000, dtype=int)
    y[850 + 20 :] = 1  # 150 test rows: 20 normal, 130 anomalous
    assert nt.eligible(y, times) == (True, "")
    y[850 + 19] = 1  # 19 normal rows
    ok, reason = nt.eligible(y, times)
    assert (ok, reason) == (False, "19 normal rows in the test partition (at least 20)")
    y2 = np.zeros(1000, dtype=int)
    ok, reason = nt.eligible(y2, times)
    assert (ok, reason) == (False, "0 anomalies in the test partition (at least 20)")


def test_the_test_partition_is_the_last_fifteen_percent_in_time_order_not_file_order():
    times = pd.Series(pd.date_range("2020-01-01", periods=1000, freq="h", tz="UTC"))
    y = np.zeros(1000, dtype=int)
    y[900:930] = 1
    reverse = np.arange(1000)[::-1]
    assert nt.eligible(y[reverse], times.iloc[reverse].reset_index(drop=True)) == (True, "")


def test_the_study_of_a_series_is_run_with_the_registry_detectors_seeds_and_alert_floor(
    tmp_path, monkeypatch
):
    n = 700
    values = np.random.default_rng(2).normal(size=n)
    stamps = pd.date_range("2020-01-01", periods=n, freq="h").astype(str).tolist()
    values[600:661] += 8
    spec = _nab_root(tmp_path, values, stamps, [[stamps[600], stamps[660]]])
    seen = {}

    def run_frame(x, y, times, **kwargs):
        seen.update(kwargs=kwargs, rows=len(y), cols=list(x.columns))
        return {"chronological": {}, "stratified": {}}

    monkeypatch.setattr(nt.td, "run_frame", run_frame)
    monkeypatch.setattr(
        nt.pc,
        "methods_for",
        lambda n_train, wanted: seen.update(n_train=n_train, wanted=wanted) or (["m1"], ["m2"]),
    )
    result = nt.run_series(spec, tmp_path)
    assert seen["kwargs"] == {"methods": ["m1"], "seeds": nt.SEEDS, "pi_floor": 0.01}
    assert seen["wanted"] == [*nt.DETECTOR_NAMES, *nt.DEEP_NAMES]
    assert seen["n_train"] == int(seen["rows"] * 0.70)
    assert result["skipped"] == ["m2"] and result["group"] == "nab_traffic"
    assert (result["id"], result["source"]) == (spec["id"], "nab")
    assert result["rows"] == seen["rows"] and "excluded" not in result


def test_the_parser_reads_the_data_directory_and_the_four_commands():
    parser = nt.build_parser()
    assert parser.description == nt.__doc__
    assert parser.parse_args(["list"]).data == nt.DATA_DIR
    args = parser.parse_args(["--data", "d", "run", "--id", "x", "--output", "o.json"])
    assert args.data == Path("d") and args.id == "x" and args.output == Path("o.json")
    assert isinstance(args.data, Path) and isinstance(args.output, Path)
    for command in ("fetch", "manifest", "list"):
        assert parser.parse_args([command]).command == command
    with pytest.raises(SystemExit):
        parser.parse_args([])
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--output", "o"])
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--id", "x"])


def test_the_fetch_command_downloads_into_the_data_directory(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(nt, "fetch", seen.append)
    assert nt.main(["--data", str(tmp_path), "fetch"]) == 0
    assert seen == [tmp_path]


def test_the_manifest_command_writes_sorted_indented_json_in_its_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(nt, "MANIFEST", tmp_path / "evidence" / "n" / "manifest.json")
    monkeypatch.setattr(
        nt, "build_manifest", lambda data: {"files": {"b": 1, "a": 2}, "data": str(data)}
    )
    assert nt.main(["--data", str(tmp_path), "manifest"]) == 0
    assert (tmp_path / "evidence" / "n" / "manifest.json").read_text() == (
        '{\n "data": "' + str(tmp_path) + '",\n "files": {\n  "a": 2,\n  "b": 1\n }\n}\n'
    )
    assert nt.main(["--data", str(tmp_path), "manifest"]) == 0  # an existing directory is fine


def test_the_list_command_prints_one_series_per_line(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(nt, "series_files", lambda data: [{"id": "x/1"}, {"id": "x/2"}])
    assert nt.main(["--data", str(tmp_path), "list"]) == 0
    assert capsys.readouterr().out == "x/1\nx/2\n"


def test_the_run_command_refuses_files_that_differ_from_the_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(nt, "check_manifest", lambda data: ["a", "b", "c", "d"])
    with pytest.raises(SystemExit) as stop:
        nt.main(["--data", str(tmp_path), "run", "--id", "x", "--output", str(tmp_path / "o.json")])
    assert str(stop.value) == "files differ from the manifest: ['a', 'b', 'c']"


def test_the_run_command_evaluates_the_named_series_and_archives_its_result(
    tmp_path, monkeypatch, capsys
):
    specs = [{"id": "s/1"}, {"id": "s/2"}]
    monkeypatch.setattr(nt, "check_manifest", lambda data: [])
    monkeypatch.setattr(nt, "series_files", lambda data: specs)
    monkeypatch.setattr(
        nt, "run_series", lambda spec, data: {"id": spec["id"], "b": 1, "a": 2, "data": str(data)}
    )
    out = tmp_path / "deep" / "o.json"
    assert nt.main(["--data", str(tmp_path), "run", "--id", "s/2", "--output", str(out)]) == 0
    assert (
        out.read_text()
        == '{\n "a": 2,\n "b": 1,\n "data": "' + str(tmp_path) + '",\n "id": "s/2"\n}\n'
    )
    assert capsys.readouterr().out == "s/2 ok\n"
    monkeypatch.setattr(
        nt, "run_series", lambda spec, data: {"id": spec["id"], "excluded": "too few"}
    )
    assert nt.main(["--data", str(tmp_path), "run", "--id", "s/1", "--output", str(out)]) == 0
    assert capsys.readouterr().out == "s/1 too few\n"
