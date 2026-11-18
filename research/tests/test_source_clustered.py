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


# --- the bootstrap is pinned against an independent derivation of its definition ---------------


def _reference(differences, clusters, by_cluster, draws):
    """Percentile bootstrap re-derived from the definition: seed, resample, count, interval."""
    rng = np.random.default_rng(sc.SEED)
    n = len(differences)
    labels = np.unique(clusters)
    means, medians = [], []
    for _ in range(draws):
        if by_cluster:
            chosen = labels[rng.integers(0, len(labels), len(labels))]
            index = np.concatenate([np.flatnonzero(clusters == c) for c in chosen])
        else:
            index = rng.integers(0, n, n)
        means.append(differences[index].mean())
        medians.append(np.median(differences[index]))
    means, medians = np.array(means), np.array(medians)
    below, above = (means <= 0).mean(), (means >= 0).mean()
    return {
        "units": len(labels) if by_cluster else n,
        "mean": differences.mean(),
        "mean_ci": tuple(np.quantile(means, [0.025, 0.975])),
        "median": np.median(differences),
        "median_ci": tuple(np.quantile(medians, [0.025, 0.975])),
        "p_two_sided": min(1.0, 2 * min(below, above)),
    }


@pytest.mark.parametrize("by_cluster", [False, True])
def test_the_bootstrap_equals_its_definition_including_the_zero_boundary(by_cluster):
    differences = np.array([-1.0, 1.0, 0.0, 0.0, 2.0, -0.5])
    clusters = np.array(["a", "a", "b", "c", "c", "d"])
    got = sc.bootstrap(differences, clusters, by_cluster=by_cluster, draws=400)
    want = _reference(differences, clusters, by_cluster, 400)
    assert got["units"] == want["units"]
    for key in ("mean", "median", "p_two_sided"):
        assert got[key] == pytest.approx(want[key], abs=1e-12)
    for key in ("mean_ci", "median_ci"):
        assert got[key] == pytest.approx(want[key], abs=1e-12)


def test_the_interval_is_the_central_ninety_five_percent():
    assert sc.LEVEL == 0.95
    assert sc._interval(np.arange(1001.0)) == pytest.approx((25.0, 975.0))


def test_p_value_is_twice_the_smaller_tail_and_capped_at_one():
    draws = 600
    positive = sc.bootstrap(
        np.array([0.0, 0.0, 1.0]), np.array(list("abc")), by_cluster=False, draws=draws
    )
    reference = _reference(np.array([0.0, 0.0, 1.0]), np.array(list("abc")), False, draws)
    assert positive["p_two_sided"] == pytest.approx(reference["p_two_sided"])
    assert 0.0 < positive["p_two_sided"] <= 1.0
    centred = sc.bootstrap(
        np.array([-1.0, 1.0]), np.array(["a", "b"]), by_cluster=False, draws=draws
    )
    assert centred["p_two_sided"] == 1.0  # both tails exceed one half


class _Spy:
    def __init__(self):
        self.calls = []

    def __call__(self, differences, clusters, *, by_cluster, draws):
        self.calls.append((differences.tolist(), clusters.tolist(), by_cluster, draws))
        return {"p_two_sided": 0.5, "units": 0}


def test_each_comparison_is_resampled_by_problem_by_source_and_without_overlap(monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(sc, "bootstrap", spy)
    problems = ["adbench:glass", "uci:42", "uci:1", "uci:109"]  # wine derives from UCI 109
    base = np.array([0.5, 0.6, 0.7, 0.8])
    names = {m for pair in sc.COMPARISONS for m in pair}
    table = {m: base.copy() for m in names}
    table["ecod"] = base + np.array([0.1, 0.2, 0.3, 0.4])  # ecod minus isolation_forest
    result = sc.analyse(problems, table, draws=17)
    first = spy.calls[:3]
    diffs = [0.1, 0.2, 0.3, 0.4]
    sources = ["uci:42", "uci:42", "uci:1", "uci:109"]  # wine derives from UCI 109
    assert first[0] == (pytest.approx(diffs), sources, False, 17)
    assert first[1] == (pytest.approx(diffs), sources, True, 17)
    assert first[2] == (pytest.approx(diffs[1:]), sources[1:], True, 17)  # glass overlaps uci:42
    assert result["comparisons"][0]["without_overlap"]["problems"] == 3
    assert result["overlapping_adbench_problems"] == 1 and result["sources"] == 3  # 42, 1, 109
    assert [c[3] for c in spy.calls] == [17] * len(spy.calls)


def test_wine_without_a_labelled_counterpart_is_not_counted_as_overlap():
    problems = ["adbench:wine", "uci:1", "uci:2"]
    table = {m: np.array([0.5, 0.6, 0.7]) for pair in sc.COMPARISONS for m in pair}
    assert sc.analyse(problems, table, draws=20)["overlapping_adbench_problems"] == 0


def test_the_default_number_of_resamples_is_used_when_none_is_requested(monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(sc, "bootstrap", spy)
    table = {m: np.array([0.5, 0.6]) for pair in sc.COMPARISONS for m in pair}
    result = sc.analyse(["uci:1", "uci:2"], table)
    assert result["bootstraps"] == sc.BOOTSTRAPS == 10_000
    assert {c[3] for c in spy.calls} == {10_000}


def test_the_command_defaults_point_at_the_archived_runs_and_the_output_is_sorted_json(
    tmp_path, monkeypatch, capsys
):
    seen = {}
    monkeypatch.setattr(sc, "load_ap", lambda dirs: seen.setdefault("dirs", dirs) and ([], {}))
    monkeypatch.setattr(
        sc, "analyse", lambda problems, table: {"problems": 0, "sources": 0, "b": 1, "a": 2}
    )
    out = tmp_path / "o.json"
    assert sc.main(["--output", str(out)]) == 0
    root = Path(sc.__file__).resolve().parent.parent / "verification" / "evidence"
    assert seen["dirs"] == [
        root / "labelled_pool" / "runs",
        root / "full_registry" / "pool_deep" / "runs",
    ]
    assert out.read_text() == '{\n "a": 2,\n "b": 1,\n "problems": 0,\n "sources": 0\n}\n'
    with pytest.raises(SystemExit) as stop:
        sc.main([])
    assert stop.value.code == 2
    capsys.readouterr()
    with pytest.raises(SystemExit):
        sc.main(["--help"])
    assert "Source-clustered paired comparison of detectors" in " ".join(
        capsys.readouterr().out.split()
    )


def test_a_holm_adjustment_of_the_wrong_length_is_refused(monkeypatch):
    problems, table = _table()
    monkeypatch.setattr(sc, "holm", lambda p: list(p)[:-1])
    with pytest.raises(ValueError, match="zip"):
        sc.analyse(problems, table, draws=20)
