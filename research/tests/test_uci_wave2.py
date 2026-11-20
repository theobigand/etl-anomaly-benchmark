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
