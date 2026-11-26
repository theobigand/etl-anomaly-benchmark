"""Summary of the naturally labelled chronological study: lift, group units, hypotheses."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import natural_temporal_summary as ns  # noqa: E402

METHODS = ["zscore", "iqr", "isolation_forest", "lof", "knn", "autoencoder", "vae"]


def _policy(f1, share):
    return {
        "f1": f1,
        "share_error": share,
        "flagged_share": 0.1,
        "precision": 0.5,
        "recall": 0.5,
        "fpr": 0.1,
    }


def _record(name, group, chrono_bias, rng, test_prevalence=0.2):
    base = {m: rng.uniform(0.2, 0.8) for m in METHODS}
    return {
        "id": name,
        "group": group,
        "partitions": {
            "train": {"rows": 700, "positives": 70, "prevalence": 0.1},
            "validation": {"rows": 150, "positives": 15, "prevalence": 0.1},
            "test": {"rows": 150, "positives": 30, "prevalence": test_prevalence},
        },
        "chronological": {
            m: {
                "pr_auc": v + chrono_bias,
                "policies": {
                    "P0": _policy(0.3, 0.9),
                    "P1": _policy(0.3, 0.6),
                    "P2": _policy(0.4, 0.3),
                },
            }
            for m, v in base.items()
        },
        "stratified": {
            m: {"pr_auc": v, "pr_auc_matched": v + chrono_bias / 2} for m, v in base.items()
        },
    }


def test_lift_removes_the_prevalence_baseline_of_each_arm():
    rng = np.random.default_rng(0)
    record = _record("s", "g", -0.1, rng, test_prevalence=0.2)
    out = ns.lifts(record)["zscore"]
    chrono, strat = (
        record["chronological"]["zscore"]["pr_auc"],
        record["stratified"]["zscore"]["pr_auc"],
    )
    assert out["chronological_lift"] == pytest.approx((chrono - 0.2) / 0.8)
    assert out["stratified_lift"] == pytest.approx((strat - 0.115) / 0.885)  # 115 of 1000 rows


def test_detectors_belong_to_one_of_three_families():
    assert [ns.family(m) for m in ("iqr", "lof", "vae")] == ["rule", "classical", "neural"]


def test_units_are_source_groups_and_a_consistent_loss_is_found():
    rng = np.random.default_rng(1)
    groups = ["a", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k"]
    evaluated = [_record(f"s{i}", g, -0.15, rng) for i, g in enumerate(groups)]
    summary = ns.summarise(evaluated, [], draws=200)
    assert summary["independent_sources"] == 11 and summary["series"]["evaluated"] == 12
    n1 = summary["N1"]
    assert n1["chronological_lower_share"] == 1.0 and n1["supported_by_share"] is True
    assert len(n1["detectors_with_interval_below_zero"]) == len(METHODS)
    assert summary["N2"]["median_spearman"] > 0.99 and summary["N2"]["supported"] is True
    assert summary["N4"]["friedman"]["units"] == 11
    assert {tuple(sorted((r["a"], r["b"]))) for r in summary["N4"]["families"]} == {
        ("classical", "neural"),
        ("classical", "rule"),
        ("neural", "rule"),
    }


def test_no_loss_is_not_reported_as_one():
    rng = np.random.default_rng(2)
    evaluated = [_record(f"s{i}", f"g{i}", 0.05, rng) for i in range(10)]
    n1 = ns.summarise(evaluated, [], draws=200)["N1"]
    assert n1["chronological_lower_share"] == 0.0 and n1["supported_by_share"] is False


def test_excluded_series_are_listed_with_their_reason_and_never_evaluated(tmp_path):
    rng = np.random.default_rng(3)
    (tmp_path / "a.json").write_text(json.dumps(_record("a", "g", 0.0, rng)))
    (tmp_path / "b.json").write_text(
        json.dumps({"id": "b", "group": "h", "excluded": "0 anomalies"})
    )
    evaluated, excluded = ns.load(tmp_path)
    assert [r["id"] for r in evaluated] == ["a"] and [r["id"] for r in excluded] == ["b"]
    summary = ns.summarise(evaluated * 1 + [_record("c", "i", 0.0, rng)] * 9, excluded, draws=100)
    assert summary["excluded"] == [{"id": "b", "group": "h", "reason": "0 anomalies"}]
    assert "0 anomalies" in ns.render(summary)


# ---------------------------------------------------------------------------------------------
# Deterministic fixture: four series in three source groups, three detectors of three families.
# ---------------------------------------------------------------------------------------------
DETECTORS = ("zscore", "lof", "autoencoder")


def _fixed(sid, group, chrono, strat, matched, policies=None, prevalence=0.2):
    default = {"P0": (0.3, 0.9), "P1": (0.3, 0.6), "P2": (0.4, 0.3)}
    result = {
        "id": sid,
        "group": group,
        "partitions": {
            "train": {"rows": 700, "positives": 70, "prevalence": 0.1},
            "validation": {"rows": 150, "positives": 15, "prevalence": 0.1},
            "test": {"rows": 150, "positives": 30, "prevalence": prevalence},
        },
        "chronological": {},
        "stratified": {},
    }
    for m, c, s, mt in zip(DETECTORS, chrono, strat, matched, strict=True):
        pol = {**default, **((policies or {}).get(m) or {})}
        result["chronological"][m] = {
            "pr_auc": c,
            "policies": {p: _policy(f1, share) for p, (f1, share) in pol.items()},
        }
        result["stratified"][m] = {"pr_auc": s, "pr_auc_matched": mt}
    return result


def _world():
    return [
        _fixed("s0", "gA", (0.30, 0.50, 0.70), (0.40, 0.45, 0.80), (0.33, 0.50, 0.73)),
        _fixed("s1", "gA", (0.20, 0.60, 0.50), (0.30, 0.55, 0.60), (0.25, 0.60, 0.50)),
        _fixed(
            "s2",
            "gB",
            (0.50, 0.40, 0.60),
            (0.45, 0.35, 0.55),
            (0.45, 0.35, 0.55),
            policies={"autoencoder": {"P0": (0.5, 0.9), "P2": (0.2, 0.3)}},
        ),
        _fixed(
            "s3",
            "gC",
            (0.10, 0.20, 0.30),
            (0.20, 0.10, 0.35),
            (0.14, 0.16, 0.30),
            policies={m: {"P2": (0.4, 0.7)} for m in DETECTORS},
        ),
    ]


def test_the_constants_name_the_rule_detectors_the_neural_family_and_the_support_share():
    assert ns.RULES == ("zscore", "iqr", "great_expectations")
    assert ns.FAMILIES["rule"] == ns.RULES
    assert ns.FAMILIES["neural"] == tuple(ns.DEEP_NAMES) and len(ns.FAMILIES["neural"]) > 0
    assert ns.SUPPORT_SHARE == 2 / 3
    for name in ns.RULES:
        assert ns.family(name) == "rule"
    for name in ns.DEEP_NAMES:
        assert ns.family(name) == "neural"
    assert ns.family("great_expectations") == "rule" and ns.family("knn") == "classical"


def test_load_separates_excluded_series_and_reads_the_files_in_sorted_order(tmp_path):
    (tmp_path / "b.json").write_text(json.dumps({"id": "b", "group": "g", "excluded": "x"}))
    (tmp_path / "c.json").write_text(json.dumps({"id": "c", "group": "g"}))
    (tmp_path / "a.json").write_text(json.dumps({"id": "a", "group": "g"}))
    (tmp_path / "notes.txt").write_text("ignored")
    evaluated, excluded = ns.load(tmp_path)
    assert [r["id"] for r in evaluated] == ["a", "c"]
    assert [r["id"] for r in excluded] == ["b"]


def test_the_lifts_record_both_pr_auc_values_and_both_lifts_per_detector():
    out = ns.lifts(_world()[0])
    assert set(out) == set(DETECTORS)
    z = out["zscore"]
    assert z["chronological"] == 0.30 and z["stratified"] == 0.40 and z["matched"] == 0.33
    assert z["chronological_lift"] == pytest.approx((0.30 - 0.2) / 0.8)
    assert z["stratified_lift"] == pytest.approx((0.40 - 0.115) / 0.885)


def test_table_by_group_averages_the_series_of_a_group_and_marks_missing_detectors():
    world = _world()
    del world[1]["chronological"]["lof"]
    groups, table = ns.table_by_group(world, lambda r, m: r["chronological"][m]["pr_auc"])
    assert groups == ["gA", "gB", "gC"]
    assert list(table) == ["autoencoder", "lof", "zscore"]
    assert table["zscore"] == pytest.approx([0.25, 0.5, 0.1])
    assert table["lof"] == pytest.approx([0.5, 0.4, 0.2])  # gA: only its first series has lof
    del world[3]["chronological"]["lof"]
    _, table = ns.table_by_group(world, lambda r, m: r["chronological"][m]["pr_auc"])
    assert table["lof"][:2] == pytest.approx([0.5, 0.4]) and np.isnan(table["lof"][2])


def test_n1_counts_the_pairs_where_the_chronological_arm_is_lower_per_series_and_group():
    s = ns.summarise(_world(), [], draws=200)
    assert s["series"] == {"evaluated": 4, "excluded": 0}
    assert s["source_groups"] == ["gA", "gB", "gC"] and s["independent_sources"] == 3
    n1 = s["N1"]
    assert n1["pairs"] == 12 and n1["chronological_lower_share"] == 0.5
    assert n1["supported_by_share"] is False
    z = n1["by_detector"]["zscore"]
    # group means: chronological 0.25, 0.5, 0.1; stratified 0.35, 0.45, 0.2
    assert z["groups_lower"] == 2 and z["units"] == 3
    assert z["median_difference"] == pytest.approx(-0.1)
    assert n1["by_detector"]["lof"]["groups_lower"] == 0
    assert n1["by_detector"]["autoencoder"]["groups_lower"] == 2
    assert n1["detectors_with_interval_below_zero"] == []
    assert list(n1["by_detector"]) == ["autoencoder", "lof", "zscore"]


def test_the_share_rule_is_met_at_two_thirds_and_not_below():
    def series(i, lower):
        chrono = (0.2, 0.2, 0.2) if lower else (0.4, 0.4, 0.4)
        return _fixed(f"s{i}", f"g{i}", chrono, (0.3, 0.3, 0.3), (0.3, 0.3, 0.3))

    met = ns.summarise([series(0, True), series(1, True), series(2, False)], [], draws=100)
    assert met["N1"]["chronological_lower_share"] == pytest.approx(2 / 3)
    assert met["N1"]["supported_by_share"] is True
    short = ns.summarise([series(0, True), series(1, False), series(2, False)], [], draws=100)
    assert short["N1"]["supported_by_share"] is False


def test_n1_on_the_lift_uses_each_arms_own_prevalence_baseline():
    s = ns.summarise(_world(), [], draws=200)
    lift = s["N1_lift"]
    # chronological lift (c - 0.2) / 0.8 against stratified lift (s - 0.115) / 0.885
    expected = 0
    for r in _world():
        for m in DETECTORS:
            c, st = r["chronological"][m]["pr_auc"], r["stratified"][m]["pr_auc"]
            expected += (c - 0.2) / 0.8 < (st - 0.115) / 0.885
    assert expected == 9
    assert lift["chronological_lower_share"] == pytest.approx(9 / 12)
    assert set(lift["by_detector"]) == set(DETECTORS)
    assert lift["by_detector"]["zscore"]["units"] == 3
    # zscore: group lift differences -0.203, -0.004 and -0.221, all negative
    assert lift["detectors_with_interval_below_zero"] == ["zscore"]


def test_n2_reports_the_spearman_agreement_between_the_arms_series_by_series():
    n2 = ns.summarise(_world(), [], draws=100)["N2"]
    assert n2["by_series"] == pytest.approx({"s0": 1.0, "s1": 0.5, "s2": 1.0, "s3": 0.5})
    assert list(n2["by_series"]) == ["s0", "s1", "s2", "s3"]
    assert n2["median_spearman"] == pytest.approx(0.75)
    assert n2["supported"] is False


def test_n3_and_the_decision_policies_come_from_the_temporal_hypotheses():
    s = ns.summarise(_world(), [], draws=100)
    # matched gap at most half of the stratified gap: s0, s1 and s3 yes; s2 no
    assert s["N3"] == {"series_where_matching_closes_half": 3, "series": 4}
    # P2 < P1 < P0 share error: all but s3 (P2 0.7 above P1 0.6)
    assert s["decision_policies"]["H2"] == {"s0": True, "s1": True, "s2": True, "s3": False}
    # P2 f1 at least P0 f1: 12 pairs, except the autoencoder of s2 (0.2 against 0.5)
    assert s["decision_policies"]["H3"] == {"p2_at_least_p0": 11, "pairs": 12}


def test_n4_ranks_the_detectors_over_source_groups_and_compares_the_families():
    n4 = ns.summarise(_world(), [], draws=100)["N4"]
    assert n4["detectors"] == ["autoencoder", "lof", "zscore"]
    assert n4["mean_rank"] == pytest.approx({"autoencoder": 1.0, "lof": 7 / 3, "zscore": 8 / 3})
    assert set(n4["rank_interval"]) == set(DETECTORS)
    assert all(lo <= hi for lo, hi in n4["rank_interval"].values())
    assert n4["friedman"]["units"] == 3 and n4["friedman"]["detectors"] == 3
    rows = {(r["a"], r["b"]): r for r in n4["families"]}
    assert list(rows) == [("classical", "neural"), ("classical", "rule"), ("neural", "rule")]
    # group means: neural 0.6, 0.6, 0.3; classical 0.55, 0.4, 0.2; rule 0.25, 0.5, 0.1
    assert rows[("classical", "neural")]["median_difference"] == pytest.approx(-0.1)
    assert rows[("neural", "rule")]["median_difference"] == pytest.approx(0.2)


def test_excluded_series_are_counted_and_listed_in_the_summary():
    excluded = [{"id": "x", "group": "gX", "excluded": "0 anomalies"}]
    s = ns.summarise(_world(), excluded, draws=100)
    assert s["series"] == {"evaluated": 4, "excluded": 1}
    assert s["excluded"] == [{"id": "x", "group": "gX", "reason": "0 anomalies"}]
    assert s["per_series"]["s0"]["zscore"]["matched"] == 0.33


def test_render_prints_the_study_report_line_by_line():
    excluded = [{"id": "x", "group": "gX", "excluded": "0 anomalies"}]
    s = ns.summarise(_world(), excluded, draws=100)
    lines = ns.render(s).splitlines()
    assert lines[0] == "# Naturally labelled chronological study: results"
    assert lines[2] == ("Series evaluated: 4 of 5; independent source groups: 3 (gA, gB, gC).")
    assert lines[4] == (
        "- N1: chronological PR-AUC below stratified for 50.0% of 12 (series, detector) pairs; "
        "share rule not met; detectors whose group-level median difference interval is below "
        "zero: 0 of 3."
    )
    assert lines[5] == (
        "- N1 on the lift over prevalence (exploratory, prevalence-adjusted): chronological "
        "lower for 75.0% of pairs; detectors with an interval below zero: 1 of 3."
    )
    assert lines[6] == "- N2: median Spearman between arms 0.75 (not supported)."
    assert lines[7] == "- N3: matching closes at least half of the gap in 3 of 4 series."
    assert lines[8].startswith("- N4: Friedman over 3 source groups, p = ")
    assert lines[10] == (
        "| Detector | Mean rank | 95 % interval | Median chronological - stratified "
        "| 95 % interval |"
    )
    assert lines[11] == "|---|---|---|---|---|"
    assert [ln.split("|")[1].strip() for ln in lines[12:15]] == ["autoencoder", "lof", "zscore"]
    assert lines[12].startswith("| autoencoder | 1.00 | ")
    assert lines[15] == ""
    assert lines[16] == (
        "| Families | Median difference | 95 % interval | p (Holm) | Probability of superiority |"
    )
    assert lines[17] == "|---|---|---|---|---|"
    assert lines[18].startswith("| classical - neural | -0.100 | ")
    assert lines[21:24] == ["", "Not evaluated:", ""]
    assert lines[24] == "- x (gX): 0 anomalies"
    assert len(lines) == 25


def test_render_marks_a_met_share_rule_and_a_supported_agreement():
    rng = np.random.default_rng(1)
    groups = ["a", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k"]
    evaluated = [_record(f"s{i}", g, -0.15, rng) for i, g in enumerate(groups)]
    text = ns.render(ns.summarise(evaluated, [], draws=100))
    assert "share rule met;" in text and "(supported)." in text
    assert "detectors whose group-level median difference interval is below zero: 7 of 7." in text


def test_main_writes_the_json_and_markdown_summaries_next_to_each_other(tmp_path):
    results, output = tmp_path / "results", tmp_path / "out"
    results.mkdir()
    output.mkdir()
    for r in _world():
        (results / f"{r['id']}.json").write_text(json.dumps(r))
    (results / "x.json").write_text(json.dumps({"id": "x", "group": "gX", "excluded": "none"}))
    assert ns.main(["--results", str(results), "--output", str(output)]) == 0
    raw = (output / "summary.json").read_text()
    assert raw.startswith('{\n "N1"') and raw.endswith("}\n")
    assert json.loads(raw)["series"] == {"evaluated": 4, "excluded": 1}
    expected = ns.render(ns.summarise(*ns.load(results)))
    assert (output / "summary.md").read_text() == expected


def test_main_defaults_point_at_the_natural_temporal_evidence(monkeypatch):
    seen = {}

    def fake_load(directory):
        seen["directory"] = directory
        raise RuntimeError("stop")

    monkeypatch.setattr(ns, "load", fake_load)
    with pytest.raises(RuntimeError):
        ns.main([])
    assert seen["directory"] == ns.ROOT / "verification/evidence/natural_temporal/results"
    from argparse import ArgumentParser

    parsed = {}
    monkeypatch.setattr(
        ArgumentParser,
        "parse_args",
        lambda self, argv=None: (
            parsed.update(defaults={a.dest: a.default for a in self._actions})
            or (_ for _ in ()).throw(RuntimeError("stop"))
        ),
    )
    with pytest.raises(RuntimeError):
        ns.main([])
    assert parsed["defaults"]["output"] == ns.ROOT / "verification/evidence/natural_temporal"


def test_an_interval_counts_as_below_zero_only_when_its_upper_end_is_negative():
    assert ns.below_zero({"ci_high": -0.01}) is True
    assert ns.below_zero({"ci_high": 0.0}) is False
    assert ns.below_zero({"ci_high": 0.01}) is False
    assert ns.below_zero({"units": 0}) is False  # no interval, no claim


def _tied_world():
    """Chronological and stratified scores are identical and the two baselines are the same."""
    equal = (0.3, 0.5, 0.7)
    return [_fixed(f"s{i}", f"g{i}", equal, equal, equal, prevalence=0.115) for i in range(4)]


def test_a_tie_is_not_a_loss_for_the_pair_the_group_or_the_interval():
    s = ns.summarise(_tied_world(), [], draws=100)
    assert s["N1"]["chronological_lower_share"] == 0.0
    assert s["N1_lift"]["chronological_lower_share"] == 0.0
    assert all(v["groups_lower"] == 0 for v in s["N1"]["by_detector"].values())
    assert s["N1"]["detectors_with_interval_below_zero"] == []
    assert s["N1_lift"]["detectors_with_interval_below_zero"] == []
    assert all(v["ci_high"] == 0.0 for v in s["N1"]["by_detector"].values())


def test_detectors_are_listed_in_the_order_of_their_mean_rank_not_alphabetically():
    reverse = [
        _fixed(
            r["id"],
            r["group"],
            tuple(reversed([r["chronological"][m]["pr_auc"] for m in DETECTORS])),
            tuple(reversed([r["stratified"][m]["pr_auc"] for m in DETECTORS])),
            tuple(reversed([r["stratified"][m]["pr_auc_matched"] for m in DETECTORS])),
        )
        for r in _world()
    ]
    s = ns.summarise(reverse, [], draws=50)
    assert s["N4"]["mean_rank"]["zscore"] == 1.0
    lines = ns.render(s).splitlines()
    assert [ln.split("|")[1].strip() for ln in lines[12:15]] == ["zscore", "lof", "autoencoder"]


def test_the_report_keeps_its_blank_separator_lines():
    excluded = [{"id": "x", "group": "gX", "excluded": "0 anomalies"}]
    lines = ns.render(ns.summarise(_world(), excluded, draws=50)).splitlines()
    assert [i for i, line in enumerate(lines) if line == ""] == [1, 3, 9, 15, 21, 23]
    assert not any("XXXX" in line for line in lines)


def test_the_parser_defaults_to_the_natural_temporal_evidence_directories():
    parser = ns.build_parser()
    assert parser.description == ns.__doc__
    args = parser.parse_args([])
    assert args.results == ns.ROOT / "verification/evidence/natural_temporal/results"
    assert args.output == ns.ROOT / "verification/evidence/natural_temporal"
    assert isinstance(args.results, Path) and isinstance(args.output, Path)
    custom = parser.parse_args(["--results", "r", "--output", "o"])
    assert custom.results == Path("r") and custom.output == Path("o")
