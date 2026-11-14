# ruff: noqa: E501
"""Workload, validation, record and command of the bounded detector cost study."""

import json
import sys

import numpy as np
import pandas as pd
import pytest

from verification import scaling


class Probe:
    """A detector that remembers the frames it was given."""

    name = "probe"
    seen: dict = {}

    def fit(self, frame):
        Probe.seen["fit"] = frame.copy()
        return self

    def predict(self, frame):
        Probe.seen["predict"] = frame.copy()
        return pd.Series(False, index=frame.index)

    def score(self, frame):
        return pd.Series(np.zeros(len(frame)), index=frame.index)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_rows": 19, "n_features": 1, "fit_cap": None},
        {"n_rows": 20, "n_features": 0, "fit_cap": None},
        {"n_rows": 20, "n_features": 1, "fit_cap": 1},
    ],
)
def test_an_unusable_workload_is_refused_with_its_message(kwargs):
    with pytest.raises(ValueError) as refused:
        scaling.run_case(Probe, seed=1, **kwargs)
    assert str(refused.value) == "n_rows, n_features and fit_cap must be positive and usable"


def test_the_smallest_usable_workload_is_accepted():
    row = scaling.run_case(Probe, n_rows=20, n_features=1, fit_cap=2, seed=1)
    assert row["status"] == "PASS" and row["fit_rows"] == 2 and row["eval_rows"] == 20


def test_the_workload_is_the_seeded_normal_table_with_numbered_features_and_a_capped_fit():
    row = scaling.run_case(Probe, n_rows=40, n_features=3, fit_cap=25, seed=7)
    expected = pd.DataFrame(
        np.random.default_rng(7).normal(size=(40, 3)),
        columns=["feature_0", "feature_1", "feature_2"],
    )
    pd.testing.assert_frame_equal(Probe.seen["predict"], expected)
    pd.testing.assert_frame_equal(Probe.seen["fit"], expected.iloc[:25])
    assert row["fit_rows"] == 25 and row["seed"] == 7 and row["n_features"] == 3


@pytest.mark.parametrize(("cap", "fit_rows"), [(None, 40), (100, 40), (40, 40), (39, 39)])
def test_the_fit_uses_the_smaller_of_the_rows_and_the_cap(cap, fit_rows):
    row = scaling.run_case(Probe, n_rows=40, n_features=2, fit_cap=cap, seed=1)
    assert row["fit_rows"] == fit_rows and len(Probe.seen["fit"]) == fit_rows


def test_a_passing_row_has_exactly_its_documented_fields():
    row = scaling.run_case(Probe, n_rows=30, n_features=2, fit_cap=None, seed=3)
    assert list(row) == [
        "status", "reason", "eval_rows", "fit_rows", "n_features", "seed", "fit_s",
        "predict_s", "score_s", "detect_s", "peak_python_bytes",
    ]  # fmt: skip
    assert row["status"] == "PASS" and row["reason"] == ""
    assert row["peak_python_bytes"] > 0


def test_a_failing_row_keeps_the_workload_and_leaves_the_timings_empty():
    def broken():
        raise RuntimeError("boom")

    row = scaling.run_case(broken, n_rows=30, n_features=2, fit_cap=10, seed=3)
    assert row["status"] == "FAIL" and row["reason"] == "RuntimeError: boom"
    assert (row["fit_s"], row["predict_s"], row["score_s"], row["detect_s"]) == (None,) * 4
    assert row["fit_rows"] == 10 and row["seed"] == 3
    assert row["peak_python_bytes"] is not None


def test_memory_tracing_is_stopped_after_each_case_even_after_a_failure():
    import tracemalloc

    def broken():
        raise ValueError("x")

    scaling.run_case(broken, n_rows=30, n_features=1, fit_cap=None, seed=1)
    assert not tracemalloc.is_tracing()
    scaling.run_case(Probe, n_rows=30, n_features=1, fit_cap=None, seed=1)
    assert not tracemalloc.is_tracing()


def test_the_registered_methods_are_the_three_neighbour_and_forest_detectors():
    assert sorted(scaling.METHODS) == ["isolation_forest", "lof", "ocsvm"]
    assert list(scaling.METHODS) == ["isolation_forest", "lof", "ocsvm"]


@pytest.fixture
def study(monkeypatch, tmp_path):
    calls = []

    def run_case(factory, **kwargs):
        calls.append((factory, kwargs))
        status = "FAIL" if kwargs["seed"] == 99 else "PASS"
        return {"status": status, "reason": "", **kwargs}

    monkeypatch.setattr(scaling, "run_case", run_case)

    real = scaling.subprocess.check_output

    def output(command, *args, **kwargs):
        if command[0] != "git":
            return real(command, *args, **kwargs)
        return "abc123\n" if command[1] == "rev-parse" else " M file\n"

    monkeypatch.setattr(scaling.subprocess, "check_output", output)
    monkeypatch.setattr(scaling.provenance, "MEASUREMENT_RECIPE", "recipe")
    monkeypatch.setattr(scaling.provenance, "measurement_fingerprint", lambda: "fingerprint")
    return calls


def _run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["scaling", *argv])
    scaling.main()


def test_the_defaults_are_three_sizes_eight_features_three_repeats_and_every_method(
    monkeypatch, tmp_path, study, capsys
):
    _run(monkeypatch, "--results-dir", str(tmp_path))
    assert len(study) == 3 * 3 * 3
    assert {kw["n_rows"] for _, kw in study} == {100, 300, 900}
    assert {kw["n_features"] for _, kw in study} == {8} and {kw["fit_cap"] for _, kw in study} == {
        None
    }
    assert [kw["seed"] for _, kw in study[:3]] == [42, 43, 44]
    assert [f for f, _ in study[::9]] == [scaling.METHODS[m] for m in scaling.METHODS]
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "isolation_forest rows=100 repeat=0: PASS" and len(lines) == 27


def test_the_loops_run_method_then_size_then_repeat_with_seeds_from_the_repeat(
    monkeypatch, tmp_path, study, capsys
):
    _run(monkeypatch, "--sizes", "50", "60", "--repeats", "2", "--methods", "lof", "ocsvm",
         "--features", "5", "--fit-cap", "30", "--results-dir", str(tmp_path))  # fmt: skip
    order = [(f, kw["n_rows"], kw["seed"]) for f, kw in study]
    lof, ocsvm = scaling.METHODS["lof"], scaling.METHODS["ocsvm"]
    assert order == [
        (lof, 50, 42), (lof, 50, 43), (lof, 60, 42), (lof, 60, 43),
        (ocsvm, 50, 42), (ocsvm, 50, 43), (ocsvm, 60, 42), (ocsvm, 60, 43),
    ]  # fmt: skip
    assert all(kw["n_features"] == 5 and kw["fit_cap"] == 30 for _, kw in study)
    assert capsys.readouterr().out.splitlines()[3] == "lof rows=60 repeat=1: PASS"


@pytest.mark.parametrize(
    "argv",
    [
        ["--repeats", "0"],
        ["--repeats", "11"],
        ["--sizes", "19"],
        ["--sizes", "5001"],
        ["--sizes", "100", "19"],
    ],
)
def test_out_of_range_repeats_and_sizes_are_refused_by_the_parser(
    monkeypatch, tmp_path, study, argv, capsys
):
    with pytest.raises(SystemExit) as stop:
        _run(monkeypatch, *argv, "--results-dir", str(tmp_path))
    assert stop.value.code == 2 and study == []
    assert "use 1–10 repeats and dataset sizes between 20 and 5000" in capsys.readouterr().err


def test_the_limits_themselves_are_accepted(monkeypatch, tmp_path, study):
    _run(
        monkeypatch,
        "--repeats",
        "10",
        "--sizes",
        "20",
        "5000",
        "--methods",
        "lof",
        "--results-dir",
        str(tmp_path),
    )
    assert len(study) == 20 and {kw["n_rows"] for _, kw in study} == {20, 5000}
    study.clear()
    _run(
        monkeypatch,
        "--repeats",
        "1",
        "--sizes",
        "20",
        "--methods",
        "lof",
        "--results-dir",
        str(tmp_path),
    )
    assert len(study) == 1


def test_the_table_and_the_record_are_written_with_their_provenance(monkeypatch, tmp_path, study):
    out = tmp_path / "new" / "dir"
    _run(
        monkeypatch,
        "--sizes",
        "40",
        "--repeats",
        "2",
        "--methods",
        "lof",
        "--results-dir",
        str(out),
    )
    table = pd.read_csv(out / "scaling.csv")
    assert list(table["method"]) == ["lof", "lof"] and list(table["repeat"]) == [0, 1]
    assert list(table.columns)[:3] == ["method", "repeat", "status"]
    text = (out / "scaling.json").read_text()
    record = json.loads(text)
    assert text == json.dumps(record, indent=2, sort_keys=True) + "\n"
    assert record["source_revision"] == "abc123" and record["worktree_dirty"] is True
    assert (
        record["measurement_recipe"] == "recipe"
        and record["measurement_fingerprint"] == "fingerprint"
    )
    assert record["sizes"] == [40] and record["n_features"] == 8 and record["repeats"] == 2
    assert record["fit_cap"] is None and record["methods"] == ["lof"]
    assert record["captured_at"].endswith("+00:00") and record["logical_cpus"] >= 1
    assert set(record["packages"]) == {"numpy", "pandas", "scikit-learn", "pyod"}
    assert record["data_loading"] == "generated in memory; CSV reading and deduplication excluded"
    assert (
        record["memory_measure"]
        == "tracemalloc peak Python allocations; native allocations excluded"
    )
    assert (
        record["timing_measure"]
        == "fit_s + predict_s + score_s inside pipeline.detect; data generation excluded"
    )
    assert [r["repeat"] for r in record["results"]] == [0, 1] and record["results"][0][
        "method"
    ] == "lof"


def test_a_clean_worktree_is_recorded_as_clean(monkeypatch, tmp_path, study):
    real = scaling.subprocess.check_output

    def clean(command, *args, **kwargs):
        if command[0] != "git":
            return real(command, *args, **kwargs)
        return "abc\n" if command[1] == "rev-parse" else ""

    monkeypatch.setattr(scaling.subprocess, "check_output", clean)
    _run(
        monkeypatch,
        "--sizes",
        "40",
        "--repeats",
        "1",
        "--methods",
        "lof",
        "--results-dir",
        str(tmp_path),
    )
    assert json.loads((tmp_path / "scaling.json").read_text())["worktree_dirty"] is False


def test_a_failed_case_is_kept_in_the_files_and_stops_the_command_with_a_message(
    monkeypatch, tmp_path, study
):
    monkeypatch.setattr(scaling, "METHODS", {"lof": scaling.METHODS["lof"]})
    real = scaling.run_case

    def failing(factory, **kwargs):
        row = real(factory, **kwargs)
        return {**row, "status": "FAIL"}

    monkeypatch.setattr(scaling, "run_case", failing)
    with pytest.raises(SystemExit) as stop:
        _run(monkeypatch, "--sizes", "40", "--repeats", "1", "--results-dir", str(tmp_path))
    assert str(stop.value) == "one or more scaling cases failed; inspect scaling.json"
    assert (tmp_path / "scaling.json").is_file() and (tmp_path / "scaling.csv").is_file()
    assert json.loads((tmp_path / "scaling.json").read_text())["results"][0]["status"] == "FAIL"


def test_the_help_describes_the_study(monkeypatch, capsys):
    with pytest.raises(SystemExit):
        _run(monkeypatch, "--help")
    assert "Bounded detector cost study; never used as a FAST timing threshold." in " ".join(
        capsys.readouterr().out.split()
    )


def test_an_unknown_method_is_refused_by_the_parser_and_the_choices_are_listed(
    monkeypatch, tmp_path, study, capsys
):
    with pytest.raises(SystemExit) as stop:
        _run(monkeypatch, "--methods", "nope", "--results-dir", str(tmp_path))
    assert stop.value.code == 2 and study == []
    assert (
        "invalid choice: 'nope' (choose from 'isolation_forest', 'lof', 'ocsvm')"
        in capsys.readouterr().err
    )


def test_the_parser_message_for_a_bad_range_is_exact(monkeypatch, tmp_path, study, capsys):
    with pytest.raises(SystemExit):
        _run(monkeypatch, "--repeats", "0", "--results-dir", str(tmp_path))
    assert (
        capsys.readouterr()
        .err.rstrip()
        .endswith("error: use 1–10 repeats and dataset sizes between 20 and 5000")
    )


def test_without_a_results_folder_the_files_go_to_verification_evidence_under_the_working_folder(
    monkeypatch, tmp_path, study
):
    monkeypatch.chdir(tmp_path)
    _run(monkeypatch, "--sizes", "40", "--repeats", "1", "--methods", "lof")
    assert (tmp_path / "verification" / "evidence" / "scaling.json").is_file()
    assert (tmp_path / "verification" / "evidence" / "scaling.csv").is_file()


def test_the_record_has_exactly_its_documented_keys_and_reads_the_machine(
    monkeypatch, tmp_path, study
):
    import platform

    _run(
        monkeypatch,
        "--sizes",
        "40",
        "--repeats",
        "1",
        "--methods",
        "lof",
        "--results-dir",
        str(tmp_path),
    )
    record = json.loads((tmp_path / "scaling.json").read_text())
    assert set(record) == {
        "captured_at", "source_revision", "worktree_dirty", "measurement_recipe",
        "measurement_fingerprint", "platform", "processor", "logical_cpus", "python", "packages",
        "sizes", "n_features", "repeats", "fit_cap", "methods", "data_loading", "memory_measure",
        "timing_measure", "results",
    }  # fmt: skip
    assert record["platform"] == platform.platform() and record["processor"] == platform.processor()
    assert record["python"] == sys.version.split()[0]


def test_git_is_asked_for_the_head_and_the_porcelain_status_as_text(monkeypatch, tmp_path, study):
    seen = []
    real = scaling.subprocess.check_output

    def spy(command, *args, **kwargs):
        if command[0] != "git":
            return real(command, *args, **kwargs)
        seen.append((command, kwargs))
        return "x\n"

    monkeypatch.setattr(scaling.subprocess, "check_output", spy)
    _run(
        monkeypatch,
        "--sizes",
        "40",
        "--repeats",
        "1",
        "--methods",
        "lof",
        "--results-dir",
        str(tmp_path),
    )
    assert seen == [
        (["git", "rev-parse", "HEAD"], {"text": True}),
        (["git", "status", "--porcelain"], {"text": True}),
    ]
