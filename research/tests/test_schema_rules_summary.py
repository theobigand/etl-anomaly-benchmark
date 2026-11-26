"""Schema-rule baseline against the archived detectors: reading, grouping and the summary."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paired_inference as pinf  # noqa: E402
import schema_rules_summary as srs  # noqa: E402

DRAWS = 200


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _typed(root, stem, classical=None, deep=None):
    if classical is not None:
        _write(root / "classical" / f"{stem}.json", {"recall_pooled": classical})
    if deep is not None:
        _write(root / "deep" / f"{stem}.json", {"recall_pooled": deep})


def _rules(root, stem, fpr, recall):
    _write(root / f"{stem}.json", {"fpr_pooled": fpr, "recall_pooled": recall})


def _world(tmp_path):
    """Four tables of four independent sources, one fault type, hand-computable recalls."""
    rules, typed = tmp_path / "rules", tmp_path / "typed"
    base = {"uci_1": 0.9, "uci_2": 0.5, "uci_3": 1.0, "uci_4": 0.3}
    fpr = {"uci_1": 0.01, "uci_2": 0.05, "uci_3": 0.2, "uci_4": 0.04}
    archived = {
        "uci_1": {"zscore": 0.8, "iqr": 0.6, "iforest": 0.5, "lstm": 0.9},
        "uci_2": {"zscore": 0.4, "iqr": 0.6, "iforest": 0.7, "lstm": 0.5},
        "uci_3": {"zscore": 0.9, "iqr": 0.9, "iforest": 0.95, "lstm": 1.0},
        "uci_4": {"zscore": 0.1, "iqr": 0.3, "iforest": 0.2, "lstm": 0.1},
    }
    for stem, recall in base.items():
        _rules(rules, stem, fpr[stem], {"missing_value": recall})
        a = archived[stem]
        classical = {name: {"missing_value": a[name]} for name in ("zscore", "iqr", "iforest")}
        classical["transform_dedup"] = {"missing_value": 1.0}
        _typed(typed, stem, classical, {"lstm": {"missing_value": a["lstm"]}})
    return rules, typed


def test_archived_merges_both_families_and_drops_the_dedup_transform(tmp_path):
    _typed(
        tmp_path,
        "t",
        {"a": {"x": 1.0}, "transform_dedup": {"x": 0.5}},
        {"b": {"x": 0.25}},
    )
    assert srs.archived(tmp_path, "t") == {"a": {"x": 1.0}, "b": {"x": 0.25}}


def test_archived_tolerates_a_missing_family_and_a_missing_table(tmp_path):
    _typed(tmp_path, "only_deep", None, {"b": {"x": 0.25}})
    _typed(tmp_path, "only_classical", {"a": {"x": 0.75}}, None)
    assert srs.archived(tmp_path, "only_deep") == {"b": {"x": 0.25}}
    assert srs.archived(tmp_path, "only_classical") == {"a": {"x": 0.75}}
    assert srs.archived(tmp_path, "absent") == {}


def test_a_later_family_overrides_an_earlier_one_for_the_same_detector(tmp_path):
    _typed(tmp_path, "t", {"a": {"x": 0.1}}, {"a": {"x": 0.9}})
    assert srs.archived(tmp_path, "t") == {"a": {"x": 0.9}}


def test_the_constants_name_the_three_rule_detectors_and_eight_fault_types():
    assert srs.RULE_DETECTORS == ("zscore", "iqr", "great_expectations")
    assert len(srs.TYPES) == 8 and len(set(srs.TYPES)) == 8
    assert "missing_value" in srs.TYPES and "duplicate" in srs.TYPES


def test_summary_headline_and_per_type_statistics_match_a_hand_computation(tmp_path):
    rules, typed = _world(tmp_path)
    s = srs.summarise(rules, typed, DRAWS)
    assert s["tables"] == 4
    assert s["S2"]["share_tables_fpr_at_most_0.05"] == 0.75
    assert s["S2"]["median_fpr"] == pytest.approx(0.045)
    assert list(s["types"]) == ["missing_value"]
    t = s["types"]["missing_value"]
    assert t["tables"] == 4 and t["sources"] == 4
    assert t["baseline_median_recall"] == pytest.approx(0.7)
    assert t["best_archived_median_recall"] == pytest.approx(0.8)
    assert t["rule_detectors_median_recall"] == pytest.approx(0.6)
    assert t["other_detectors_median_recall"] == pytest.approx(0.65)
    assert t["tables_baseline_at_least_best"] == 0.75
    assert t["tables_baseline_at_least_0.9"] == 0.5
    best = t["baseline_minus_best"]
    assert best["units"] == 4 and best["median_difference"] == pytest.approx(0.0)
    rule = t["baseline_minus_rule_detectors"]
    assert rule["units"] == 4 and rule["median_difference"] == pytest.approx(0.1)
    expected = pinf.paired_effect(
        np.array([0.9, 0.5, 1.0, 0.3]), np.array([0.7, 0.5, 0.9, 0.2]), DRAWS
    )
    assert rule == expected


def test_the_baseline_at_least_best_share_tolerates_float_noise(tmp_path):
    rules, typed = tmp_path / "rules", tmp_path / "typed"
    _rules(rules, "uci_1", 0.0, {"missing_value": 0.7})
    _typed(
        typed,
        "uci_1",
        {"zscore": {"missing_value": 0.7 + 5e-13}, "iforest": {"missing_value": 0.1}},
        None,
    )
    t = srs.summarise(rules, typed, DRAWS)["types"]["missing_value"]
    assert t["tables_baseline_at_least_best"] == 1.0
    _rules(rules, "uci_1", 0.0, {"missing_value": 0.7})
    _typed(
        typed,
        "uci_1",
        {"zscore": {"missing_value": 0.7 + 5e-12}, "iforest": {"missing_value": 0.1}},
        None,
    )
    t = srs.summarise(rules, typed, DRAWS)["types"]["missing_value"]
    assert t["tables_baseline_at_least_best"] == 0.0


def test_a_twin_table_shares_the_source_of_its_uci_counterpart(tmp_path):
    rules, typed = tmp_path / "rules", tmp_path / "typed"
    # ADBench breastw is the twin of UCI 15: the two tables are one independent source.
    for stem, recall in (("adbench_breastw", 0.9), ("uci_15", 0.7), ("uci_2", 0.5)):
        _rules(rules, stem, 0.0, {"missing_value": recall})
        _typed(
            typed, stem, {"zscore": {"missing_value": 0.1}, "iforest": {"missing_value": 0.2}}, None
        )
    t = srs.summarise(rules, typed, DRAWS)["types"]["missing_value"]
    assert t["tables"] == 3 and t["sources"] == 2


def test_a_type_without_a_baseline_recall_or_without_archived_values_is_skipped(tmp_path):
    rules, typed = tmp_path / "rules", tmp_path / "typed"
    _rules(rules, "uci_1", 0.0, {"missing_value": None, "duplicate": 0.5})
    _typed(
        typed,
        "uci_1",
        {
            "zscore": {"missing_value": 0.4, "duplicate": 0.9},
            "iforest": {"missing_value": 0.3, "duplicate": 0.9},
        },
        None,
    )
    _rules(rules, "uci_2", 0.0, {"missing_value": 0.5, "invalid_code": 0.5})
    _typed(
        typed,
        "uci_2",
        {
            "zscore": {"missing_value": None, "invalid_code": None},
            "iforest": {"missing_value": None},
        },
        None,
    )
    _rules(rules, "uci_3", 0.0, {"missing_value": 0.5})
    _typed(
        typed, "uci_3", {"zscore": {"missing_value": 0.4}, "iforest": {"missing_value": 0.3}}, None
    )
    s = srs.summarise(rules, typed, DRAWS)
    assert list(s["types"]) == ["missing_value", "duplicate"]
    assert s["types"]["missing_value"]["tables"] == 1  # only uci_3 has both sides
    assert s["types"]["duplicate"]["tables"] == 1


def test_a_table_archived_without_any_rule_detector_is_an_error(tmp_path):
    rules, typed = tmp_path / "rules", tmp_path / "typed"
    _rules(rules, "uci_1", 0.0, {"missing_value": 0.5})
    _typed(typed, "uci_1", {"iforest": {"missing_value": 0.4}}, None)
    with pytest.raises(ValueError):
        srs.summarise(rules, typed, DRAWS)


def test_tables_are_read_in_sorted_order_and_the_names_use_the_first_underscore(tmp_path):
    rules, typed = _world(tmp_path)
    s = srs.summarise(rules, typed, DRAWS)
    assert s["tables"] == 4
    renamed = sorted(p.stem for p in rules.glob("*.json"))
    assert renamed == ["uci_1", "uci_2", "uci_3", "uci_4"]


def test_the_default_number_of_draws_is_the_one_of_the_paired_inference_module():
    import inspect

    assert inspect.signature(srs.summarise).parameters["draws"].default == pinf.DRAWS


def test_render_lists_the_headline_and_one_row_per_type(tmp_path):
    rules, typed = _world(tmp_path)
    s = srs.summarise(rules, typed, DRAWS)
    text = srs.render(s)
    lines = text.splitlines()
    assert lines[0] == "# Schema-rule baseline against the archived detectors"
    assert lines[2] == (
        "Tables: 4. Median false-positive rate on clean rows 0.045; 75% of tables at or below 0.05."
    )
    assert lines[4].startswith("| Fault type | Tables | Sources | Baseline |")
    assert lines[5] == "|---|---:|---:|---:|---:|---:|---:|---:|---|"
    assert lines[6] == (
        "| missing_value | 4 | 4 | 0.70 | 0.80 | 0.60 | 0.65 | 75% | +0.00 [-0.20, +0.00] |"
    )
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert len(lines) == 7
    assert [i for i, line in enumerate(lines) if line == ""] == [1, 3]


def test_main_writes_the_json_and_markdown_summaries_and_returns_zero(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence"
    out = evidence / "pool_extension_v3"
    rules, typed = _world(tmp_path)
    for p in rules.glob("*.json"):
        _write(out / "schema_rules" / p.name, json.loads(p.read_text()))
    for p in typed.rglob("*.json"):
        target = evidence / "pool_extension_v2" / "typed_mixed" / p.relative_to(typed)
        _write(target, json.loads(p.read_text()))
    monkeypatch.setattr(srs, "EVIDENCE", evidence)
    assert srs.main() == 0
    summary = json.loads((out / "schema_rules_summary.json").read_text())
    assert summary["tables"] == 4
    assert summary["types"]["missing_value"]["tables"] == 4
    raw = (out / "schema_rules_summary.json").read_text()
    assert raw.endswith("}\n") and raw.startswith('{\n "S2"')
    assert (out / "schema_rules_summary.md").read_text() == srs.render(summary)


def test_the_number_of_bootstrap_draws_reaches_both_paired_effects(tmp_path):
    rules, typed = _world(tmp_path)
    t = srs.summarise(rules, typed, 5)["types"]["missing_value"]
    base, best, rule = [0.9, 0.5, 1.0, 0.3], [0.9, 0.7, 1.0, 0.3], [0.7, 0.5, 0.9, 0.2]
    assert t["baseline_minus_best"] == pinf.paired_effect(np.array(base), np.array(best), 5)
    assert t["baseline_minus_rule_detectors"] == pinf.paired_effect(
        np.array(base), np.array(rule), 5
    )
