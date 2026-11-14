# ruff: noqa: E501
"""The UCI pool command in detail: call arguments, throttle, written text and help."""

import json
import sys
from pathlib import Path

import pytest
from test_uci_pool_contracts import _meta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uci_pool as up  # noqa: E402


def test_a_candidate_with_no_licence_entry_at_all_is_rejected_for_its_licence():
    chosen, rejected = up.select([_meta(1)], {})
    assert chosen == [] and rejected == [(_meta(1), "licence not open or not stated on the page")]


def test_the_crawl_waits_a_third_of_a_second_between_requests_unless_told_otherwise():
    waits = []
    pages = {f"{up.API}/datasets/list": json.dumps({"data": [{"id": 1}, {"id": 2}]})}
    for i in (1, 2):
        pages[f"{up.API}/dataset?id={i}"] = json.dumps({"data": {"uci_id": i}})
    up.crawl(pages.__getitem__, sleep=waits.append)
    assert waits == [0.3, 0.3]
    waits.clear()
    up.crawl(pages.__getitem__, sleep=waits.append, delay=2.5)
    assert waits == [2.5, 2.5]


def test_the_survey_mode_crawls_with_the_catalogue_reader_and_writes_sorted_indented_text(
    tmp_path, monkeypatch
):
    seen = {}
    monkeypatch.setattr(
        up, "crawl", lambda fetch: seen.update(fetch=fetch) or {"failed": [9], "datasets": [1]}
    )
    out = tmp_path / "survey.json"
    up.main(["--survey", str(out), "--output", str(tmp_path / "x.json")])
    assert seen["fetch"] is up.dr._text
    assert (
        out.read_text()
        == json.dumps({"failed": [9], "datasets": [1]}, indent=1, sort_keys=True) + "\n"
    )


def test_the_select_mode_pauses_a_third_of_a_second_after_each_page_and_keeps_the_page_url(
    tmp_path, monkeypatch
):
    survey = tmp_path / "survey.json"
    survey.write_text(json.dumps({"datasets": [_meta(1), _meta(2)]}))
    pauses = []
    monkeypatch.setattr(up.dr, "_text", lambda url: url)
    monkeypatch.setattr(up.dr, "uci_licence", lambda page: {"licence": "CC BY 4.0"})
    monkeypatch.setattr(up.time, "sleep", pauses.append)
    seen = {}
    real = up.select
    monkeypatch.setattr(
        up,
        "select",
        lambda survey_rows, licences: seen.update(licences=licences) or real(survey_rows, licences),
    )
    out = tmp_path / "chosen.json"
    up.main(["--select", str(survey), "--output", str(out)])
    assert pauses == [0.3, 0.3]
    assert seen["licences"] == {
        1: {"licence": "CC BY 4.0", "url": _meta(1)["repository_url"]},
        2: {"licence": "CC BY 4.0", "url": _meta(2)["repository_url"]},
    }
    text = out.read_text()
    assert text == json.dumps(json.loads(text), indent=1, sort_keys=True) + "\n"


def test_the_curate_mode_writes_sorted_indented_text(tmp_path, capsys):
    chosen = tmp_path / "chosen.json"
    chosen.write_text(json.dumps({"chosen": [_meta(1), _meta(2)]}))
    out = tmp_path / "pool.json"
    up.main(["--curate", str(chosen), "--output", str(out)])
    text = out.read_text()
    assert text == json.dumps(json.loads(text), indent=1, sort_keys=True) + "\n"
    assert capsys.readouterr().out == "kept 2, dropped 0\n"


def test_each_mode_option_is_a_path_and_the_output_is_required(tmp_path):
    with pytest.raises(SystemExit) as stop:
        up.main(["--survey", str(tmp_path / "s.json")])
    assert stop.value.code == 2


def test_the_help_describes_each_mode(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "400")
    with pytest.raises(SystemExit):
        up.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "--survey SURVEY crawl the catalogue metadata to this file" in text
    assert "--select SELECT survey file to filter" in text
    assert "--curate CURATE selection file to curate and split in panels" in text
    assert "--output OUTPUT" in text
