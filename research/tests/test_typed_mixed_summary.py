"""Mixed-schema summary: sources, not entries, are the units."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import typed_mixed_summary as tms  # noqa: E402


def _frame():
    rows = []
    for ident, source, recall in [
        ("adbench:satellite", "uci:146", 0.2),
        ("uci:146", "uci:146", 0.4),
    ]:
        rows.append(
            {
                "id": ident,
                "source": source,
                "tier": "A",
                "numeric_only": True,
                "method": "knn",
                "type": "invalid_code",
                "recall": recall,
                "test_n": 10,
            }
        )
    rows.append(
        {
            "id": "uci:9",
            "source": "uci:9",
            "tier": "B",
            "numeric_only": False,
            "method": "knn",
            "type": "invalid_code",
            "recall": 1.0,
            "test_n": 10,
        }
    )
    return pd.DataFrame(rows)


def test_entries_of_one_source_are_averaged_before_any_median():
    out = tms.by_source(_frame())
    assert sorted(out["source"]) == ["uci:146", "uci:9"]
    assert out.set_index("source").loc["uci:146", "recall"] == pytest.approx(0.3)


def test_median_intervals_count_sources_not_entries():
    row = tms.medians(_frame())[0]
    assert row["sources"] == 2 and row["median"] == pytest.approx(0.65)


def test_m2_compares_rule_and_distance_detectors_on_categorical_faults():
    frame = pd.concat([_frame(), _frame().assign(method="zscore", recall=0.0)], ignore_index=True)
    out = tms.m2(frame)
    assert out["invalid_code"]["rules"] == 0.0 and out["invalid_code"][
        "distance_density"
    ] == pytest.approx(0.65)
