"""Source-grouped rankings, paired tests and label-rule agreement of the validity study."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paired_inference as pinf  # noqa: E402
import validity_summary as vs  # noqa: E402

from etl_benchmark.registry import DEEP_NAMES  # noqa: E402

DRAWS = 100
NEURAL = sorted(DEEP_NAMES)[0]


def _run(directory, name, problem, methods, seeds, rule=None, **extra):
    """One archived run: ``methods`` maps a detector to its per-seed PR-AUC list."""
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "problem": problem,
        "seeds": list(seeds),
        "metrics": {m: [{"pr_auc": v} for v in values] for m, values in methods.items()},
        **extra,
    }
    if rule is not None:
        record["rule"] = rule
    (directory / f"{name}.json").write_text(json.dumps(record))


def test_families_separate_rules_neural_and_classical_detectors():
    assert vs.family("zscore") == "rule"
    assert vs.family("iqr") == "rule"
    assert vs.family("great_expectations") == "rule"
    assert vs.family(NEURAL) == "neural"
    assert vs.family("isolation_forest") == "classical"
    assert vs.FAMILY == {"zscore": "rule", "iqr": "rule", "great_expectations": "rule"}
    assert vs.RULE_SEEDS == 3


def test_load_seeds_reads_pr_auc_per_seed_and_skips_failed_runs_and_short_methods(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _run(a, "p1", "uci:1", {"m": [0.1, 0.2], "short": [0.5]}, [0, 1])
    _run(a, "p2", "uci:2", {"m": [0.3, 0.4]}, [0, 1], failed="boom")
    _run(a, "p3", "uci:3", {"m": [0.3, 0.4]}, [0, 1], not_applicable="no labels")
    _run(b, "p1", "uci:1", {"n": [0.6, 0.7]}, [0, 1])
    got = vs.load_seeds((a, b))
    assert got == {"uci:1": {"m": [0.1, 0.2], "n": [0.6, 0.7]}}


def test_load_seeds_lets_a_later_directory_replace_the_same_detector(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _run(a, "p", "uci:1", {"m": [0.1, 0.2]}, [0, 1])
    _run(b, "p", "uci:1", {"m": [0.8, 0.9]}, [0, 1])
    assert vs.load_seeds((a, b)) == {"uci:1": {"m": [0.8, 0.9]}}
    assert vs.load_seeds((tmp_path / "absent",)) == {}


def test_merge_appends_the_new_seeds_to_the_old_ones_and_ignores_new_only_problems():
    old = {"p": {"m": [1.0, 2.0], "n": [3.0]}, "q": {"m": [4.0]}}
    new = {"p": {"m": [5.0]}, "z": {"m": [9.0]}}
    assert vs.merge(old, new) == {"p": {"m": [1.0, 2.0, 5.0], "n": [3.0]}, "q": {"m": [4.0]}}


def test_source_table_averages_the_problems_of_a_source_and_marks_absent_detectors():
    # adbench:breastw is the twin of uci:15, so both belong to the same source group
    ap = {
        "adbench:breastw": {"a": 0.2},
        "uci:15": {"a": 0.4, "b": 0.6},
        "uci:2": {"a": 0.5},
    }
    groups, table = vs.source_table(ap)
    assert groups == ["uci:15", "uci:2"]
    assert list(table) == ["a", "b"]
    assert table["a"] == pytest.approx([0.3, 0.5])
    assert table["b"][0] == pytest.approx(0.6) and np.isnan(table["b"][1])


def test_ranking_orders_detectors_alphabetically_and_ranks_one_as_best():
    table = {
        "b": np.array([0.9, 0.8, 0.7, 0.9, 0.6]),
        "a": np.array([0.5, 0.9, 0.2, 0.4, 0.1]),
        "c": np.array([0.1, 0.1, 0.1, 0.1, 0.9]),
    }
    r = vs.ranking(table, DRAWS)
    assert r["detectors"] == ["a", "b", "c"]
    assert r["units"] == 5
    assert r["mean_rank"] == pytest.approx({"a": 2.0, "b": 1.4, "c": 2.6})
    names, matrix = pinf.complete_matrix(table)
    expected = pinf.rank_intervals(matrix, DRAWS)
    assert r["rank_interval"] == {
        n: [float(lo), float(hi)] for n, (lo, hi) in zip(names, expected, strict=True)
    }
    assert r["friedman"] == pinf.friedman(matrix)


def test_tau_uses_the_common_detectors_only():
    a = {"x": 1.0, "y": 2.0, "z": 3.0, "only_a": 9.0}
    assert vs.tau(a, {"x": 1.0, "y": 2.0, "z": 3.0, "only_b": 0.0}) == pytest.approx(1.0)
    assert vs.tau(a, {"x": 3.0, "y": 2.0, "z": 1.0}) == pytest.approx(-1.0)


def _seeded():
    """Seven problems (six independent sources) with ten seeds for four detectors."""
    per = {
        "zscore": [0.9] * 5 + [0.2] * 5,
        "isolation_forest": [0.7] * 10,
        "knn": [0.5] * 10,
        NEURAL: [0.3] * 10,
        "lof": [0.6] * 7,
    }
    problems = ["uci:15", "adbench:breastw", "uci:2", "uci:3", "uci:4", "uci:5", "uci:6"]
    out = {}
    for i, p in enumerate(problems):
        out[p] = {m: [v + 0.01 * i for v in vals] for m, vals in per.items()}
    return out


def test_part_a_ranks_ten_seeds_against_five_and_counts_independent_sources():
    a = vs.part_a(_seeded(), DRAWS)
    assert a["problems"] == 7
    assert a["independent_sources"] == 6
    ten, five = a["ten_seeds"], a["five_seeds"]
    # ten seeds: zscore averages 0.55 and falls behind the steady forest; lof has only 7 seeds
    assert ten["detectors"] == sorted(["zscore", "isolation_forest", "knn", NEURAL])
    assert ten["mean_rank"]["isolation_forest"] == 1.0 and ten["mean_rank"]["zscore"] == 2.0
    assert ten["units"] == 6
    # five seeds: zscore averages 0.9 over its first five seeds and wins; lof (7 seeds) joins
    assert "lof" in five["detectors"]
    assert five["mean_rank"]["zscore"] == 1.0
    assert a["V4_tau_5_vs_10"] == pytest.approx(vs.tau(ten["mean_rank"], five["mean_rank"]))
    assert a["V3"]["best"] == "isolation_forest" and a["V3"]["second"] == "zscore"
    assert {a["V3"]["a"], a["V3"]["b"]} == {"isolation_forest", "zscore"}
    assert a["pairs_total"] == 6 == len(a["pairwise"])
    assert a["pairs_significant_holm_05"] == sum(r["p_holm"] < 0.05 for r in a["pairwise"])
    assert a["problem_level_ranking"]["units"] == 7
    assert [r["a"] for r in a["families"]] == ["classical", "classical", "neural"]
    assert [r["b"] for r in a["families"]] == ["neural", "rule", "rule"]


def test_part_a_family_means_pool_the_detectors_of_each_family():
    a = vs.part_a(_seeded(), DRAWS)
    by_pair = {(r["a"], r["b"]): r for r in a["families"]}
    # classical = mean(forest, knn) = 0.6 plus a source offset; rule = zscore mean 0.55
    assert by_pair[("classical", "rule")]["median_difference"] == pytest.approx(0.05)
    # classical 0.6 against neural 0.3
    assert by_pair[("classical", "neural")]["median_difference"] == pytest.approx(0.3)
    assert by_pair[("neural", "rule")]["median_difference"] == pytest.approx(-0.25)


def _rules_world():
    """Five UCI sources, three detectors, five seeds; the first three define the R0 ranking."""
    seeded, runs = {}, {}
    for i in range(1, 6):
        p = f"uci:{i}"
        seeded[p] = {"a": [0.9, 0.9, 0.9, 0.0, 0.0], "b": [0.6] * 5, "c": [0.3] * 5}
        runs[p] = {"a": [0.6, 0.6, 0.6], "b": [0.9, 0.9, 0.9], "c": [0.3, 0.3, 0.3]}
    seeded["adbench:foo"] = {"a": [0.9] * 5, "b": [0.6] * 5, "c": [0.3] * 5}
    runs["adbench:foo"] = {"a": [0.1] * 3, "b": [0.2] * 3, "c": [0.3] * 3}
    runs["uci:9"] = {"a": [0.1] * 3, "b": [0.2] * 3, "c": [0.3] * 3}
    return seeded, runs


def test_part_b_compares_the_first_seeds_ranking_with_each_rule_on_shared_uci_problems():
    seeded, runs = _rules_world()
    b = vs.part_b(seeded, {"R1": runs}, DRAWS)
    r = b["R1"]
    assert r["problems"] == 5 and r["sources"] == 5
    assert r["R0_leader"] == "a" and r["R0_leader_rank_under_rule"] == 2
    assert r["leader_under_rule"] == "b"
    assert r["kendall_tau_vs_R0"] == pytest.approx(1 / 3)
    assert r["mean_rank_R0"] == pytest.approx({"a": 1.0, "b": 2.0, "c": 3.0})
    assert r["mean_rank_rule"] == pytest.approx({"a": 2.0, "b": 1.0, "c": 3.0})


def test_part_b_keeps_every_rule_separate():
    seeded, runs = _rules_world()
    same = {p: {m: v[:3] for m, v in d.items()} for p, d in seeded.items()}
    b = vs.part_b(seeded, {"R1": runs, "R2": same}, DRAWS)
    assert list(b) == ["R1", "R2"]
    assert b["R2"]["kendall_tau_vs_R0"] == pytest.approx(1.0)
    assert b["R2"]["R0_leader_rank_under_rule"] == 1


def _summary():
    seeded, runs = _rules_world()
    seeded = {**_seeded(), **{p: d for p, d in seeded.items() if p.startswith("uci:")}}
    summary = {"A": vs.part_a(_seeded(), DRAWS), "B": vs.part_b(seeded, {"R1": runs}, DRAWS)}
    return summary


def test_render_reports_the_headline_the_ranking_table_the_families_and_the_rules():
    summary = _summary()
    text = vs.render(summary)
    a = summary["A"]
    lines = text.splitlines()
    assert lines[0] == "# Statistical validity of the labelled-pool rankings"
    fr = a["ten_seeds"]["friedman"]
    assert lines[2] == (
        f"Problems 7; independent source groups 6 (units of inference). "
        f"Friedman over {fr['units']} sources and {fr['detectors']} detectors: p = {fr['p']:.3g}. "
        f"Pairs significant after Holm: {a['pairs_significant_holm_05']} of 6. "
        f"Five-seed versus ten-seed ranking, Kendall tau {a['V4_tau_5_vs_10']:.2f}."
    )
    v3 = a["V3"]
    assert lines[4] == (
        f"V3: best isolation_forest against second zscore: median AP difference "
        f"{v3['median_difference']:+.3f} [{v3['ci_low']:+.3f}, {v3['ci_high']:+.3f}], "
        f"p (Holm) {v3['p_holm']:.3f}."
    )
    assert lines[6] == "| Detector | Mean rank (10 seeds) | 95 % interval | Mean rank (5 seeds) |"
    assert lines[7] == "|---|---:|---|---:|"
    assert lines[8].startswith("| isolation_forest | 1.00 | ")
    assert lines[8].endswith(f" | {a['five_seeds']['mean_rank']['isolation_forest']:.2f} |")
    ranks = [ln.split("|")[1].strip() for ln in lines[8:12]]
    assert ranks == ["isolation_forest", "zscore", "knn", NEURAL]
    assert lines[12] == ""
    assert lines[13] == "| Families | Median difference | 95 % interval | p (Holm) |"
    assert lines[14] == "|---|---:|---|---:|"
    assert lines[15].startswith("| classical - neural | +0.300 | ")
    assert lines[18] == ""
    assert lines[19] == "## Label rules"
    assert lines[21].startswith("| Rule | Problems | Sources | Kendall tau vs R0 |")
    assert lines[22] == "|---|---:|---:|---:|---|---:|---|"
    assert lines[23] == "| R1 | 5 | 5 | 0.33 | a | 2 | b |"
    assert text.endswith("|\n") and len(lines) == 24


def test_render_prints_nan_for_a_detector_missing_from_the_five_seed_ranking():
    summary = _summary()
    del summary["A"]["five_seeds"]["mean_rank"][NEURAL]
    assert any(
        line.startswith(f"| {NEURAL} |") and line.endswith("| nan |")
        for line in vs.render(summary).splitlines()
    )


def test_main_merges_archive_and_new_seeds_loads_the_rules_and_writes_both_summaries(
    tmp_path, monkeypatch
):
    old, new = tmp_path / "old", tmp_path / "new"
    rules_c, rules_d = tmp_path / "rc", tmp_path / "rd"
    evidence = tmp_path / "evidence"
    (evidence / "validity").mkdir(parents=True)
    for i in range(1, 7):
        p = f"uci:{i}"
        _run(
            old,
            f"p{i}",
            p,
            {"zscore": [0.9] * 5, "isolation_forest": [0.6] * 5, NEURAL: [0.3] * 5},
            range(5),
        )
        _run(
            new,
            f"p{i}",
            p,
            {"zscore": [0.9] * 5, "isolation_forest": [0.6] * 5, NEURAL: [0.3] * 5},
            range(5, 10),
        )
        _run(
            rules_c,
            f"r{i}",
            p,
            {"zscore": [0.6] * 3, "isolation_forest": [0.9] * 3, NEURAL: [0.3] * 3},
            range(3),
            "R1",
        )
    _run(rules_d, "bad", "uci:1", {"zscore": [0.0] * 3}, range(3), "R1", failed="x")
    _run(rules_d, "na", "uci:1", {"zscore": [0.0] * 3}, range(3), "R1", not_applicable="x")
    _run(rules_d, "short", "uci:1", {"lof": [0.0]}, range(3), "R1")
    monkeypatch.setattr(vs, "ARCHIVE", (old,))
    monkeypatch.setattr(vs, "NEW", (new,))
    monkeypatch.setattr(vs, "RULE_DIRS", (rules_c, rules_d))
    monkeypatch.setattr(vs, "EVIDENCE", evidence)
    monkeypatch.setattr(vs.pinf, "DRAWS", DRAWS)
    assert vs.main() == 0
    out = evidence / "validity"
    summary = json.loads((out / "summary.json").read_text())
    assert summary["A"]["problems"] == 6
    assert summary["A"]["ten_seeds"]["units"] == 6
    assert list(summary["B"]) == ["R1"]
    assert summary["B"]["R1"]["problems"] == 6
    assert summary["B"]["R1"]["R0_leader"] == "zscore"
    assert "lof" not in summary["B"]["R1"]["mean_rank_rule"]
    raw = (out / "summary.json").read_text()
    assert raw.startswith('{\n "A"') and raw.endswith("}\n")
    assert (out / "summary.md").read_text() == vs.render(summary)


def test_the_archive_and_rule_directories_point_into_the_evidence_tree():
    root = vs.EVIDENCE
    assert (
        root / "labelled_pool" / "runs",
        root / "full_registry" / "pool_deep" / "runs",
    ) == vs.ARCHIVE
    assert (
        root / "validity" / "seeds_5_9" / "classical",
        root / "validity" / "seeds_5_9" / "deep",
    ) == vs.NEW
    assert (
        root / "validity" / "label_rules" / "classical",
        root / "validity" / "label_rules" / "deep",
    ) == vs.RULE_DIRS
    assert root.name == "evidence" and root.parent.name == "verification"


# ---------------------------------------------------------------------------------------------
# Varied data: per-problem noise makes every source and detector differ, so wiring errors show.
# ---------------------------------------------------------------------------------------------
BASE = {"zscore": 0.55, "isolation_forest": 0.7, "knn": 0.5, NEURAL: 0.3, "lof": 0.6, "exact5": 0.4}
LENGTH = {"zscore": 10, "isolation_forest": 10, "knn": 10, NEURAL: 10, "lof": 7, "exact5": 5}


def _varied():
    """Eleven problems of ten sources (adbench:breastw is the twin of uci:15)."""
    rng = np.random.default_rng(11)
    problems = ["uci:15", "adbench:breastw"] + [f"uci:{i}" for i in range(2, 11)]
    out = {}
    for p in problems:
        out[p] = {}
        for m, base in BASE.items():
            if m == "knn" and p == "uci:2":
                continue  # one problem of eleven lacks this detector
            values = list(base + rng.normal(0, 0.08, LENGTH[m]))
            if m == "lof":
                values[5:] = [0.0, 0.0]  # the sixth seed must not enter the five-seed mean
            out[p][m] = values
    return out


def _expected_tables(seeded):
    ten = {
        p: {m: float(np.mean(v)) for m, v in d.items() if len(v) >= 10} for p, d in seeded.items()
    }
    five = {
        p: {m: float(np.mean(v[:5])) for m, v in d.items() if len(v) >= 5}
        for p, d in seeded.items()
    }
    return ten, five


def test_part_a_agrees_with_an_independent_computation_on_varied_data():
    seeded = _varied()
    a = vs.part_a(seeded, DRAWS)
    ten, five = _expected_tables(seeded)
    groups, table = vs.source_table(ten)
    _, table5 = vs.source_table(five)
    assert a["problems"] == 11 and a["independent_sources"] == 10 == len(groups)
    assert a["pairwise"] == pinf.pairwise(table, DRAWS)
    assert a["ten_seeds"] == vs.ranking(table, DRAWS)
    assert a["five_seeds"] == vs.ranking(table5, DRAWS)
    # exact5 has exactly five seeds: in the five-seed ranking only; lof's sixth seed is ignored
    assert "exact5" in a["five_seeds"]["detectors"] and "exact5" not in a["ten_seeds"]["detectors"]
    assert "lof" in a["five_seeds"]["detectors"]
    # knn is missing from one problem: 9 of 10 sources still reach the 90 % coverage
    assert "knn" in a["ten_seeds"]["detectors"] and a["ten_seeds"]["units"] == 9
    fams = {
        name: np.nanmean(np.column_stack([table[m] for m in table if vs.family(m) == name]), axis=1)
        for name in ("rule", "classical", "neural")
    }
    assert a["families"] == pinf.pairwise(fams, DRAWS)
    problem_table = {m: np.array([ten[p].get(m, np.nan) for p in sorted(ten)]) for m in table}
    assert a["problem_level_ranking"] == vs.ranking(problem_table, DRAWS)
    assert a["problem_level_ranking"]["units"] == 10  # knn is absent from one of eleven problems


def test_part_a_counts_pairs_significant_after_holm_with_a_strict_threshold():
    a = vs.part_a(_varied(), DRAWS)
    assert a["pairs_significant_holm_05"] == sum(r["p_holm"] < 0.05 for r in a["pairwise"])
    assert a["pairs_total"] == len(a["pairwise"]) == 6


def test_part_b_ranks_only_the_detectors_that_both_the_baseline_and_the_rule_ran():
    seeded, runs = _rules_world()
    for d in (seeded, runs):
        for p in list(d):
            d[p]["d"] = [0.1] * len(d[p]["a"])
    runs = {p: {m: v for m, v in d.items() if m != "c"} for p, d in runs.items()}
    r = vs.part_b(seeded, {"R1": runs}, DRAWS)["R1"]
    assert set(r["mean_rank_rule"]) == {"a", "b", "d"}
    assert set(r["mean_rank_R0"]) == {"a", "b", "c", "d"}
    assert r["R0_leader"] == "a" and r["R0_leader_rank_under_rule"] == 2
    assert r["leader_under_rule"] == "b"
    assert r["kendall_tau_vs_R0"] == pytest.approx(1 / 3)


def test_the_report_keeps_its_blank_separator_lines():
    lines = vs.render(_summary()).splitlines()
    blank = [i for i, line in enumerate(lines) if line == ""]
    assert blank == [1, 3, 5, 12, 18, 20]
    assert not any("XXXX" in line for line in lines)


def test_main_skips_failed_and_inapplicable_runs_but_keeps_reading_the_directory(
    tmp_path, monkeypatch
):
    old, new = tmp_path / "old", tmp_path / "new"
    rules_c, rules_d = tmp_path / "rc", tmp_path / "rd"
    evidence = tmp_path / "evidence"
    (evidence / "validity").mkdir(parents=True)
    names = {"zscore": 0.9, "isolation_forest": 0.6, NEURAL: 0.3}
    for i in range(1, 7):
        for directory, seeds in ((old, range(5)), (new, range(5, 10))):
            _run(directory, f"p{i}", f"uci:{i}", {m: [v] * 5 for m, v in names.items()}, seeds)
        _run(
            rules_c,
            f"r{i}",
            f"uci:{i}",
            {m: [v] * 3 for m, v in {"zscore": 0.6, "isolation_forest": 0.9, NEURAL: 0.3}.items()},
            range(3),
            "R1",
        )
    # a failed and an inapplicable run come first in sorted order and must be skipped, not stop
    # the reading of the files that follow them
    _run(rules_d, "a_failed", "uci:7", {"zscore": [0.0] * 3}, range(3), "R1", failed="x")
    _run(rules_d, "b_na", "uci:8", {"zscore": [0.0] * 3}, range(3), "R1", not_applicable="x")
    _run(rules_d, "c_good", "uci:6", {NEURAL: [0.3] * 3}, range(3), "R1")
    for directory in (old, new):
        _run(directory, "p7", "uci:7", {m: [0.5] * 5 for m in names}, range(5))
        _run(directory, "p8", "uci:8", {m: [0.5] * 5 for m in names}, range(5))
    monkeypatch.setattr(vs, "ARCHIVE", (old,))
    monkeypatch.setattr(vs, "NEW", (new,))
    monkeypatch.setattr(vs, "RULE_DIRS", (rules_c, rules_d))
    monkeypatch.setattr(vs, "EVIDENCE", evidence)
    monkeypatch.setattr(vs.pinf, "DRAWS", DRAWS)
    assert vs.main() == 0
    summary = json.loads((evidence / "validity" / "summary.json").read_text())
    assert summary["B"]["R1"]["problems"] == 6
    raw = (evidence / "validity" / "summary.json").read_text()
    assert list(summary["A"]) == sorted(summary["A"])
    assert raw.index('"V3"') < raw.index('"families"') < raw.index('"pairwise"')


def test_load_seeds_goes_on_with_the_next_file_after_a_failed_or_inapplicable_run(tmp_path):
    d = tmp_path / "d"
    _run(d, "a", "uci:1", {"m": [0.1, 0.2]}, [0, 1], failed="boom")
    _run(d, "b", "uci:2", {"m": [0.3, 0.4]}, [0, 1], not_applicable="none")
    _run(d, "c", "uci:3", {"m": [0.5, 0.6]}, [0, 1])
    assert vs.load_seeds((d,)) == {"uci:3": {"m": [0.5, 0.6]}}
