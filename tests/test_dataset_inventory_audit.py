"""The dataset inventory must retain its population and independence limits."""

from pathlib import Path


def test_dataset_audit_separates_populations_and_partition_limit():
    text = (
        Path(__file__).resolve().parents[1]
        / "docs/thesis-remediation/DATASET_INVENTORY_AUDIT_2026-11-07.md"
    ).read_text()
    for phrase in (
        "152 fichiers",
        "100 problèmes",
        "58 porteurs",
        "19 occurrences",
        "T089 reste donc ouvert",
    ):
        assert phrase in text
