"""The paired comparison of the train-only replay with the archived labelled pool."""

import json

import numpy as np
import pytest

from research.pool_train_only_compare import DRAWS, THRESHOLD, compare, main


def _write(directory, problem, source, metrics, errors=None):
    stem = problem.replace(":", "_")
    body = {
        "problem": problem,
        "source": source,
        "metrics": {m: [{"pr_auc": v} for v in values] for m, values in metrics.items()},
        "errors": errors or [],
    }
    (directory / f"{stem}.json").write_text(json.dumps(body))


@pytest.fixture
def archives(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    # a: deltas +0.1 (adbench), 0.0 (uci), -0.2 (uci); each AP is the mean over two seeds
    _write(old, "adbench:p1", "adbench", {"a": [0.2, 0.4], "b": [0.5]})
    _write(new, "adbench:p1", "adbench", {"a": [0.3, 0.5], "b": [0.5]})
    _write(old, "uci:p2", "uci", {"a": [0.5, 0.5], "b": [0.3]})
    _write(new, "uci:p2", "uci", {"a": [0.5], "b": [0.4]})
    _write(old, "uci:p3", "uci", {"a": [0.6], "b": [0.2]})
    _write(new, "uci:p3", "uci", {"a": [0.4], "b": [0.1]}, errors=[{"seed": 1, "reason": "x"}])
    return old, new


def test_each_method_reports_its_paired_differences_over_the_common_problems(archives):
    old, new = archives
    a = compare(new, old)["methods"]["a"]
    assert a["problems"] == 3
    assert a["median_archived_ap"] == pytest.approx(0.5)
    assert a["median_replay_ap"] == pytest.approx(0.4)
    assert a["median_delta"] == pytest.approx(0.0)
    assert a["mean_delta"] == pytest.approx(-0.1 / 3)
    assert a["max_abs_delta"] == pytest.approx(0.2)
    assert a["share_abs_delta_above_threshold"] == pytest.approx(2 / 3)
    assert a["share_unchanged"] == pytest.approx(1 / 3)
    low, high = a["median_delta_ci95"]
    assert -0.2 <= low <= a["median_delta"] <= high <= 0.1


def test_differences_are_split_by_source(archives):
    old, new = archives
    by_source = compare(new, old)["methods"]["a"]["by_source"]
    assert set(by_source) == {"adbench", "uci"}
    assert by_source["adbench"] == {
        "problems": 1,
        "share_unchanged": 0.0,
        "mean_delta": pytest.approx(0.1),
        "mean_abs_delta": pytest.approx(0.1),
    }
    assert by_source["uci"]["problems"] == 2
    assert by_source["uci"]["share_unchanged"] == pytest.approx(0.5)
    assert by_source["uci"]["mean_delta"] == pytest.approx(-0.1)
    assert by_source["uci"]["mean_abs_delta"] == pytest.approx(0.1)


def test_rankings_follow_the_median_ap_and_the_bootstrap_is_reproducible(archives):
    old, new = archives
    result = compare(new, old)
    assert result["ranking_archived"] == ["a", "b"]
    assert result["ranking_replay"] == ["a", "b"]
    assert result["protocol"] == "pool-train-only-replay-v1"
    assert (result["threshold"], result["bootstrap_draws"]) == (THRESHOLD, DRAWS)
    assert compare(new, old) == result


def test_a_ranking_can_change_between_archive_and_replay(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    _write(old, "uci:q", "uci", {"x": [0.1], "y": [0.9], "z": [0.5]})
    _write(new, "uci:q", "uci", {"x": [0.5], "y": [0.1], "z": [0.9]})
    result = compare(new, old)
    assert result["ranking_archived"] == ["y", "z", "x"]  # not the alphabetical order
    assert result["ranking_replay"] == ["z", "x", "y"]


def test_failed_problems_and_replay_errors_are_recorded_not_compared(archives):
    old, new = archives
    (new / "uci_f.json").write_text(json.dumps({"problem": "uci:f", "failed": "boom"}))
    result = compare(new, old)
    assert result["failed_problems"] == {"uci:f": "boom"}
    assert result["problems_with_errors"] == {"uci:p3": [{"seed": 1, "reason": "x"}]}
    assert result["methods"]["a"]["problems"] == 3


def test_a_method_missing_on_either_side_is_not_paired(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    _write(old, "uci:q", "uci", {"x": [0.5], "only_old": [0.5], "empty": []})
    _write(new, "uci:q", "uci", {"x": [0.6], "only_new": [0.5], "empty": [0.1]})
    methods = compare(new, old)["methods"]
    assert set(methods) == {"x"}
    assert set(methods["x"]["by_source"]) == {"uci"}  # a source with no problem is omitted


def test_the_command_writes_the_json_and_a_markdown_row_per_detector(archives, tmp_path):
    old, new = archives
    out = tmp_path / "summary.json"
    assert main(["--new", str(new), "--archive", str(old), "--output", str(out)]) == 0
    assert json.loads(out.read_text())["methods"]["a"]["problems"] == 3
    lines = out.with_suffix(".md").read_text().splitlines()
    assert lines[0].startswith("| detector | n |")
    row = next(line for line in lines if line.startswith("| a |"))
    assert row.startswith("| a | 3 | 0.500 | 0.400 | +0.000 [")
    assert row.endswith("| -0.033 | 0.33 | 0.67 |")


def test_the_interval_is_a_seeded_bootstrap_of_the_median_with_the_documented_percentiles(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    deltas = [round(float(d), 4) for d in np.random.default_rng(5).normal(0.0, 0.1, 60)]
    n = len(deltas)
    for i, delta in enumerate(deltas):
        _write(old, f"uci:{i:02d}", "uci", {"m": [0.5]})
        _write(new, f"uci:{i:02d}", "uci", {"m": [0.5 + delta]})
    observed = np.array(deltas)
    rng = np.random.default_rng(0)
    draws = [np.median(observed[rng.integers(0, n, n)]) for _ in range(DRAWS)]
    low, high = compare(new, old)["methods"]["m"]["median_delta_ci95"]
    assert low == pytest.approx(np.percentile(draws, 2.5), abs=1e-9)
    assert high == pytest.approx(np.percentile(draws, 97.5), abs=1e-9)


def test_a_change_of_exactly_the_threshold_is_not_above_it_and_a_tiny_one_is_not_unchanged(
    tmp_path,
):
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    for name, delta in (("a", THRESHOLD), ("b", 1e-9), ("c", 0.0)):
        _write(old, f"uci:{name}", "uci", {"m": [0.0]})
        _write(new, f"uci:{name}", "uci", {"m": [delta]})
    m = compare(new, old)["methods"]["m"]
    assert m["share_abs_delta_above_threshold"] == 0.0
    assert m["share_unchanged"] == pytest.approx(1 / 3)
    assert m["by_source"]["uci"]["share_unchanged"] == pytest.approx(1 / 3)


def test_the_command_requires_its_inputs_and_defaults_to_the_archived_pool(
    archives, tmp_path, monkeypatch, capsys
):
    old, new = archives
    with pytest.raises(SystemExit):
        main(["--output", str(tmp_path / "x.json")])
    with pytest.raises(SystemExit):
        main(["--new", str(new)])
    with pytest.raises(SystemExit):
        main(["--help"])
    assert "Paired comparison of the train-only replay" in capsys.readouterr().out
    monkeypatch.setattr("research.pool_train_only_compare.ARCHIVE", old)
    out = tmp_path / "default.json"
    assert main(["--new", str(new), "--output", str(out)]) == 0
    assert json.loads(out.read_text())["methods"]["a"]["problems"] == 3


def test_the_files_have_a_fixed_layout(archives, tmp_path):
    old, new = archives
    out = tmp_path / "summary.json"
    main(["--new", str(new), "--archive", str(old), "--output", str(out)])
    result = compare(new, old)
    assert out.read_text() == json.dumps(result, indent=2, sort_keys=True) + "\n"
    markdown = out.with_suffix(".md").read_text().split("\n")
    assert markdown[0] == (
        "| detector | n | AP archived | AP replay | median delta [95% CI] "
        "| mean delta | unchanged | >0.05 |"
    )
    assert markdown[1] == "|---|---|---|---|---|---|---|---|"
    assert len(markdown) == 5 and markdown[-1] == ""
