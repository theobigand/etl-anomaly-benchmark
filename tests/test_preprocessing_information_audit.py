"""The documented feature-access limitation must remain explicit."""

from pathlib import Path


def test_audit_records_input_asymmetry_and_train_only_boundary():
    text = (
        Path(__file__).resolve().parents[1]
        / "docs/thesis-remediation/PREPROCESSING_INFORMATION_AUDIT_2026-11-07.md"
    ).read_text()
    for phrase in (
        "prepare_frozen",
        "vocabulaire",
        "imputation médiane",
        "plus grande signifie",
        "asymétrie",
    ):
        assert phrase in text
