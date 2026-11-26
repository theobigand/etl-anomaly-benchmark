"""Pilot summary: recall by detector and mechanism, and the four preregistered checks."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline_batch as pb  # noqa: E402
import pipeline_batch_summary as ps  # noqa: E402


def _arm(rule, learned, stat=0.5):
    """An arm where each detector has one recall per mechanism (same at the three severities)."""
    detectors = ["constraint_rules", "distribution_distance", "isolation_forest", "random"]
    results = {}
    for d in detectors:
        results[d] = {}
        for m in pb.MECHANISMS:
            r = {
                "constraint_rules": rule,
                "isolation_forest": learned,
                "distribution_distance": stat,
            }.get(d, 0.05)
            r = r(m) if callable(r) else r
            results[d][m] = {lv: {"recall": r, "false_alert_rate": 0.05} for lv in ("0", "1", "2")}
    return {"detectors": detectors, "results": results}


def _source(i, rule, learned, dirty_drop=0.1):
    clean = _arm(rule, learned)
    dirty = _arm(lambda m: rule(m) - dirty_drop if callable(rule) else rule - dirty_drop, learned)
    return {"id": f"uci:{i}", "arms": {"clean_reference": clean, "contaminated_reference": dirty}}


def test_hypotheses_are_read_from_the_sources_and_few_sources_are_descriptive_only():
    rule = lambda m: 0.95 if m in ps.CLEAR else 0.1  # noqa: E731
    sources = [_source(i, rule, 0.6) for i in range(3)]
    s = ps.summarise(sources)
    assert s["descriptive_only"] is True and len(s["sources"]) == 3
    assert all(v == 1.0 for v in s["B1_share_of_sources_recall_ge_0.9"].values())
    b2 = s["B2_rules_vs_best_learned"]["silent_corruption"]
    assert b2["median_gap"] == pytest.approx(0.5) and b2["share_ge_0.2"] == 1.0
    assert s["B3_best_family_by_mechanism"]["partial_load"] == "rules"
    assert s["B3_best_family_by_mechanism"]["silent_corruption"] == "learned"
    assert s["B3_holds"] is True
    assert s["B4_mean_recall_change_contaminated_minus_clean"]["learned"] == pytest.approx(0.0)
    assert s["B4_mean_recall_change_contaminated_minus_clean"]["rules"] < 0
    assert s["median_recall_at_budget"]["random"]["partial_load"]["high"] == pytest.approx(0.05)


def test_one_family_best_everywhere_fails_b3():
    sources = [_source(i, 0.9, 0.2) for i in range(2)]
    assert ps.summarise(sources)["B3_holds"] is False


def test_the_report_names_every_detector_and_marks_the_pilot_descriptive(tmp_path):
    sources = [_source(i, 0.9, 0.2) for i in range(2)]
    text = ps.render(ps.summarise(sources))
    assert "Descriptive only" in text and "constraint_rules" in text and "B4" in text
    assert text.count("| random |") == 1


def test_a_second_run_of_the_same_sources_adds_its_detectors_and_feeds_b5(tmp_path):
    import json

    full, compact = tmp_path / "full", tmp_path / "compact"
    full.mkdir()
    compact.mkdir()
    for i in range(2):
        src = _source(i, 0.9, 0.2)
        (full / f"uci_{i}.json").write_text(json.dumps(src))
        extra = _source(i, 0.9, 0.8)
        for arm in extra["arms"].values():
            arm["results"] = {"isolation_forest_compact": arm["results"]["isolation_forest"]}
            arm["detectors"] = ["isolation_forest_compact"]
        (compact / f"uci_{i}.json").write_text(json.dumps(extra))
    sources = ps.load(full, compact)
    assert "isolation_forest_compact" in sources[0]["arms"]["clean_reference"]["detectors"]
    s = ps.summarise(sources)
    assert s["B5_compact_minus_full_profile_best_learned"]["partial_load"][
        "median_gain"
    ] == pytest.approx(0.6)
    assert (
        s["B5_compact_minus_full_profile_best_learned"]["partial_load"]["share_gain_positive"]
        == 1.0
    )


# ---------------------------------------------------------------------------------------------
# Hand-computed fixtures: every recall is set explicitly, so each statistic has one right value.
# ---------------------------------------------------------------------------------------------
DETS = (
    "constraint_rules",
    "distribution_distance",
    "isolation_forest",
    "isolation_forest_compact",
    "random",
)


def _spec_arm(spec=None, detectors=DETS, false_alert=0.05, omit=()):
    """``spec`` maps (detector, mechanism) to the recalls at severities 0, 1 and 2 (default 0.1)."""
    spec = spec or {}
    results = {}
    for d in detectors:
        results[d] = {}
        for m in pb.MECHANISMS:
            if (d, m) in omit:
                continue
            values = spec.get((d, m), (0.1, 0.1, 0.1))
            results[d][m] = {
                str(i): {"recall": v, "false_alert_rate": false_alert} for i, v in enumerate(values)
            }
    return {"detectors": list(detectors), "results": results}


def _src(i, spec=None, dirty=None, **kw):
    return {
        "id": f"uci:{i}",
        "arms": {
            "clean_reference": _spec_arm(spec, **kw),
            "contaminated_reference": _spec_arm(spec if dirty is None else dirty, **kw),
        },
    }


def test_the_module_constants_name_the_mechanism_groups_and_the_descriptive_limit():
    assert ps.CLEAR == (
        "partial_load",
        "duplicate_load",
        "stale_batch",
        "null_spike",
        "schema_drop",
    )
    assert ps.HARD == ("silent_corruption", "distribution_shift")
    assert ps.DESCRIPTIVE_BELOW == 15


def test_recall_averages_the_requested_severities_and_is_none_when_nothing_matches():
    arm = _spec_arm({("random", "partial_load"): (0.2, 0.4, 0.9)})
    assert ps.recall(arm, "random", "partial_load", ("0", "1", "2")) == pytest.approx(0.5)
    assert ps.recall(arm, "random", "partial_load", ("1",)) == 0.4
    assert ps.recall(arm, "random", "partial_load", ("1", "2")) == pytest.approx(0.65)
    assert ps.recall(arm, "random", "partial_load", ("3",)) is None
    assert ps.recall(arm, "random", "partial_load", ("0", "3")) == 0.2
    assert ps.recall(arm, "absent", "partial_load", ("0",)) is None
    assert ps.recall(arm, "random", "absent", ("0",)) is None


def test_family_best_takes_the_highest_recall_of_each_family():
    spec = {
        ("constraint_rules", "stale_batch"): (0.3, 0.3, 0.3),
        ("distribution_distance", "stale_batch"): (0.5, 0.5, 0.5),
        ("isolation_forest", "stale_batch"): (0.4, 0.4, 0.4),
        ("isolation_forest_compact", "stale_batch"): (0.0, 0.0, 0.0),
        ("random", "stale_batch"): (0.05, 0.05, 0.05),
    }
    best = ps.family_best(_spec_arm(spec), "stale_batch", ("0", "1", "2"))
    assert best == pytest.approx({"rules": 0.3, "statistical": 0.5, "learned": 0.4, "floor": 0.05})
    zero = {("isolation_forest", "stale_batch"): (0.0,) * 3}
    only = _spec_arm(zero, detectors=("isolation_forest",))
    assert ps.family_best(only, "stale_batch", ("0",)) == {"learned": 0.0}
    assert ps.family_best(_spec_arm(), "stale_batch", ("9",)) == {}


def test_load_reads_the_result_files_of_the_sources_in_sorted_order(tmp_path):
    for i in (2, 0, 1):
        (tmp_path / f"uci_{i}.json").write_text(json.dumps(_src(i)))
    (tmp_path / "other.json").write_text(json.dumps({"id": "x"}))
    assert [s["id"] for s in ps.load(tmp_path)] == ["uci:0", "uci:1", "uci:2"]


def _extra(i, detectors, value):
    return _src(
        i, {(d, m): (value,) * 3 for d in detectors for m in pb.MECHANISMS}, detectors=detectors
    )


def test_merging_a_second_run_never_replaces_an_existing_detector_and_orders_the_list(tmp_path):
    main, extra = tmp_path / "main", tmp_path / "extra"
    main.mkdir()
    extra.mkdir()
    (main / "uci_0.json").write_text(json.dumps(_src(0)))
    (main / "uci_1.json").write_text(json.dumps(_src(1)))
    (extra / "uci_0.json").write_text(
        json.dumps(_extra(0, ("random", "isolation_forest_compact", "ecod_compact"), 0.9))
    )
    sources = ps.load(main, extra)
    arm = sources[0]["arms"]["clean_reference"]
    # random already existed and keeps its own results; the two new detectors are added
    assert arm["results"]["random"]["partial_load"]["0"]["recall"] == 0.1
    assert arm["results"]["ecod_compact"]["partial_load"]["0"]["recall"] == 0.9
    assert arm["detectors"] == [d for d in pb.DETECTORS if d in arm["results"]]
    assert "ecod_compact" in sources[0]["arms"]["contaminated_reference"]["detectors"]
    # a source without a counterpart in the second run is left untouched
    assert "ecod_compact" not in sources[1]["arms"]["clean_reference"]["results"]
    assert sources[1]["arms"]["clean_reference"]["detectors"] == list(DETS)


def test_the_merge_matches_files_by_the_source_id_with_the_colon_replaced(tmp_path):
    main, extra = tmp_path / "main", tmp_path / "extra"
    main.mkdir()
    extra.mkdir()
    (main / "uci_7.json").write_text(json.dumps(_src(7)))
    (extra / "uci_7.json").write_text(json.dumps(_extra(7, ("ecod_compact",), 0.9)))
    (extra / "uci_8.json").write_text(json.dumps(_extra(8, ("pca_compact",), 0.9)))
    (extra / "notes.json").write_text("{}")
    (source,) = ps.load(main, extra)
    assert "ecod_compact" in source["arms"]["clean_reference"]["results"]
    assert "pca_compact" not in source["arms"]["clean_reference"]["results"]


def test_the_table_reports_the_median_over_sources_at_each_severity():
    low_mid_high = {
        0: (0.2, 0.4, 0.6),
        1: (0.4, 0.6, 0.8),
        2: (0.9, 0.9, 1.0),
    }
    sources = [_src(i, {("constraint_rules", "partial_load"): v}) for i, v in low_mid_high.items()]
    row = ps.summarise(sources)["median_recall_at_budget"]["constraint_rules"]["partial_load"]
    assert row == {
        "low": pytest.approx(0.4),
        "medium": pytest.approx(0.6),
        "high": pytest.approx(0.8),
    }
    other = ps.summarise(sources)["median_recall_at_budget"]["constraint_rules"]["stale_batch"]
    assert other == {"low": 0.1, "medium": 0.1, "high": 0.1}


def test_detectors_are_listed_in_the_registry_order_and_only_where_they_ran():
    sources = [_src(0), _src(1, detectors=("random", "constraint_rules"))]
    table = ps.summarise(sources)["median_recall_at_budget"]
    assert list(table) == [
        "constraint_rules",
        "distribution_distance",
        "isolation_forest",
        "isolation_forest_compact",
        "random",
    ]
    only_first = ps.summarise([_src(0), _src(1, detectors=("constraint_rules",))])
    # the median of a detector uses the sources where it ran: one value here
    assert only_first["median_recall_at_budget"]["random"]["partial_load"]["low"] == 0.1


def test_a_missing_mechanism_leaves_an_empty_row_and_a_dash_in_the_report():
    omit = {("random", "unit_change")}
    summary = ps.summarise([_src(0, omit=omit), _src(1, omit=omit)])
    row = summary["median_recall_at_budget"]["random"]
    assert row["unit_change"] == {} and row["partial_load"]["low"] == 0.1
    lines = ps.render(summary).splitlines()
    compact = next(ln for ln in lines if ln.startswith("| random |"))
    cells = [c.strip() for c in compact.strip("|").split("|")]
    assert cells[1 + pb.MECHANISMS.index("unit_change")] == "-"
    assert cells[1] == "0.10"


def test_the_false_alert_rate_is_the_median_over_sources_of_each_sources_mean():
    sources = [_src(0, false_alert=0.01), _src(1, false_alert=0.05), _src(2, false_alert=0.30)]
    far = ps.summarise(sources)["median_false_alert_rate"]
    assert far["random"] == pytest.approx(0.05)
    mixed = _src(3)
    for m in pb.MECHANISMS:
        for level, value in zip("012", (0.0, 0.1, 0.2), strict=True):
            mixed["arms"]["clean_reference"]["results"]["random"][m][level]["false_alert_rate"] = (
                value
            )
    assert ps.summarise([mixed])["median_false_alert_rate"]["random"] == pytest.approx(0.1)


def test_b1_counts_sources_whose_rule_recall_reaches_point_nine_at_medium_and_high():
    def spec(levels):
        return {("constraint_rules", "partial_load"): levels}

    sources = [
        _src(0, spec((0.0, 0.8, 1.0))),  # (0.8 + 1.0) / 2 = 0.9: reaches the bar
        _src(1, spec((1.0, 0.8, 0.98))),  # 0.89: below, the low severity is not used
        _src(2, spec((0.0, 1.0, 1.0))),
        _src(3, spec((1.0, 0.0, 1.0))),  # 0.5
    ]
    b1 = ps.summarise(sources)["B1_share_of_sources_recall_ge_0.9"]
    assert list(b1) == list(ps.CLEAR)
    assert b1["partial_load"] == 0.5
    assert b1["duplicate_load"] == 0.0


def test_b2_compares_the_best_learned_variant_with_the_rules_on_the_hard_mechanisms():
    spec = {
        ("constraint_rules", "silent_corruption"): (0.1, 0.2, 0.3),  # mean 0.2
        ("isolation_forest", "silent_corruption"): (0.5, 0.5, 0.5),
        ("isolation_forest_compact", "silent_corruption"): (0.9, 0.9, 0.9),
        ("distribution_distance", "silent_corruption"): (1.0, 1.0, 1.0),  # not a learned detector
        ("constraint_rules", "distribution_shift"): (0.25, 0.9, 0.9),  # only severity 0 counts
        ("isolation_forest", "distribution_shift"): (0.5, 0.0, 0.0),
    }
    flat = {
        ("constraint_rules", "silent_corruption"): (0.4, 0.4, 0.4),
        ("isolation_forest", "silent_corruption"): (0.5, 0.5, 0.5),
        ("constraint_rules", "distribution_shift"): (0.5, 0.5, 0.5),
        ("isolation_forest", "distribution_shift"): (0.6, 0.6, 0.6),
    }
    sources = [_src(0, spec), _src(1, flat), _src(2, flat)]
    b2 = ps.summarise(sources)["B2_rules_vs_best_learned"]
    assert list(b2) == ["silent_corruption", "distribution_shift"]
    # gaps: 0.9 - 0.2 = 0.7, 0.5 - 0.4 = 0.1 twice
    assert b2["silent_corruption"]["sources"] == 3
    assert b2["silent_corruption"]["median_gap"] == pytest.approx(0.1)
    assert b2["silent_corruption"]["share_ge_0.2"] == pytest.approx(1 / 3)
    # severity 0 only: 0.5 - 0.25 = 0.25, then 0.6 - 0.5 = 0.1 twice (float: just below)
    assert b2["distribution_shift"]["median_gap"] == pytest.approx(0.1)
    assert b2["distribution_shift"]["share_ge_0.2"] == pytest.approx(1 / 3)


def test_b2_gap_threshold_is_inclusive_and_sources_without_a_learned_detector_are_skipped():
    spec = {
        ("constraint_rules", "silent_corruption"): (0.25, 0.25, 0.25),
        ("isolation_forest", "silent_corruption"): (0.5, 0.5, 0.5),
    }
    no_learned = _src(1, detectors=("constraint_rules", "random"))
    b2 = ps.summarise([_src(0, spec), no_learned])["B2_rules_vs_best_learned"]
    assert b2["silent_corruption"]["sources"] == 1
    assert b2["silent_corruption"]["median_gap"] == pytest.approx(0.25)
    assert b2["silent_corruption"]["share_ge_0.2"] == 1.0
    exact = {
        ("constraint_rules", "silent_corruption"): (0.5, 0.5, 0.5),
        ("isolation_forest", "silent_corruption"): (0.75, 0.75, 0.75),
    }
    assert (
        ps.summarise([_src(0, exact)])["B2_rules_vs_best_learned"]["silent_corruption"][
            "share_ge_0.2"
        ]
        == 1.0
    )


def test_b5_compares_the_best_compact_variant_with_the_best_full_profile_variant():
    def spec(compact, full):
        return {
            (d, m): (v, v, v)
            for m in ("partial_load", "unit_change")
            for d, v in (("isolation_forest_compact", compact), ("isolation_forest", full))
        }

    sources = [
        _src(0, spec(0.9, 0.3)),  # gain 0.6
        _src(1, spec(0.5, 0.5)),  # gain 0.0 (not positive)
        _src(2, spec(0.2, 0.6)),  # gain -0.4
        _src(3, detectors=("constraint_rules", "isolation_forest")),  # no compact: skipped
    ]
    b5 = ps.summarise(sources)["B5_compact_minus_full_profile_best_learned"]
    assert list(b5) == [
        "partial_load",
        "duplicate_load",
        "null_spike",
        "schema_drop",
        "unit_change",
    ]
    assert b5["partial_load"]["sources"] == 3
    assert b5["partial_load"]["median_gain"] == pytest.approx(0.0)
    assert b5["partial_load"]["share_gain_positive"] == pytest.approx(1 / 3)
    assert b5["duplicate_load"]["median_gain"] == pytest.approx(0.0)


def test_b5_is_absent_for_a_mechanism_when_no_source_has_both_profiles():
    b5 = ps.summarise([_src(0, detectors=("constraint_rules", "isolation_forest"))])
    assert b5["B5_compact_minus_full_profile_best_learned"] == {}


def test_b3_names_the_family_with_the_best_median_recall_and_ties_go_to_the_first_family():
    sources = [_src(i) for i in range(3)]
    s = ps.summarise(sources)
    assert set(s["B3_best_family_by_mechanism"].values()) == {"rules"}
    assert s["B3_holds"] is False
    spec = {
        ("distribution_distance", "stale_batch"): (0.6, 0.6, 0.6),
        ("isolation_forest", "silent_corruption"): (0.7, 0.7, 0.7),
        ("isolation_forest_compact", "unit_change"): (0.7, 0.7, 0.7),
    }
    s = ps.summarise([_src(i, spec) for i in range(3)])
    winners = s["B3_best_family_by_mechanism"]
    assert list(winners) == list(pb.MECHANISMS)
    assert winners["stale_batch"] == "statistical"
    assert winners["silent_corruption"] == "learned"
    assert winners["unit_change"] == "learned"
    assert winners["partial_load"] == "rules"
    assert s["B3_holds"] is True


def test_b3_uses_the_median_over_sources_not_the_best_source():
    rules_wins_twice = {("constraint_rules", "stale_batch"): (0.5, 0.5, 0.5)}
    learned_once = {("isolation_forest", "stale_batch"): (0.9, 0.9, 0.9)}
    sources = [_src(0, rules_wins_twice), _src(1, rules_wins_twice), _src(2, learned_once)]
    assert ps.summarise(sources)["B3_best_family_by_mechanism"]["stale_batch"] == "rules"


def test_b3_ignores_a_family_that_no_detector_of_the_source_set_covers():
    s = ps.summarise([_src(0, detectors=("constraint_rules", "random"))])
    assert set(s["B3_best_family_by_mechanism"].values()) == {"rules"}


def test_b4_is_the_mean_recall_change_with_a_contaminated_reference_by_family():
    clean = {("constraint_rules", "stale_batch"): (0.5, 0.5, 0.5)}
    dirty_rules = {("constraint_rules", "stale_batch"): (0.1, 0.1, 0.1)}
    dirty_learned = {
        ("constraint_rules", "stale_batch"): (0.5, 0.5, 0.5),
        ("isolation_forest", "stale_batch"): (0.9, 0.9, 0.9),
    }
    sources = [_src(0, clean, dirty=dirty_rules), _src(1, clean, dirty=dirty_learned)]
    b4 = ps.summarise(sources)["B4_mean_recall_change_contaminated_minus_clean"]
    assert list(b4) == ["rules", "statistical", "learned"]
    # 16 (source, mechanism) pairs; only (rules, stale_batch) of source 0 changed, by -0.4
    assert b4["rules"] == pytest.approx(-0.4 / 16)
    assert b4["learned"] == pytest.approx(0.8 / 16)
    assert b4["statistical"] == pytest.approx(0.0)


def test_b4_is_nan_for_a_family_without_detectors():
    s = ps.summarise([_src(0, detectors=("constraint_rules", "random"))])
    b4 = s["B4_mean_recall_change_contaminated_minus_clean"]
    assert b4["rules"] == 0.0
    assert np.isnan(b4["statistical"]) and np.isnan(b4["learned"])


def test_fewer_than_fifteen_sources_make_the_pilot_descriptive():
    assert ps.summarise([_src(i) for i in range(14)])["descriptive_only"] is True
    assert ps.summarise([_src(i) for i in range(15)])["descriptive_only"] is False
    s = ps.summarise([_src(3), _src(1), _src(2)])
    assert s["sources"] == ["uci:1", "uci:2", "uci:3"]


def test_render_prints_the_report_line_by_line_for_a_descriptive_pilot():
    spec = {
        ("constraint_rules", "partial_load"): (0.2, 0.4, 0.6),
        ("isolation_forest", "silent_corruption"): (0.5, 0.5, 0.5),
        ("constraint_rules", "silent_corruption"): (0.25, 0.25, 0.25),
        ("distribution_distance", "stale_batch"): (0.6, 0.6, 0.6),
    }
    summary = ps.summarise([_src(0, spec), _src(1, spec)])
    lines = ps.render(summary).splitlines()
    assert lines[0] == "# Batch-level pipeline faults: pilot results"
    assert lines[2] == (
        "Sources: 2 (uci:0, uci:1). Descriptive only (fewer than 15 sources): no ranking claim."
    )
    assert lines[4] == (
        "Median recall at the label-free 5 % alert budget, over sources, averaged over "
        "severities (clean reference)."
    )
    assert lines[6] == (
        "| Detector | partial_load | duplicate_load | stale_batch | null_spike | schema_drop "
        "| unit_change | distribution_shift | silent_corruption | false alerts |"
    )
    assert lines[7] == "|---|" + "---:|" * 9
    assert lines[8] == (
        "| constraint_rules | 0.40 | 0.10 | 0.10 | 0.10 | 0.10 | 0.10 | 0.10 | 0.25 | 0.05 |"
    )
    assert lines[9].startswith("| distribution_distance | 0.10 | 0.10 | 0.60 |")
    assert lines[12] == "| random | " + " | ".join(["0.10"] * 8) + " | 0.05 |"
    assert lines[13:16] == ["", "Hypotheses (exploratory):", ""]
    assert lines[16] == (
        "- B1 share of sources with `constraint_rules` recall >= 0.9 (medium and high): "
        "partial_load 0%, duplicate_load 0%, stale_batch 0%, null_spike 0%, schema_drop 0%"
    )
    assert lines[17] == (
        "- B2 silent_corruption: best learned minus rules, median +0.25; "
        "gap >= 0.2 in 100% of 2 sources"
    )
    assert lines[18] == (
        "- B2 distribution_shift: best learned minus rules, median +0.00; "
        "gap >= 0.2 in 0% of 2 sources"
    )
    assert lines[19].startswith("- B3 best family per mechanism: {'partial_load': 'rules'")
    assert lines[19].endswith("differs between mechanisms: True")
    assert lines[20] == (
        "- B4 mean recall change with a contaminated reference: "
        "rules +0.000, statistical +0.000, learned +0.000"
    )
    assert lines[21].startswith("- B5 partial_load: best compact minus best full-profile")
    assert lines[21].endswith("median +0.00; positive in 0% of 2 sources")
    assert len(lines) == 26 and ps.render(summary).endswith("\n")


def test_render_leaves_the_sentence_open_once_the_pilot_has_fifteen_sources():
    summary = ps.summarise([_src(i) for i in range(15)])
    line = ps.render(summary).splitlines()[2]
    assert line.startswith("Sources: 15 (uci:0, uci:1,")
    assert "Descriptive" not in line


def test_main_summarises_a_results_directory_and_writes_both_files(tmp_path):
    for i in range(2):
        (tmp_path / f"uci_{i}.json").write_text(json.dumps(_src(i)))
    assert ps.main(["--results", str(tmp_path)]) == 0
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["sources"] == ["uci:0", "uci:1"]
    raw = (tmp_path / "summary.json").read_text()
    assert raw.startswith('{\n "B1_share') and raw.endswith("}\n")
    assert (tmp_path / "summary.md").read_text() == ps.render(ps.summarise(ps.load(tmp_path)))


def test_main_merges_the_compact_results_when_given_and_uses_the_pilot_directory_by_default(
    tmp_path, monkeypatch
):
    main, extra = tmp_path / "main", tmp_path / "extra"
    main.mkdir()
    extra.mkdir()
    (main / "uci_0.json").write_text(json.dumps(_src(0)))
    (extra / "uci_0.json").write_text(json.dumps(_extra(0, ("ecod_compact",), 0.9)))
    assert ps.main(["--results", str(main), "--compact-results", str(extra)]) == 0
    merged = json.loads((main / "summary.json").read_text())
    assert "ecod_compact" in merged["median_recall_at_budget"]

    seen = {}

    def fake_load(directory, extra=None):
        seen.update(directory=directory, extra=extra)
        raise RuntimeError("stop")

    monkeypatch.setattr(ps, "load", fake_load)
    with pytest.raises(RuntimeError):
        ps.main([])
    assert seen["directory"] == ps.ROOT / "verification/evidence/pipeline_batch/pilot"
    assert seen["extra"] is None
