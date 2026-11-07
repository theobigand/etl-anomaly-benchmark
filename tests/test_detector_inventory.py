"""The published detector inventory must stay synchronized with the registry."""

import re
from pathlib import Path

from etl_benchmark import registry


def test_inventory_documents_every_comparable_registered_detector_once():
    text = (Path(__file__).resolve().parents[1] / "verification/detector_inventory.md").read_text()
    rows = re.findall(r"^\| `([^`]+)` \|", text, re.MULTILINE)
    expected = [*registry.RULE_NAMES, *registry.ML_NAMES, *registry.DEEP_NAMES]
    assert rows == expected
    assert len(rows) == 17


def test_inventory_states_the_required_comparison_fields():
    text = (Path(__file__).resolve().parents[1] / "verification/detector_inventory.md").read_text()
    for field in (
        "Family",
        "Implementation origin",
        "Accepted input",
        "Preprocessing",
        "Training cap",
        "Score and direction",
        "Decision threshold",
    ):
        assert field in text
