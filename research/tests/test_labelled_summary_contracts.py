"""Exact table, bootstrap, rank, hypothesis and report behaviour of the labelled-pool summary."""

import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import labelled_summary as ls  # noqa: E402


def _run(problem, source, prevalence, **methods):
    """methods: name -> (pr_auc, flagged_pct) as a single identical seed, or a list of seeds."""
    metrics = {}
    for name, value in methods.items():
        seeds = value if isinstance(value, list) else [value]
        metrics[name] = [
            {"pr_auc": pr, "roc_auc": pr + 0.1, "f1": pr / 2, "flagged_pct": flagged}
            for pr, flagged in seeds
        ]
    return {"problem": problem, "source": source, "prevalence": prevalence, "metrics": metrics}


def test_the_table_averages_the_seeds_skips_failed_problems_and_names_its_columns():
    runs = [
        _run("a", "uci", 0.1, zscore=[(0.2, 10.0), (0.4, 20.0)]),
        {"problem": "bad", "failed": "boom"},
    ]
    out = ls.table(runs)
    assert list(out.columns) == [
        "problem", "source", "prevalence", "method", "pr_auc", "roc_auc", "f1", "flagged_pct",
    ]  # fmt: skip
    row = out.iloc[0]
    assert len(out) == 1 and row["problem"] == "a" and row["source"] == "uci"
    assert row["prevalence"] == 0.1 and row["method"] == "zscore"
    assert row["pr_auc"] == pytest.approx(0.3) and row["roc_auc"] == pytest.approx(0.4)
    assert row["f1"] == pytest.approx(0.15) and row["flagged_pct"] == pytest.approx(15.0)


def _wide_table(values, prevalences=None, sources=None, flagged=None):
    """values: {problem: {method: pr_auc}}; one row per problem and method."""
    runs = []
    for problem, methods in values.items():
        prevalence = (prevalences or {}).get(problem, 0.1)
        source = (sources or {}).get(problem, "uci")
        runs.append(
            _run(
                problem, source, prevalence,
                **{m: [(v, (flagged or {}).get((problem, m), 10.0))] for m, v in methods.items()},
            )
        )  # fmt: skip
    return ls.table(runs)


def test_the_bootstrap_follows_its_definition_and_defaults_to_two_thousand_seed_zero():

    assert inspect.signature(ls.pooled).parameters["resamples"].default == 2000
    assert inspect.signature(ls.pooled).parameters["seed"].default == 0
    data = _wide_table(
        {"p0": {"a": 0.1, "b": 0.5}, "p1": {"a": 0.3, "b": 0.7}, "p2": {"a": 0.9, "b": 0.2}}
    )
    out = ls.pooled(data, resamples=30, seed=4)
    values = np.array([[0.1, 0.5], [0.3, 0.7], [0.9, 0.2]])
    rng = np.random.default_rng(4)
    boot = np.stack([np.nanmedian(values[rng.integers(0, 3, 3)], axis=0) for _ in range(30)])
    assert out.index.tolist() == ["a", "b"] and list(out.columns) == ["median", "lo", "hi"]
    assert out["median"].tolist() == [0.3, 0.5]
    assert np.allclose(out["lo"], np.nanpercentile(boot, 2.5, axis=0))
    assert np.allclose(out["hi"], np.nanpercentile(boot, 97.5, axis=0))
    roc = ls.pooled(data, "roc_auc", resamples=5)
    assert roc["median"].tolist() == pytest.approx([0.4, 0.6])


def test_ranks_give_one_to_the_best_share_ties_and_put_methods_in_rows():
    data = _wide_table({"p0": {"a": 0.9, "b": 0.5, "c": 0.5}, "p1": {"a": 0.1, "b": 0.5, "c": 0.9}})
    ranks = ls.ranks(data)
    assert ranks.index.tolist() == ["a", "b", "c"] and ranks.columns.tolist() == ["p0", "p1"]
    assert ranks.loc["a"].tolist() == [1.0, 3.0]
    assert ranks.loc["b"].tolist() == [2.5, 2.0] and ranks.loc["c"].tolist() == [2.5, 1.0]


def _flat(problem_values, **kwargs):
    """Identical problems collapse the bootstrap interval onto the median."""
    return _wide_table({f"p{i}": problem_values for i in range(4)}, **kwargs)


def test_h1_holds_when_the_best_interval_reaches_the_second_median_and_names_both():
    close = ls.hypotheses(_flat({"isolation_forest": 0.5, "zscore": 0.5, "iqr": 0.1}), resamples=5)[
        "H1"
    ]
    assert close["supported"] is True and {close["best"], close["second"]} == {
        "isolation_forest",
        "zscore",
    }
    far = ls.hypotheses(_flat({"isolation_forest": 0.9, "zscore": 0.5, "iqr": 0.1}), resamples=5)[
        "H1"
    ]
    assert far == {"supported": False, "best": "isolation_forest", "second": "zscore"}


def test_h2_needs_the_forest_strictly_above_both_rules():
    def h2(forest, z, iqr):
        values = {"isolation_forest": forest, "zscore": z, "iqr": iqr}
        return ls.hypotheses(_flat(values), resamples=5)["H2"]["supported"]

    assert h2(0.5, 0.4, 0.3) is True
    assert h2(0.4, 0.4, 0.3) is False
    assert h2(0.4, 0.3, 0.4) is False
    assert h2(0.5, 0.6, 0.3) is False


def _by_prevalence(prevalences, gains):
    values = {
        f"p{i}": {"isolation_forest": 0.5 + gain, "zscore": 0.5, "iqr": 0.1}
        for i, gain in enumerate(gains)
    }
    return ls.hypotheses(
        _wide_table(values, prevalences={f"p{i}": p for i, p in enumerate(prevalences)}),
        resamples=5,
    )["H3"]


def test_h3_bins_problems_by_prevalence_with_half_open_edges_and_needs_a_sign_change():
    out = _by_prevalence([0.02, 0.05, 0.2, 0.9], [0.25, 0.125, -0.25, -0.5])
    assert out["by_prevalence"]["<5%"] == {"median": 0.25, "n": 1}
    assert out["by_prevalence"]["5-20%"] == {"median": 0.125, "n": 1}
    assert out["by_prevalence"][">20%"] == {"median": -0.375, "n": 2}
    assert out["supported"] is True
    zero_high = _by_prevalence([0.02, 0.3], [0.25, 0.0])
    assert zero_high["supported"] is True
    positive_high = _by_prevalence([0.02, 0.3], [0.25, 0.125])
    assert positive_high["supported"] is False
    zero_low = _by_prevalence([0.02, 0.3], [0.0, -0.25])
    assert zero_low["supported"] is False
    empty = _by_prevalence([0.1], [0.25])
    assert empty["by_prevalence"]["<5%"] == {"median": None, "n": 0} and empty["supported"] is False


def _flags(iqr, other, prevalence=0.1):
    values = {m: 0.5 for m in ("isolation_forest", "zscore", "iqr")}
    flagged = {}
    for problem in ("p0", "p1"):
        flagged[(problem, "iqr")] = iqr * 100 * prevalence
        flagged[(problem, "zscore")] = other * 100 * prevalence
        flagged[(problem, "isolation_forest")] = 100 * prevalence
    data = _wide_table(
        {"p0": values, "p1": values},
        prevalences={"p0": prevalence, "p1": prevalence},
        flagged=flagged,
    )
    return ls.hypotheses(data, resamples=5)["H4"]


def test_h4_needs_the_iqr_to_flag_more_than_three_times_the_prevalence_and_more_than_any_other():
    out = _flags(iqr=4.0, other=2.0)
    assert out["supported"] is True
    assert out["median_flag_to_prevalence"] == {"iqr": 4.0, "isolation_forest": 1.0, "zscore": 2.0}
    assert _flags(iqr=3.0, other=2.0)["supported"] is False
    assert _flags(iqr=4.0, other=5.0)["supported"] is False
    assert _flags(iqr=4.0, other=4.0)["supported"] is True


def test_h5_is_the_rank_agreement_of_the_two_sources_and_nan_without_two_usable_sources():
    values = {
        f"p{i}": {"isolation_forest": 0.1 * (i % 3), "zscore": 0.2, "iqr": 0.9 - 0.1 * (i % 3)}
        for i in range(6)
    }
    sources = {f"p{i}": ("uci" if i < 3 else "adbench") for i in range(6)}
    out = ls.hypotheses(_wide_table(values, sources=sources), resamples=5)["H5"]
    assert out["supported"] is (out["spearman"] >= 0.7) and not np.isnan(out["spearman"])
    one_source = ls.hypotheses(_wide_table(values), resamples=5)["H5"]
    assert one_source["supported"] is False and np.isnan(one_source["spearman"])
    lonely = {f"p{i}": ("uci" if i < 5 else "adbench") for i in range(6)}
    single = ls.hypotheses(_wide_table(values, sources=lonely), resamples=5)["H5"]
    assert np.isnan(single["spearman"]) and single["supported"] is False


def test_h5_accepts_a_rank_agreement_of_exactly_seven_tenths(monkeypatch):
    values = {f"p{i}": {"isolation_forest": 0.1, "zscore": 0.2, "iqr": 0.3} for i in range(4)}
    sources = {f"p{i}": ("uci" if i < 2 else "adbench") for i in range(4)}
    from types import SimpleNamespace

    for rho, expected in ((0.7, True), (0.69, False)):
        monkeypatch.setattr(ls, "spearmanr", lambda a, b, r=rho: SimpleNamespace(statistic=r))
        out = ls.hypotheses(_wide_table(values, sources=sources), resamples=5)["H5"]
        assert out["supported"] is expected and out["spearman"] == rho


def _registry_inputs(new, forest=0.5, deep=None):
    classical = {"isolation_forest": forest, "zscore": 0.3, **new}
    classical_data = _flat(classical)
    deep_data = _flat(deep or {"vae": 0.4, "dif": 0.45})
    return classical_data, deep_data


def test_registry_h1_needs_one_new_classical_detector_strictly_above_the_forest():
    classical, deep = _registry_inputs(
        {"ecod": 0.6, "copod": 0.1, "hbos": 0.1, "knn": 0.1, "pca": 0.1}
    )
    out = ls.registry_hypotheses(classical, deep, [])["H1"]
    assert out["supported"] is True and out["isolation_forest"] == 0.5
    assert out["new_classical"] == {"ecod": 0.6, "copod": 0.1, "hbos": 0.1, "knn": 0.1, "pca": 0.1}
    tie = _registry_inputs({m: 0.5 for m in ls.NEW_CLASSICAL})
    assert ls.registry_hypotheses(*tie, [])["H1"]["supported"] is False


def test_registry_h2_allows_the_deep_detectors_two_points_over_the_best_classical_median():
    new = {m: 0.1 for m in ls.NEW_CLASSICAL}
    inside = _registry_inputs(new, deep={"vae": 0.5, "dif": 0.5})
    out = ls.registry_hypotheses(*inside, [])["H2"]
    assert out["supported"] is True and out["best_classical"] == {
        "method": "isolation_forest",
        "median": 0.5,
    }
    assert out["deep"] == {"vae": 0.5, "dif": 0.5}
    over = _registry_inputs(new, deep={"vae": 0.53, "dif": 0.4})
    assert ls.registry_hypotheses(*over, [])["H2"]["supported"] is False
    edge = _registry_inputs(new, forest=0.5, deep={"vae": 0.5 + ls.DEEP_MARGIN - 1e-9})
    assert ls.registry_hypotheses(*edge, [])["H2"]["supported"] is True


def test_registry_h6_counts_failures_against_the_problems_each_detector_ran_on():
    new = {m: 0.1 for m in ls.NEW_CLASSICAL}
    classical, deep = _registry_inputs(new, deep={"vae": 0.4, "dif": 0.4})
    runs = [{"errors": {"vae": ["x"]}} if i < 1 else {"errors": {}} for i in range(20)]
    runs += [{"failed": "boom"}, {"skipped": ["dif"], "errors": {}}]
    out = ls.registry_hypotheses(classical, deep, runs)["H6"]
    assert out["failures"] == {
        "vae": {"failed": 1, "problems": 21},
        "dif": {"failed": 0, "problems": 20},
    }
    assert out["supported"] is True
    runs[1] = {"errors": {"vae": ["y"]}}
    assert ls.registry_hypotheses(classical, deep, runs)["H6"]["supported"] is False
    runs = [{"errors": {"vae": ["x"]}}] + [{"errors": {}}] * 19
    assert ls.registry_hypotheses(classical, deep, runs)["H6"]["supported"] is True


def test_load_reads_the_json_files_of_a_folder_in_name_order(tmp_path):
    (tmp_path / "b.json").write_text(json.dumps({"n": 2}))
    (tmp_path / "a.json").write_text(json.dumps({"n": 1}))
    (tmp_path / "c.txt").write_text("{}")
    assert ls.load(tmp_path) == [{"n": 1}, {"n": 2}]


def _write_runs(folder, runs):
    folder.mkdir()
    for index, run in enumerate(runs):
        (folder / f"{index}.json").write_text(json.dumps(run))


def _suite():
    methods = ("zscore", "iqr", "great_expectations", "isolation_forest", "lof", "ocsvm")
    runs = []
    for i in range(4):
        values = {m: [(0.2 + 0.05 * k + 0.01 * i, 8.0 + k)] for k, m in enumerate(methods)}
        runs.append(_run(f"p{i}", "uci" if i < 2 else "adbench", 0.1, **values))
    runs.append({"problem": "bad", "failed": "boom"})
    runs[0]["skipped"] = ["lof"]
    return runs


def test_the_command_writes_the_results_and_a_table_and_reports_problems_and_failures(
    tmp_path, capsys
):
    _write_runs(tmp_path / "runs", _suite())
    out = tmp_path / "new" / "out"
    assert ls.main(["--runs", str(tmp_path / "runs"), "--output", str(out)]) == 0
    assert capsys.readouterr().out == "4 problems, 1 failed\n"
    text = (out / "labelled_results.json").read_text()
    results = json.loads(text)
    assert text == json.dumps(results, indent=1, sort_keys=True) + "\n"
    assert results["problems"] == 4 and results["failed"] == {"bad": "boom"}
    assert results["skipped"] == {"p0": ["lof"]}
    assert set(results) == {
        "problems",
        "failed",
        "skipped",
        "pr_auc",
        "roc_auc",
        "median_rank",
        "hypotheses",
    }
    assert set(results["hypotheses"]) == {"H1", "H2", "H3", "H4", "H5"}
    lines = (out / "labelled_results.md").read_text().splitlines()
    assert (
        lines[0] == "Median over 4 labelled problems (95% interval over problems)"
        and lines[1] == ""
    )
    assert lines[2] == "| method | PR-AUC | ROC-AUC | median rank |"
    assert lines[3] == "|---|---|---|---|"
    assert lines[4].startswith("| great_expectations | 0.")
    assert "[" in lines[4] and lines[4].endswith("|")
    assert len(lines) == 4 + 6


def test_the_command_adds_the_neural_section_when_their_runs_are_given(tmp_path):
    _write_runs(tmp_path / "runs", _suite())
    deep = [
        _run(f"p{i}", "uci" if i < 2 else "adbench", 0.1, vae=[(0.3, 9.0)], dif=[(0.35, 9.0)])
        for i in range(4)
    ]
    _write_runs(tmp_path / "deep", deep)
    out = tmp_path / "out"
    argv = [
        "--runs",
        str(tmp_path / "runs"),
        "--deep-runs",
        str(tmp_path / "deep"),
        "--output",
        str(out),
    ]
    assert ls.main(argv) == 0
    results = json.loads((out / "labelled_results.json").read_text())
    assert set(results["deep"]) == {"pr_auc", "roc_auc", "hypotheses"}
    assert set(results["deep"]["hypotheses"]) == {"H1", "H2", "H6"}
    assert set(results["median_rank_all"]) >= {"vae", "dif", "zscore"}
    lines = (out / "labelled_results.md").read_text().splitlines()
    start = lines.index("Neural detectors (fit rows capped, same problems)")
    assert lines[start - 1] == "" and lines[start + 1] == ""
    assert (
        lines[start + 2] == "| method | PR-AUC | ROC-AUC |" and lines[start + 3] == "|---|---|---|"
    )
    assert lines[start + 4].startswith("| dif | 0.350 [0.350, 0.350] | 0.450 [0.450, 0.450] |")
    assert lines[start + 5].startswith("| vae | 0.300 [0.300, 0.300] | 0.400 [0.400, 0.400] |")
    assert lines[-2] == "" and lines[-1].startswith("Median rank over all methods: ")
    with pytest.raises(SystemExit) as stop:
        ls.main(["--runs", str(tmp_path / "runs")])
    assert stop.value.code == 2


def test_the_interval_is_the_2_5_and_97_5_percentiles_of_seeded_bootstraps_of_many_problems():
    gen = np.random.default_rng(21)
    values = np.round(gen.random((12, 2)), 3)
    data = _wide_table({f"p{i:02d}": {"a": row[0], "b": row[1]} for i, row in enumerate(values)})
    out = ls.pooled(data, resamples=400, seed=7)
    rng = np.random.default_rng(7)
    boot = np.stack([np.nanmedian(values[rng.integers(0, 12, 12)], axis=0) for _ in range(400)])
    assert np.allclose(out["lo"], np.nanpercentile(boot, 2.5, axis=0))
    assert np.allclose(out["hi"], np.nanpercentile(boot, 97.5, axis=0))
    assert out.equals(ls.pooled(data, resamples=400, seed=7))
    assert not out.equals(ls.pooled(data, resamples=400, seed=8))
    default = ls.pooled(data)
    rng = np.random.default_rng(0)
    boot = np.stack([np.nanmedian(values[rng.integers(0, 12, 12)], axis=0) for _ in range(2000)])
    assert np.allclose(default["hi"], np.nanpercentile(boot, 97.5, axis=0))


def test_a_failed_run_is_skipped_and_the_runs_after_it_are_still_read():
    runs = [
        {"problem": "bad", "failed": "boom"},
        _run("p0", "uci", 0.1, zscore=[(0.5, 1.0)]),
        _run("p1", "uci", 0.1, zscore=[(0.7, 1.0)]),
    ]
    assert ls.table(runs)["problem"].tolist() == ["p0", "p1"]


def test_hypotheses_use_the_number_of_resamples_they_are_given(monkeypatch):
    seen = []
    real = ls.pooled
    monkeypatch.setattr(
        ls, "pooled", lambda data, *a, **k: seen.append(k.get("resamples")) or real(data, *a, **k)
    )
    data = _wide_table(
        {f"p{i}": {m: 0.1 * (j + 1) + 0.01 * i for j, m in enumerate(ls.CORE)} for i in range(4)},
        sources={"p0": "uci", "p1": "uci", "p2": "adbench", "p3": "adbench"},
    )
    ls.hypotheses(data, resamples=13)
    assert seen[0] == 13
    ls.hypotheses(data)
    assert 2000 in seen


def test_registry_h2_accepts_a_deep_median_exactly_at_the_best_classical_plus_the_margin():
    new = {m: 0.1 for m in ls.NEW_CLASSICAL}
    classical, deep = _registry_inputs(new, forest=0.5, deep={"vae": 0.5 + ls.DEEP_MARGIN})
    assert ls.registry_hypotheses(classical, deep, [])["H2"]["supported"] is True


def test_the_default_bootstrap_is_two_thousand_resamples_with_seed_zero():
    # a small table whose interval changes with the seed and with one more resample
    values = np.random.default_rng(8013).random((8, 2))
    data = _wide_table({f"p{i:02d}": {"a": row[0], "b": row[1]} for i, row in enumerate(values)})
    default = ls.pooled(data)

    rng = np.random.default_rng(0)
    boot = np.stack([np.nanmedian(values[rng.integers(0, 8, 8)], axis=0) for _ in range(2000)])
    low, high = np.nanpercentile(boot, 2.5, axis=0), np.nanpercentile(boot, 97.5, axis=0)
    assert np.allclose(default["lo"], low, rtol=0, atol=1e-12)
    assert np.allclose(default["hi"], high, rtol=0, atol=1e-12)
    other_seed, one_more = ls.pooled(data, seed=1), ls.pooled(data, resamples=2001)
    for other in (other_seed, one_more):
        assert not np.allclose(other[["lo", "hi"]], default[["lo", "hi"]], rtol=0, atol=1e-12)
