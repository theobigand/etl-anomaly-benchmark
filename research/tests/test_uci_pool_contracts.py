"""Rejection reasons, strata, curation, panels, crawl and the modes of the UCI pool command."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uci_pool as up  # noqa: E402


def _meta(uci_id=1, **over):
    base = {
        "uci_id": uci_id,
        "name": f"set{uci_id}",
        "num_instances": 1000,
        "num_features": 10,
        "characteristics": ["Tabular"],
        "tasks": ["Classification"],
        "data_url": "https://x/data.zip",
        "has_missing_values": "no",
        "feature_types": ["Real"],
        "area": "Physics",
        "repository_url": f"https://archive.ics.uci.edu/dataset/{uci_id}",
    }
    base.update(over)
    return base


def test_a_usable_dataset_has_no_rejection_and_every_fault_is_named_alone():
    assert up.rejection(_meta()) is None
    faults = {
        "rows (299)": {"num_instances": 299},
        "rows (1000001)": {"num_instances": 1_000_001},
        "rows (None)": {"num_instances": None},
        "features (3)": {"num_features": 3},
        "features (301)": {"num_features": 301},
        "features (None)": {"num_features": None},
        "modality": {"characteristics": ["Tabular", "Image"]},
        "task": {"tasks": ["Clustering"]},
        "download": {"data_url": ""},
    }
    for reason, change in faults.items():
        assert up.rejection(_meta(**change)) == reason


def test_limits_are_inclusive_and_several_faults_are_joined_in_order():
    for edge in (
        {"num_instances": 300},
        {"num_instances": 1_000_000},
        {"num_features": 4},
        {"num_features": 300},
    ):
        assert up.rejection(_meta(**edge)) is None
    both = _meta(
        num_instances=10, num_features=1, tasks=[], data_url=None, characteristics=["Text"]
    )
    assert up.rejection(both) == "rows (10); features (1); modality; task; download"
    assert up.rejection(_meta(characteristics=None, tasks=["Regression"])) is None
    assert (up.MIN_ROWS, up.MAX_ROWS, up.MIN_FEATURES, up.MAX_FEATURES) == (300, 1_000_000, 4, 300)


@pytest.mark.parametrize(
    ("rows", "size"),
    [
        (1999, "tiny"),
        (2000, "small"),
        (19_999, "small"),
        (20_000, "medium"),
        (199_999, "medium"),
        (200_000, "large"),
    ],
)
def test_the_size_class_changes_exactly_at_its_edges(rows, size):
    assert up.strata(_meta(num_instances=rows))["size"] == size


@pytest.mark.parametrize(("features", "dim"), [(10, "low"), (11, "mid"), (50, "mid"), (51, "high")])
def test_the_dimension_class_changes_exactly_at_its_edges(features, dim):
    assert up.strata(_meta(num_features=features))["dim"] == dim


def test_the_other_tags_read_missing_values_types_time_and_area():
    tags = up.strata(
        _meta(
            has_missing_values="yes",
            feature_types=["Categorical", "Real"],
            characteristics=["Time-Series"],
            area="Biology",
        )  # fmt: skip
    )
    assert tags == {
        "size": "tiny", "dim": "low", "missing": True, "mixed_types": True,
        "time": True, "domain": "Biology",
    }  # fmt: skip
    plain = up.strata(_meta(feature_types=None, characteristics=None))
    assert plain["missing"] is False and plain["mixed_types"] is False and plain["time"] is False


def test_selection_keeps_open_licences_only_and_records_the_reason_of_each_rejection():
    catalogue = [_meta(1), _meta(2), _meta(3, num_instances=5), _meta(4)]
    licences = {1: {"licence": "CC BY 4.0"}, 2: {"licence": "GPL"}, 4: {"licence": "CC0 1.0"}}
    chosen, rejected = up.select(catalogue, licences)
    assert [m["uci_id"] for m in chosen] == [1, 4]
    assert [(m["uci_id"], r) for m, r in rejected] == [
        (2, "licence not open or not stated on the page"),
        (3, "rows (5)"),
    ]
    assert sorted(up.ACCEPTED) == ["CC BY 4.0", "CC0 1.0"]


def test_curation_drops_duplicates_and_synthetic_or_game_sets_with_a_reason():
    chosen = [_meta(20), _meta(107), _meta(22), _meta(5)]
    kept, dropped = up.curate(chosen)
    assert [m["uci_id"] for m in kept] == [5]
    assert [(m["uci_id"], r) for m, r in dropped] == [
        (20, "duplicate of 2"),
        (107, up.CURATION_EXCLUSIONS[107]),
        (22, up.CURATION_EXCLUSIONS[22]),
    ]


def test_each_panel_collects_the_sets_that_answer_its_question():
    pool = [
        _meta(1, has_missing_values="yes"),
        _meta(2, feature_types=["Categorical"]),
        _meta(3, characteristics=["Time-Series"]),
        _meta(4, num_instances=500),
        _meta(5, num_instances=200_000),
        _meta(6, num_features=100),
        _meta(7, num_instances=501, num_features=99),
    ]
    out = up.panels(pool)
    assert out == {
        "missing_values": [1], "mixed_types": [2], "temporal": [3],
        "stress_tiny": [4], "stress_large": [5], "stress_wide": [6],
    }  # fmt: skip


def test_the_crawl_lists_then_reads_each_dataset_pauses_between_them_and_records_failures():
    asked, pauses = [], []

    def fetch(url):
        asked.append(url)
        if url.endswith("/datasets/list"):
            return json.dumps({"data": [{"id": 1}, {"id": 2}, {"id": 3}]})
        if url.endswith("id=2"):
            raise OSError("down")
        return json.dumps({"data": {"uci_id": int(url[-1])}})

    out = up.crawl(fetch, sleep=pauses.append, delay=0.5)
    assert asked[0] == f"{up.API}/datasets/list" and asked[1] == f"{up.API}/dataset?id=1"
    assert out == {"datasets": [{"uci_id": 1}, {"uci_id": 3}], "failed": [2]}
    assert pauses == [0.5, 0.5, 0.5]
    bad = up.crawl(
        lambda url: json.dumps({"data": [{"id": 9}]}) if "list" in url else "not json",
        sleep=lambda s: None,
    )
    assert bad == {"datasets": [], "failed": [9]}
    missing_key = up.crawl(
        lambda url: json.dumps({"data": [{"id": 4}]}) if "list" in url else "{}",
        sleep=lambda s: None,
    )
    assert missing_key["failed"] == [4]


def test_the_balance_report_counts_each_tag_value():
    report = up.balance_report([_meta(1), _meta(2, num_instances=50_000), _meta(3, area=None)])
    assert report["total"] == 3 and report["size"] == {"tiny": 2, "medium": 1}
    assert report["dim"] == {"low": 3} and report["missing"] == {False: 3}
    assert report["domain"] == {"Physics": 2, None: 1}
    assert set(report) == {"total", "size", "dim", "missing", "mixed_types", "time", "domain"}


def test_the_curate_mode_writes_the_split_the_panels_and_the_report(tmp_path, capsys):
    source = tmp_path / "selection.json"
    source.write_text(
        json.dumps({"chosen": [_meta(20), _meta(5), _meta(6, has_missing_values="yes")]})
    )
    out = tmp_path / "new" / "curated.json"
    assert up.main(["--curate", str(source), "--output", str(out)]) == 0
    assert capsys.readouterr().out == "kept 2, dropped 1\n"
    text = out.read_text()
    document = json.loads(text)
    assert text == json.dumps(document, indent=1, sort_keys=True) + "\n"
    assert set(document) == {"kept", "dropped", "panels", "report"}
    assert document["dropped"] == [{"uci_id": 20, "name": "set20", "reason": "duplicate of 2"}]
    assert document["panels"]["missing_values"] == [6] and document["report"]["total"] == 2


def test_the_survey_mode_crawls_the_catalogue_and_reports_the_counts(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(up, "crawl", lambda fetch: {"datasets": [1, 2], "failed": [9]})
    out = tmp_path / "survey.json"
    assert up.main(["--survey", str(out), "--output", str(tmp_path / "unused.json")]) == 0
    assert capsys.readouterr().out == "surveyed 2 datasets, 1 failed\n"
    assert json.loads(out.read_text()) == {"datasets": [1, 2], "failed": [9]}
    assert not (tmp_path / "unused.json").exists()


def test_the_select_mode_reads_pages_only_for_usable_candidates_and_records_the_check_date(
    tmp_path, monkeypatch, capsys
):
    survey = tmp_path / "survey.json"
    survey.write_text(json.dumps({"datasets": [_meta(1), _meta(2), _meta(3, num_instances=5)]}))
    pages = []
    monkeypatch.setattr(up.dr, "_text", lambda url: pages.append(url) or url)
    monkeypatch.setattr(
        up.dr,
        "uci_licence",
        lambda page: {"licence": "CC BY 4.0" if page.endswith("/1") else "GPL", "text": "t"},
    )
    monkeypatch.setattr(up.time, "sleep", lambda s: None)
    out = tmp_path / "chosen.json"
    assert up.main(["--select", str(survey), "--output", str(out)]) == 0
    assert capsys.readouterr().out == "chosen 1, rejected 2\n"
    assert pages == [_meta(1)["repository_url"], _meta(2)["repository_url"]]
    document = json.loads(out.read_text())
    assert set(document) == {"checked", "chosen", "rejected", "report"}
    assert (
        document["chosen"][0]["licence"] == "CC BY 4.0"
        and document["chosen"][0]["strata"]["size"] == "tiny"
    )
    assert document["rejected"] == [
        {"uci_id": 2, "name": "set2", "reason": "licence not open or not stated on the page"},
        {"uci_id": 3, "name": "set3", "reason": "rows (5)"},
    ]
    assert len(document["checked"]) == 10 and document["checked"][4] == "-"
    with pytest.raises(SystemExit) as stop:
        up.main([])
    assert stop.value.code == 2
