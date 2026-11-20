"""Chronological summary on hand-computed runs: units, intervals, hypotheses, report, command."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chrono_injected_summary as cis  # noqa: E402


def arm(fpr, recall):
    return {"fpr": fpr, "recall": {m: {"a": r, "b": r + 0.1} for m, r in recall.items()}}


def run(ident, c_fpr, r_fpr, c_rec, r_rec):
    return {
        "id": ident,
        "arms": {
            "chronological": arm(c_fpr, c_rec),
            "random": arm(r_fpr, r_rec),
        },
    }


RUNS = {
    "uci_1": run("uci:1", {"knn": 0.30, "zscore": 0.10}, {"knn": 0.10, "zscore": 0.12},
                 {"knn": 0.6, "zscore": 0.3}, {"knn": 0.5, "zscore": 0.3}),
    "uci_2": run("uci:2", {"knn": 0.20, "zscore": 0.05}, {"knn": 0.10, "zscore": 0.05},
                 {"knn": 0.7, "zscore": 0.2}, {"knn": 0.6, "zscore": 0.4}),
    "uci_3": run("uci:3", {"knn": 0.50, "zscore": 0.10}, {"knn": 0.20, "zscore": 0.08},
                 {"knn": 0.8, "zscore": 0.1}, {"knn": 0.6, "zscore": 0.5}),
}  # fmt: skip


def test_load_reads_every_run_keyed_by_file_stem(tmp_path):
    for stem, payload in RUNS.items():
        (tmp_path / f"{stem}.json").write_text(json.dumps(payload))
    (tmp_path / "ignored.txt").write_text("x")
    assert cis.load(tmp_path) == RUNS


def test_paired_differences_are_taken_per_table_in_table_order():
    out = cis.paired(RUNS)
    assert sorted(out) == ["knn", "zscore"]
    assert list(out["knn"]["fpr"]) == pytest.approx([0.20, 0.10, 0.30])
    assert list(out["zscore"]["fpr"]) == pytest.approx([-0.02, 0.0, 0.02])
    assert list(out["knn"]["recall"]) == pytest.approx([0.1, 0.1, 0.2])
    assert list(out["zscore"]["recall"]) == pytest.approx([0.0, -0.2, -0.4])
    assert cis._mean_recall(RUNS["uci_1"]["arms"]["chronological"], "knn") == pytest.approx(0.65)
    assert cis._cell(0.1234, [-0.05, 0.2]) == "+0.123 [-0.050, +0.200]"


def test_bootstrap_interval_of_the_median_is_seeded_and_uses_the_draw_count():
    values = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    assert cis.interval(values) == [0.1, 0.5]
    assert cis.interval(values, seed=1, draws=50) == [0.2, 0.5]
    assert cis.interval(np.arange(10.0)) == [2.0, 7.0]
    assert cis.interval(np.array([0.3, 0.3])) == [0.3, 0.3]


def test_ranking_agreement_is_the_mean_rank_correlation_over_tables():
    same = {
        "t": {
            "arms": {
                a: {"recall": {"m1": {"x": 0.1}, "m2": {"x": 0.5}, "m3": {"x": 0.9}}}
                for a in ("chronological", "random")
            }
        }
    }
    assert cis.ranking_agreement(same) == pytest.approx(1.0)
    flipped = json.loads(json.dumps(same))
    flipped["t"]["arms"]["random"]["recall"] = {
        "m1": {"x": 0.9},
        "m2": {"x": 0.5},
        "m3": {"x": 0.1},
    }
    assert cis.ranking_agreement(flipped) == pytest.approx(-1.0)
    both = {"a": same["t"], "b": flipped["t"]}
    assert cis.ranking_agreement(both) == pytest.approx(0.0)


def test_summary_holds_per_detector_medians_and_the_three_hypotheses():
    s = cis.summarise_runs(RUNS)
    assert s["n_tables"] == 3 and s["tables"] == ["uci:1", "uci:2", "uci:3"]
    knn = s["detectors"]["knn"]
    assert knn["fpr_median_difference"] == pytest.approx(0.20)
    assert knn["recall_median_difference"] == pytest.approx(0.1)
    assert knn["tables_fpr_higher"] == 3
    assert s["detectors"]["zscore"]["tables_fpr_higher"] == 1
    assert s["C1_median_detector_fpr_difference"] == pytest.approx(0.1)  # median of 0.20 and 0.0
    assert s["C2_median_detector_recall_difference"] == pytest.approx(-0.05)
    assert s["C2_abs_recall_smaller_than_fpr"] is True
    assert -1.0 <= s["C3_mean_rank_correlation"] <= 1.0


def test_report_lists_each_detector_and_the_three_hypothesis_values():
    text = cis.report(cis.summarise_runs(RUNS))
    assert text.startswith("# Chronological study with controlled injection\n\n3 real time-series")
    assert "| knn | +0.200 [" in text and "| zscore | +0.000 [" in text and "| 3/3 |" in text
    assert "C1 median detector FPR difference: +0.1000" in text
    assert "C2 median detector recall difference: -0.0500 (smaller in magnitude" in text
    assert "rank correlation of detector recall between the arms:" in text


def test_main_writes_summary_files_and_prints_the_report(tmp_path, capsys):
    folder = tmp_path / "runs"
    folder.mkdir()
    for stem, payload in RUNS.items():
        (folder / f"{stem}.json").write_text(json.dumps(payload))
    out = tmp_path / "out"
    assert cis.main([str(folder), "--out", str(out)]) == 0
    saved = json.loads((out / "summary.json").read_text())
    assert saved["n_tables"] == 3
    assert (out / "summary.md").read_text() == capsys.readouterr().out.rstrip("\n") + "\n"


# --- contracts -------------------------------------------------------------------------------


def test_the_interval_uses_seed_2026_and_5000_draws_by_default():
    values = np.random.default_rng(5).uniform(size=30)
    rng = np.random.default_rng(2026)
    boot = np.median(rng.choice(values, (5000, len(values))), axis=1)
    assert cis.interval(values) == [float(x) for x in np.quantile(boot, [0.025, 0.975])]
    assert (cis.SEED, cis.DRAWS) == (2026, 5000)
    assert cis.interval(values) != cis.interval(values, seed=2027)


def test_c2_compares_magnitudes_not_signs():
    big_negative = {"t": run("uci:1", {"knn": 0.1}, {"knn": 0.1}, {"knn": 0.1}, {"knn": 0.9})}
    s = cis.summarise_runs(big_negative)
    assert s["C2_median_detector_recall_difference"] == pytest.approx(-0.8)
    assert s["C2_abs_recall_smaller_than_fpr"] is False


def test_report_text_is_exact():
    summary = {
        "n_tables": 3,
        "detectors": {
            "knn": {
                "fpr_median_difference": 0.2,
                "fpr_ci": [0.1, 0.3],
                "recall_median_difference": -0.05,
                "recall_ci": [-0.1, 0.0],
                "tables_fpr_higher": 2,
            }
        },
        "C1_median_detector_fpr_difference": 0.2,
        "C2_median_detector_recall_difference": -0.05,
        "C2_abs_recall_smaller_than_fpr": True,
        "C3_mean_rank_correlation": 0.912,
    }
    assert cis.report(summary) == (
        "# Chronological study with controlled injection\n"
        "\n"
        "3 real time-series tables. Differences are chronological minus random.\n"
        "\n"
        "| detector | FPR difference (median, 95% CI) | recall difference | higher FPR |\n"
        "|---|---|---|---|\n"
        "| knn | +0.200 [+0.100, +0.300] | -0.050 [-0.100, +0.000] | 2/3 |\n"
        "\n"
        "C1 median detector FPR difference: +0.2000\n"
        "C2 median detector recall difference: -0.0500"
        " (smaller in magnitude than the FPR difference: True)\n"
        "C3 mean rank correlation of detector recall between the arms: 0.91\n"
    )


def test_main_writes_both_files_with_exact_formatting(tmp_path):
    folder = tmp_path / "runs"
    folder.mkdir()
    (folder / "a.json").write_text(json.dumps(RUNS["uci_1"]))
    out = tmp_path / "deep" / "out"
    assert cis.main([str(folder), "--out", str(out)]) == 0
    summary = cis.summarise(folder)
    assert (out / "summary.json").read_text() == json.dumps(
        summary, indent=1, sort_keys=True
    ) + "\n"
    assert (out / "summary.md").read_text() == cis.report(summary)
    assert cis.PARSER.parse_args(["f", "--out", "o"]).folder == Path("f")
    with pytest.raises(SystemExit):
        cis.PARSER.parse_args(["f"])


def test_writing_into_an_existing_directory_is_allowed_and_creates_missing_parents(tmp_path):
    summary = cis.summarise_runs(RUNS)
    cis.write_summary(tmp_path, summary)
    cis.write_summary(tmp_path, summary)
    nested = tmp_path / "x" / "y"
    cis.write_summary(nested, summary)
    assert json.loads((nested / "summary.json").read_text())["n_tables"] == 3
