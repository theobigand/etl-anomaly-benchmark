"""Choosing relevant datasets from the UCI catalogue: eligibility, strata and rights."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uci_pool as up  # noqa: E402


def _meta(**over):
    base = {
        "uci_id": 1,
        "name": "Toy",
        "area": "Health and Medicine",
        "tasks": ["Classification"],
        "characteristics": ["Tabular", "Multivariate"],
        "num_instances": 5000,
        "num_features": 12,
        "feature_types": ["Real"],
        "has_missing_values": "no",
        "data_url": "https://archive.ics.uci.edu/static/public/1/data.csv",
        "dataset_doi": "10.24432/C5X",
    }
    return {**base, **over}


def test_a_plain_numeric_table_is_eligible_with_no_reason_to_reject():
    assert up.rejection(_meta()) is None


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"num_instances": 100}, "rows"),
        ({"num_instances": 5_000_000}, "rows"),
        ({"num_features": 2}, "features"),
        ({"num_features": 5000}, "features"),
        ({"characteristics": ["Image"]}, "modality"),
        ({"characteristics": ["Text"]}, "modality"),
        ({"characteristics": ["Sequential"]}, "modality"),
        ({"tasks": ["Clustering"]}, "task"),
        ({"data_url": None}, "download"),
        ({"num_instances": None}, "rows"),
    ],
)
def test_ineligible_datasets_are_rejected_with_a_reason(over, reason):
    assert reason in up.rejection(_meta(**over))


def test_strata_describe_how_the_dataset_can_be_used():
    tags = up.strata(
        _meta(
            num_instances=3000,
            num_features=60,
            has_missing_values="yes",
            feature_types=["Real", "Categorical"],
        )
    )
    assert tags["size"] == "small" and tags["dim"] == "high"
    assert tags["missing"] is True and tags["mixed_types"] is True and tags["time"] is False
    assert tags["domain"] == "Health and Medicine"


def test_time_series_are_tagged_for_the_temporal_questions():
    assert up.strata(_meta(characteristics=["Time-Series", "Multivariate"]))["time"] is True


@pytest.mark.parametrize(
    ("rows", "size"),
    [
        (500, "tiny"),
        (1999, "tiny"),
        (2000, "small"),
        (19999, "small"),
        (20000, "medium"),
        (199999, "medium"),
        (200000, "large"),
    ],
)
def test_size_bins(rows, size):
    assert up.strata(_meta(num_instances=rows))["size"] == size


def test_selection_keeps_every_eligible_licensed_dataset_and_reports_the_rest():
    catalogue = [
        _meta(uci_id=1, name="A"),
        _meta(uci_id=2, name="B", num_instances=10),
        _meta(uci_id=3, name="C"),
    ]
    licences = {1: {"licence": "CC BY 4.0"}, 3: {"licence": None}}
    chosen, rejected = up.select(catalogue, licences)
    assert [m["uci_id"] for m in chosen] == [1]
    reasons = {m["uci_id"]: r for m, r in rejected}
    assert "rows" in reasons[2] and "licence" in reasons[3]


def test_the_catalogue_crawl_is_polite_and_survives_a_missing_dataset():
    calls = []

    def fetch(url):
        calls.append(url)
        if url.endswith("list"):
            return '{"data": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]}'
        if url.endswith("id=2"):
            raise OSError("gone")
        return '{"data": {"uci_id": 1, "name": "A"}}'

    slept = []
    out = up.crawl(fetch, sleep=slept.append, delay=0.1)
    assert [m["uci_id"] for m in out["datasets"]] == [1] and out["failed"] == [2]
    assert slept == [0.1, 0.1]


def test_the_balanced_report_counts_datasets_per_stratum():
    chosen = [_meta(uci_id=i, num_instances=n) for i, n in enumerate([500, 3000, 3500, 50000], 1)]
    report = up.balance_report(chosen)
    assert report["size"] == {"tiny": 1, "small": 2, "medium": 1}
    assert report["total"] == 4


# --- curation: relevance for ETL data quality, no synthetic or duplicate datasets ---


def test_curation_removes_synthetic_rule_generated_and_duplicate_versions_with_a_reason():
    pool = [_meta(uci_id=i, name=f"D{i}") for i in (2, 20, 107, 26, 5)]
    kept, dropped = up.curate(pool)
    assert {m["uci_id"] for m in kept} == {2, 5}
    reasons = {m["uci_id"]: r for m, r in dropped}
    assert "duplicate of 2" in reasons[20]
    assert "synthetic" in reasons[107] and "game" in reasons[26]


def test_every_curation_rule_has_a_stated_reason_and_no_duplicate_points_to_itself():
    assert all(isinstance(reason, str) and reason for reason in up.CURATION_EXCLUSIONS.values())
    assert all(a != b for a, b in up.DUPLICATE_OF.items())
    assert set(up.DUPLICATE_OF.values()).isdisjoint(up.DUPLICATE_OF)


def test_panels_group_datasets_by_the_question_they_can_answer():
    pool = [
        _meta(uci_id=1, has_missing_values="yes", num_instances=3000),
        _meta(uci_id=2, feature_types=["Real", "Categorical"], num_instances=500),
        _meta(uci_id=3, characteristics=["Time-Series"], num_instances=300000),
        _meta(uci_id=4, num_features=250, num_instances=3000),
    ]
    panels = up.panels(pool)
    assert panels["missing_values"] == [1] and panels["mixed_types"] == [2]
    assert panels["temporal"] == [3]
    assert (
        panels["stress_tiny"] == [2]
        and panels["stress_large"] == [3]
        and panels["stress_wide"] == [4]
    )
