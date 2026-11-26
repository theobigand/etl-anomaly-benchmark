"""Second UCI wave: stratum tags, rejection reasons, licence rule, pinning with a checksum."""

import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uci_wave2 as w2  # noqa: E402


def _meta(**kw):
    base = {
        "uci_id": 9001, "name": "T", "num_instances": 1000, "num_features": 8,
        "characteristics": ["Multivariate", "Time-Series"], "feature_types": ["Real"],
        "area": "Other", "data_url": "https://archive.ics.uci.edu/static/public/9001/data.csv",
        "repository_url": "https://archive.ics.uci.edu/dataset/9001/t",
    }  # fmt: skip
    return {**base, **kw}


def test_tags_name_the_uncovered_stratum_a_table_can_serve():
    assert w2.tags(_meta()) == ["time_series"]
    assert w2.tags(_meta(characteristics=["Sequential"])) == ["sequential"]
    assert w2.tags(_meta(characteristics=[], area="Business")) == ["transactional"]
    assert w2.tags(_meta(characteristics=[], area="Business", num_instances=100)) == []
    assert w2.tags(_meta(characteristics=[], feature_types=["Categorical"])) == ["categorical_only"]


def test_rejection_reasons_are_explicit_and_taken_tables_are_skipped():
    assert w2.rejection(_meta(), set()) is None
    assert "first pool" in w2.rejection(_meta(), {9001})
    assert "rows" in w2.rejection(_meta(num_instances=100), set())
    assert "features" in w2.rejection(_meta(num_features=140256), set())
    assert "modality" in w2.rejection(_meta(characteristics=["Time-Series", "Text"]), set())
    assert "download" in w2.rejection(_meta(data_url=None), set())
    assert "stratum" in w2.rejection(_meta(characteristics=[], feature_types=["Real"]), set())


def test_a_table_needs_an_open_licence_stated_on_its_own_page():
    survey = [_meta(uci_id=1), _meta(uci_id=2), _meta(uci_id=3), _meta(uci_id=4)]
    licences = {1: "CC BY 4.0", 2: "CC0 1.0", 3: None, 4: "CC BY-NC 4.0"}
    chosen, rejected = w2.select(survey, licences, taken=set())
    assert [m["uci_id"] for m in chosen] == [1, 2]
    assert {m["uci_id"] for m, _ in rejected} == {3, 4}
    assert all("licence" in reason for _, reason in rejected)


def test_pinning_records_the_checksum_of_the_downloaded_bytes_and_the_time_columns(tmp_path):
    frame = pd.DataFrame(
        {"date": pd.date_range("2020-01-01", periods=400, freq="h").astype(str), "v": range(400)}
    )
    payload = frame.to_csv(index=False).encode()

    def fetcher(url, path):
        path.write_bytes(payload)
        return path, hashlib.sha256(payload).hexdigest()

    row = w2.pin({**_meta(), "licence": "CC BY 4.0"}, tmp_path, fetcher)
    assert row["sha256"] == hashlib.sha256(payload).hexdigest()
    assert row["rows"] == 400 and row["time_candidates"] == ["date"]
    assert row["tags"] == ["time_series"] and row["licence"] == "CC BY 4.0"


def test_a_download_over_the_size_limit_is_recorded_as_failed_not_fatal(tmp_path, monkeypatch):
    import json

    def too_big(meta, destination, fetcher=None):
        raise w2.dr.RegistryError("the download is larger than 104857600 bytes")

    selection = tmp_path / "sel.json"
    selection.write_text(json.dumps({"chosen": [{**_meta(), "licence": "CC BY 4.0"}]}))
    monkeypatch.setattr(w2, "SELECTION", selection)
    monkeypatch.setattr(w2, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(w2, "pin", too_big)
    assert w2.main(["fetch", "--destination", str(tmp_path / "d")]) == 0
    out = json.loads((tmp_path / "manifest.json").read_text())
    assert out["tables"] == [] and out["failed"][0]["uci_id"] == 9001
    assert "larger" in out["failed"][0]["reason"]


def test_a_time_column_is_verified_only_if_parsed_distinct_and_spanning_a_week():
    good = pd.DataFrame({"t": pd.date_range("2020-01-01", periods=300, freq="D").astype(str)})
    assert w2.check_time(good, "t")["verified"] is True
    short = pd.DataFrame({"t": pd.date_range("2020-01-01", periods=300, freq="s").astype(str)})
    assert w2.check_time(short, "t")["verified"] is False  # one day only
    junk = pd.DataFrame({"t": ["x"] * 300})
    r = w2.check_time(junk, "t")
    assert r["verified"] is False and r["parsed_share"] == 0.0
    shuffled = good.sample(frac=1, random_state=0)
    r = w2.check_time(shuffled, "t")
    assert r["verified"] is True and r["file_in_time_order"] is False


def test_the_selection_limits_and_files_are_the_documented_ones():
    assert (w2.MIN_ROWS, w2.MAX_ROWS, w2.MIN_FEATURES, w2.MAX_FEATURES) == (300, 3_000_000, 3, 300)
    assert {"Image", "Text"} == w2.EXCLUDED_MODALITIES
    assert {"CC BY 4.0", "CC0 1.0"} == w2.ACCEPTED
    assert (w2.MIN_PARSED_SHARE, w2.MIN_DISTINCT, w2.MIN_SPAN_DAYS) == (0.99, 100, 7)
    assert w2.WAVE_DIR == w2.ROOT / "data" / "uci_wave2"
    evidence = w2.ROOT / "verification/evidence"
    assert evidence / "dataset_registry/uci_pool.json" == w2.FIRST_POOL
    assert evidence / "dataset_registry_v2/uci_wave2_selection.json" == w2.SELECTION
    assert evidence / "dataset_registry_v2/uci_wave2_manifest.json" == w2.MANIFEST
    assert evidence / "dataset_registry_v2/uci_wave2_time.json" == w2.TIME_REPORT


def test_row_and_feature_limits_are_inclusive_at_both_ends():
    for rows in (300, 3_000_000):
        assert w2.rejection(_meta(num_instances=rows), set()) is None
    for rows in (299, 3_000_001):
        assert w2.rejection(_meta(num_instances=rows), set()) == f"rows ({rows})"
    for features in (3, 300):
        assert w2.rejection(_meta(num_features=features), set()) is None
    for features in (2, 301):
        assert w2.rejection(_meta(num_features=features), set()) == f"features ({features})"


def test_missing_counts_are_rejected_and_every_reason_is_reported_in_order():
    assert w2.rejection(_meta(num_instances=None), set()) == "rows (None)"
    assert w2.rejection(_meta(num_features=None), set()) == "features (None)"
    both = w2.rejection(
        _meta(
            num_instances=1,
            num_features=1,
            characteristics=["Image"],
            data_url="",
            feature_types=["Real"],
        ),
        {9001},
    )
    assert both == (
        "already in the first pool; rows (1); features (1); modality; download; "
        "serves no uncovered stratum"
    )
    assert w2.rejection(_meta(characteristics=["Time-Series", "Image"]), set()) == "modality"
    assert w2.rejection(_meta(characteristics=None), set()) == "serves no uncovered stratum"


def test_tags_at_their_boundaries_and_in_combination():
    business = _meta(characteristics=[], area="Business")
    assert w2.tags({**business, "num_instances": 500}) == ["transactional"]
    assert w2.tags({**business, "num_instances": 499}) == []
    assert w2.tags({**business, "num_instances": None}) == []
    assert w2.tags(_meta(characteristics=[], area="Other", num_instances=900)) == []
    assert w2.tags(_meta(characteristics=[], feature_types=["Categorical", "Real"])) == []
    assert w2.tags(_meta(characteristics=[], feature_types=["Categorical", "Integer"])) == []
    assert w2.tags(_meta(characteristics=[], feature_types=None)) == []
    assert w2.tags(_meta(characteristics=None, feature_types=["Categorical"])) == [
        "categorical_only"
    ]
    both = _meta(
        characteristics=["Time-Series", "Sequential"],
        area="Business",
        feature_types=["Categorical"],
    )
    assert w2.tags(both) == ["time_series", "sequential", "transactional", "categorical_only"]


def test_select_keeps_the_survey_order_and_names_the_licence_reason():
    survey = [_meta(uci_id=1), _meta(uci_id=2, num_instances=1), _meta(uci_id=3)]
    chosen, rejected = w2.select(survey, {1: "CC0 1.0", 2: "CC0 1.0", 3: "GPL"}, set())
    assert [m["uci_id"] for m in chosen] == [1]
    assert [(m["uci_id"], r) for m, r in rejected] == [
        (2, "rows (1)"),
        (3, "licence not open or not stated on the page"),
    ]


def _frame_with_time(n, freq):
    return pd.DataFrame({"t": pd.date_range("2020-01-01", periods=n, freq=freq).astype(str)})


def test_the_time_check_thresholds_are_inclusive_and_the_report_is_complete():
    exact = w2.check_time(_frame_with_time(100, "D"), "t")
    assert exact == {
        "column": "t",
        "parsed_share": 1.0,
        "distinct": 100,
        "span_days": 99.0,
        "file_in_time_order": True,
        "verified": True,
    }
    assert w2.check_time(_frame_with_time(99, "D"), "t")["verified"] is False
    week = pd.DataFrame({"t": pd.date_range("2020-01-01", "2020-01-08", periods=120).astype(str)})
    assert w2.check_time(week, "t")["span_days"] == 7.0
    assert w2.check_time(week, "t")["verified"] is True
    under = pd.DataFrame({"t": pd.date_range("2020-01-01", "2020-01-07", periods=120).astype(str)})
    assert w2.check_time(under, "t")["span_days"] == 6.0
    assert w2.check_time(under, "t")["verified"] is False


def test_the_parsed_share_must_reach_ninety_nine_percent():
    frame = _frame_with_time(200, "D")
    ok = frame.copy()
    ok.loc[:1, "t"] = "bad"
    assert w2.check_time(ok, "t")["parsed_share"] == 0.99
    assert w2.check_time(ok, "t")["verified"] is True
    low = frame.copy()
    low.loc[:2, "t"] = "bad"
    assert w2.check_time(low, "t")["parsed_share"] == 0.985
    assert w2.check_time(low, "t")["verified"] is False


def test_an_unparsable_column_has_no_span_and_mixed_formats_are_read():
    r = w2.check_time(pd.DataFrame({"t": ["x", "y"]}), "t")
    assert r["span_days"] == 0.0 and r["distinct"] == 0 and r["file_in_time_order"] is True
    mixed = pd.DataFrame({"t": ["2020-01-01", "2020-01-02 10:00:00", "2020-01-03T00:00:00Z"]})
    assert w2.check_time(mixed, "t")["parsed_share"] == 1.0


def test_first_pool_ids_reads_the_ids_of_the_rows(tmp_path):
    import json

    path = tmp_path / "pool.json"
    path.write_text(json.dumps({"rows": [{"uci_id": 3}, {"uci_id": 5}, {"uci_id": 3}]}))
    assert w2.first_pool_ids(path) == {3, 5}


def test_verify_times_checks_the_first_candidate_of_each_table_that_has_one(tmp_path):
    import json

    _frame_with_time(150, "D").assign(other=1).to_csv(tmp_path / "1.csv", index=False)
    _frame_with_time(150, "D").to_csv(tmp_path / "2.csv", index=False)
    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps(
            {
                "tables": [
                    {"uci_id": 1, "time_candidates": ["t", "other"]},
                    {"uci_id": 3, "time_candidates": []},
                    {"uci_id": 2, "time_candidates": ["t"]},
                ]
            }
        )
    )
    got = w2.verify_times(manifest, tmp_path)
    assert list(got) == ["uci:1", "uci:2"]
    assert got["uci:1"]["column"] == "t" and got["uci:1"]["verified"] is True


def test_pin_downloads_into_a_file_named_by_the_uci_id_and_records_the_page(tmp_path):
    seen = {}

    def fetcher(url, path):
        seen.update(url=url, path=path)
        path.write_text("a,b,c\n1,2,3\n")
        return path, "abc"

    row = w2.pin({**_meta(), "licence": "CC0 1.0"}, tmp_path, fetcher)
    assert seen["path"] == tmp_path / "9001.csv"
    assert seen["url"] == _meta()["data_url"]
    assert row == {
        "uci_id": 9001,
        "name": "T",
        "licence": "CC0 1.0",
        "url": _meta()["data_url"],
        "page": _meta()["repository_url"],
        "sha256": "abc",
        "rows": 1,
        "columns": 3,
        "tags": ["time_series"],
        "area": "Other",
        "time_candidates": [],
    }


def test_the_select_command_checks_licences_of_candidates_and_writes_the_selection(
    tmp_path, monkeypatch, capsys
):
    import json

    def entry(uci_id, **kw):
        return _meta(uci_id=uci_id, repository_url=f"https://page/{uci_id}", **kw)

    survey = tmp_path / "survey.json"
    survey.write_text(
        json.dumps(
            {
                "datasets": [
                    entry(1, name="open"),
                    entry(2, name="closed"),
                    entry(3, name="small", num_instances=1),
                    entry(4, name="taken"),
                ]
            }
        )
    )
    pages = []
    licences = {"https://page/1": "CC BY 4.0", "https://page/2": "GPL"}
    monkeypatch.setattr(w2, "first_pool_ids", lambda: {4})
    monkeypatch.setattr(w2.dr, "_text", lambda url: pages.append(url) or url)
    monkeypatch.setattr(w2.dr, "uci_licence", lambda page: {"licence": licences[page]})
    pauses = []
    monkeypatch.setattr(w2.time, "sleep", pauses.append)
    monkeypatch.setattr(w2, "SELECTION", tmp_path / "out" / "selection.json")
    assert w2.main(["select", "--survey", str(survey)]) == 0
    out = json.loads((tmp_path / "out" / "selection.json").read_text())
    assert pages == ["https://page/1", "https://page/2"]
    assert pauses == [0.3, 0.3]
    assert [(m["uci_id"], m["licence"], m["tags"]) for m in out["chosen"]] == [
        (1, "CC BY 4.0", ["time_series"])
    ]
    assert out["rejected_after_metadata"] == 2
    assert out["rejected_by_licence"] == [
        {"uci_id": 2, "name": "closed", "reason": "licence not open or not stated on the page"}
    ]
    assert len(out["checked"]) == 10 and out["checked"][4] == "-"
    assert capsys.readouterr().out == "chosen 1, licence-rejected 1\n"
    assert (tmp_path / "out" / "selection.json").read_text().endswith("}\n")


def test_the_verify_time_command_writes_the_report_and_prints_the_verdicts(
    tmp_path, monkeypatch, capsys
):
    import json

    report = {"uci:1": {"verified": True}, "uci:2": {"verified": False}}
    monkeypatch.setattr(w2, "verify_times", lambda: report)
    monkeypatch.setattr(w2, "TIME_REPORT", tmp_path / "time.json")
    assert w2.main(["verify-time"]) == 0
    assert json.loads((tmp_path / "time.json").read_text()) == report
    assert (tmp_path / "time.json").read_text().endswith("}\n")
    assert capsys.readouterr().out == "{'uci:1': True, 'uci:2': False}\n"


def test_the_fetch_command_pins_every_chosen_table_and_counts_failures(
    tmp_path, monkeypatch, capsys
):
    import json

    selection = tmp_path / "sel.json"
    selection.write_text(
        json.dumps({"chosen": [{"uci_id": 1, "name": "a"}, {"uci_id": 2, "name": "b"}]})
    )

    def pin(meta, destination):
        if meta["uci_id"] == 2:
            raise ValueError("bad csv")
        return {"uci_id": meta["uci_id"]}

    monkeypatch.setattr(w2, "SELECTION", selection)
    monkeypatch.setattr(w2, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(w2, "pin", pin)
    destination = tmp_path / "nested" / "wave"
    assert w2.main(["fetch", "--destination", str(destination)]) == 0
    assert destination.is_dir()
    out = json.loads((tmp_path / "manifest.json").read_text())
    assert out["tables"] == [{"uci_id": 1}]
    assert out["failed"] == [{"uci_id": 2, "name": "b", "reason": "ValueError('bad csv')"}]
    assert capsys.readouterr().out == "fetched 1, failed 1\n"


def test_the_fetch_command_does_not_hide_an_unexpected_error(tmp_path, monkeypatch):
    import json

    selection = tmp_path / "sel.json"
    selection.write_text(json.dumps({"chosen": [{"uci_id": 1, "name": "a"}]}))
    monkeypatch.setattr(w2, "SELECTION", selection)
    monkeypatch.setattr(w2, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(w2, "pin", lambda meta, destination: 1 / 0)
    import pytest

    with pytest.raises(ZeroDivisionError):
        w2.main(["fetch", "--destination", str(tmp_path / "d")])


def test_the_command_is_required_and_the_default_destination_is_the_wave_directory(
    tmp_path, monkeypatch
):
    import json

    import pytest

    with pytest.raises(SystemExit):
        w2.main([])
    seen = {}
    selection = tmp_path / "sel.json"
    selection.write_text(json.dumps({"chosen": []}))
    monkeypatch.setattr(w2, "SELECTION", selection)
    monkeypatch.setattr(w2, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(Path, "mkdir", lambda self, **kw: seen.setdefault("dir", self))
    assert w2.main(["fetch"]) == 0
    assert seen["dir"] == w2.WAVE_DIR
