"""The documented ETL paths must retain their separate scientific roles."""

from pathlib import Path


def test_etl_paths_document_standard_and_typed_routes():
    text = (
        Path(__file__).resolve().parents[1] / "docs/thesis-remediation/ETL_PATHS_2026-11-07.md"
    ).read_text()
    for phrase in (
        "run_pipeline",
        "exact drop_duplicates",
        "transform_dedup",
        "The typed study does not go through `run_pipeline`",
        "group_id",
        "T062 and T063",
    ):
        assert phrase in text
