"""Source grouping, per-problem averaging, cluster resampling and multiplicity."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import source_clustered as sc  # noqa: E402


def test_an_adbench_problem_derived_from_a_uci_table_takes_that_source():
    assert sc.source_id("adbench:annthyroid") == "uci:102"
    assert sc.source_id("adbench:thyroid") == "uci:102"
    assert sc.source_id("adbench:fraud") == "adbench:fraud"
    assert sc.source_id("uci:102") == "uci:102" and sc.source_id("uci:7") == "uci:7"


def _run(directory, problem, methods, seeds=(1, 2), failed=False):
    payload = {"problem": problem, "seeds": list(seeds), "metrics": methods}
    if failed:
        payload = {"problem": problem, "failed": "boom"}
    (directory / f"{problem.replace(':', '_')}.json").write_text(json.dumps(payload))


def _rows(*values):
    return [{"pr_auc": v} for v in values]


def test_the_average_precision_is_averaged_over_seeds_within_each_problem(tmp_path):
    _run(tmp_path, "uci:1", {"a": _rows(0.2, 0.4), "b": _rows(0.1, 0.1)})
    _run(tmp_path, "uci:2", {"a": _rows(0.6, 0.8)})
    problems, table = sc.load_ap([tmp_path])
    assert problems == ["uci:1", "uci:2"]
    assert table["a"].tolist() == pytest.approx([0.3, 0.7])
    assert table["b"][0] == pytest.approx(0.1) and np.isnan(table["b"][1])


def test_failed_runs_and_methods_with_missing_seeds_are_not_used(tmp_path):
    _run(tmp_path, "uci:1", {}, failed=True)
    _run(tmp_path, "uci:2", {"a": _rows(0.5), "b": _rows(0.2, 0.4)})
    problems, table = sc.load_ap([tmp_path])
    assert problems == ["uci:2"] and "a" not in table and table["b"][0] == pytest.approx(0.3)


def test_directories_are_merged_by_problem(tmp_path):
    first, second = tmp_path / "x", tmp_path / "y"
    first.mkdir(), second.mkdir()  # noqa: E702
    _run(first, "uci:1", {"a": _rows(0.2, 0.2)})
    _run(second, "uci:1", {"b": _rows(0.4, 0.4)})
    problems, table = sc.load_ap([first, second])
    assert problems == ["uci:1"] and table["a"][0] == pytest.approx(0.2) and table["b"][0] == 0.4


def test_the_bootstrap_is_deterministic_and_reports_the_point_estimates():
    differences = np.array([0.1, 0.2, -0.1, 0.0, 0.3, 0.05])
    clusters = np.array(list("abcdef"))
    one = sc.bootstrap(differences, clusters, by_cluster=False, draws=500)
    assert one == sc.bootstrap(differences, clusters, by_cluster=False, draws=500)
    assert one["mean"] == pytest.approx(differences.mean())
    assert one["median"] == pytest.approx(np.median(differences))
    assert one["mean_ci"][0] < one["mean"] < one["mean_ci"][1] and one["units"] == 6


def test_a_constant_positive_difference_has_a_degenerate_interval_and_zero_p_value():
    result = sc.bootstrap(np.full(10, 0.2), np.arange(10).astype(str), by_cluster=True, draws=200)
    assert (
        result["mean_ci"] == (pytest.approx(0.2), pytest.approx(0.2))
        and result["p_two_sided"] == 0.0
    )
    assert result["median_ci"][0] == pytest.approx(0.2)


def test_a_symmetric_difference_gives_a_large_p_value_and_an_interval_around_zero():
    differences = np.r_[np.full(20, 0.1), np.full(20, -0.1)]
    result = sc.bootstrap(differences, np.arange(40).astype(str), by_cluster=False, draws=2000)
    assert result["p_two_sided"] > 0.5 and result["mean_ci"][0] < 0 < result["mean_ci"][1]


def test_resampling_whole_sources_widens_the_interval_when_problems_share_their_outcome():
    differences = np.repeat(np.array([0.3, -0.2, 0.1, -0.3, 0.2]), 6)
    clusters = np.repeat(np.arange(5).astype(str), 6)
    by_problem = sc.bootstrap(differences, clusters, by_cluster=False, draws=3000)
    by_source = sc.bootstrap(differences, clusters, by_cluster=True, draws=3000)
    width = lambda r: r["mean_ci"][1] - r["mean_ci"][0]  # noqa: E731
    assert by_source["units"] == 5 and by_problem["units"] == 30
    assert width(by_source) > 1.4 * width(by_problem)


def test_holm_adjustment_matches_the_textbook_values_in_input_order():
    assert sc.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert sc.holm([0.5, 0.5]) == pytest.approx([1.0, 1.0])
    assert sc.holm([0.001]) == [0.001]
    assert sc.holm([0.4, 0.001]) == pytest.approx([0.4, 0.002])


def _table(n=30, seed=0):
    rng = np.random.default_rng(seed)
    problems = [f"uci:{i}" for i in range(n - 6)] + [f"adbench:{name}" for name in (
        "annthyroid", "thyroid", "cardio", "fraud", "skin", "wine")]  # fmt: skip
    base = rng.uniform(0.1, 0.5, size=n)
    names = {m for pair in sc.COMPARISONS for m in pair}
    return problems, {
        m: base + rng.normal(0, 0.01, n) + (0.2 if m == "great_expectations" else 0) for m in names
    }


def test_the_analysis_counts_unique_sources_and_overlapping_adbench_problems():
    problems, table = _table()
    problems[0], problems[1] = "uci:102", "uci:193"  # the sources of annthyroid/thyroid and cardio
    result = sc.analyse(problems, table, draws=200)
    assert result["problems"] == 30
    assert result["sources"] == 30 - 3 and result["overlapping_adbench_problems"] == 3
    assert [c["comparison"] for c in result["comparisons"]][0] == "ecod - isolation_forest"
    assert all(c["without_overlap"]["problems"] == 27 for c in result["comparisons"])
    assert result["seed"] == sc.SEED and result["level"] == 0.95 and result["bootstraps"] == 200


def test_the_analysis_uses_only_problems_where_both_detectors_ran():
    problems, table = _table()
    table["ocsvm"] = table["ocsvm"].copy()
    table["ocsvm"][:5] = np.nan
    result = sc.analyse(problems, table, draws=200)
    entry = next(c for c in result["comparisons"] if c["comparison"].startswith("ocsvm"))
    assert entry["problems"] == 25 and entry["by_problem"]["units"] == 25


def test_a_clear_effect_survives_the_multiplicity_correction_and_a_null_one_does_not():
    problems, table = _table()
    result = sc.analyse(problems, table, draws=2000)
    by_name = {c["comparison"]: c for c in result["comparisons"]}
    assert by_name["great_expectations - isolation_forest"]["holm_p_by_source"] < 0.01
    assert by_name["ecod - isolation_forest"]["holm_p_by_source"] > 0.05
    assert by_name["great_expectations - isolation_forest"]["by_source"]["mean"] == pytest.approx(
        0.2, abs=0.02
    )


def test_the_command_reads_the_runs_and_writes_the_analysis(tmp_path, monkeypatch, capsys):
    classical, deep = tmp_path / "c", tmp_path / "d"
    classical.mkdir(), deep.mkdir()  # noqa: E702
    for i in range(8):
        methods = {m: _rows(0.2 + 0.01 * i, 0.2) for m in ("ecod", "isolation_forest", "copod",
                   "ocsvm", "zscore", "great_expectations")}  # fmt: skip
        _run(classical, f"uci:{i}", methods)
        _run(deep, f"uci:{i}", {"dif": _rows(0.1, 0.1)})
    monkeypatch.setattr(sc, "BOOTSTRAPS", 50)
    output = tmp_path / "out.json"
    assert (
        sc.main(["--classical", str(classical), "--deep", str(deep), "--output", str(output)]) == 0
    )
    result = json.loads(output.read_text())
    assert (result["problems"], result["sources"], result["bootstraps"]) == (8, 8, 50)
    assert len(result["comparisons"]) == len(sc.COMPARISONS)
    assert capsys.readouterr().out.strip() == "8 problems, 8 sources"
