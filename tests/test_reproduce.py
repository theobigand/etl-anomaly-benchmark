"""The reproduction report must distinguish numerical, statistical and artifact agreement."""

import json
import stat
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from verification import reproduce

ROOT = Path(__file__).resolve().parents[1]


def _table(path, f1=0.5, f1_std=0.1, detect=0.01, with_timing=True):
    frame = pd.DataFrame(
        {"f1_mean": [f1, 0.2], "f1_std": [f1_std, 0.05]},
        index=pd.Index(["a", "b"], name="detector"),
    )
    if with_timing:
        frame["detect_s_mean"] = [detect, detect]
    frame.to_csv(path)
    return path


def test_identical_tables_are_numerically_reproduced_whatever_the_timing(tmp_path):
    result = reproduce.compare(_table(tmp_path / "a.csv", detect=0.5), _table(tmp_path / "b.csv"))
    assert result == {"kind": "NUMERICAL", "max_abs_diff": 0.0, "timing_max_rel_diff": 49.0}


def test_a_difference_inside_the_reference_spread_is_only_statistical(tmp_path):
    result = reproduce.compare(_table(tmp_path / "a.csv", f1=0.52), _table(tmp_path / "b.csv"))
    assert result["kind"] == "STATISTICAL"
    assert result["max_abs_diff"] == pytest.approx(0.02)


def test_a_difference_beyond_the_spread_is_not_a_reproduction(tmp_path):
    result = reproduce.compare(_table(tmp_path / "a.csv", f1=0.9), _table(tmp_path / "b.csv"))
    assert result["kind"] == "DIFFERENT"


def test_a_different_shape_is_reported_without_a_distance(tmp_path):
    other = _table(tmp_path / "a.csv")
    frame = pd.read_csv(other, index_col=0).drop(index="b")
    frame.to_csv(other)
    result = reproduce.compare(other, _table(tmp_path / "b.csv"))
    assert result == {"kind": "DIFFERENT_SHAPE", "max_abs_diff": None, "timing_max_rel_diff": None}


def test_tables_without_timing_columns_have_no_timing_spread(tmp_path):
    result = reproduce.compare(
        _table(tmp_path / "a.csv", with_timing=False), _table(tmp_path / "b.csv", with_timing=False)
    )
    assert result["timing_max_rel_diff"] is None and result["kind"] == "NUMERICAL"


def _run(tmp_path, name, f1=0.5, splits=b"s"):
    directory = tmp_path / name
    directory.mkdir()
    return {
        "table": _table(directory / "benchmark_cardio_1.csv", f1=f1),
        "splits": _write(directory / "split_ids_cardio_1.json.gz", splits),
    }


def _write(path, content):
    path.write_bytes(content)
    return path


def test_level_fails_when_the_split_archive_differs_even_if_metrics_agree(tmp_path):
    level = reproduce._level(_run(tmp_path, "a"), _run(tmp_path, "b", splits=b"other"))
    assert level["status"] == "FAIL" and level["artifact_identical"] is False
    assert reproduce._level(_run(tmp_path, "c"), _run(tmp_path, "d"))["status"] == "PASS"
    assert reproduce._level(_run(tmp_path, "e", f1=0.9), _run(tmp_path, "f"))["status"] == "FAIL"


FAKE = """#!/bin/sh
# stands in for the interpreter: writes the two files run_benchmark would write
while [ $# -gt 0 ]; do [ "$1" = --results-dir ] && out="$2"; shift; done
printf 'detector,f1_mean,f1_std,detect_s_mean\\na,0.5,0.1,0.01\\n' > "$out/benchmark_cardio_1.csv"
printf 's' > "$out/split_ids_cardio_1.json.gz"
"""


def _fake_python(tmp_path, body=FAKE):
    path = tmp_path / "fake_python"
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def test_run_dataset_collects_the_table_and_the_split_archive(tmp_path):
    files = reproduce.run_dataset(_fake_python(tmp_path), "cardio", tmp_path / "out")
    assert files["table"].name == "benchmark_cardio_1.csv"
    assert files["splits"].read_bytes() == b"s"


def test_run_dataset_reports_a_failed_benchmark(tmp_path):
    python = _fake_python(tmp_path, "#!/bin/sh\necho boom >&2\nexit 3\n")
    with pytest.raises(RuntimeError, match="boom"):
        reproduce.run_dataset(python, "cardio", tmp_path / "out")


class _Recorder:
    def __init__(self):
        self.commands = []

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")


def test_the_environment_is_rebuilt_from_the_recorded_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(reproduce.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(reproduce.platform, "machine", lambda: "arm64")
    recorder = _Recorder()
    monkeypatch.setattr(reproduce.subprocess, "run", recorder)
    python = reproduce.build_environment(tmp_path / "env", ["scikit-learn==1.8.0"])
    assert python == str(tmp_path / "env" / "bin" / "python")
    conda, pip, extra = recorder.commands
    assert conda[:3] == ["conda", "create", "-y"] and conda[-1].endswith(".explicit.txt")
    assert "--no-deps" in pip and pip[-1].endswith("pip-freeze.txt")
    assert extra[-1] == "scikit-learn==1.8.0"
    recorder.commands.clear()
    reproduce.build_environment(tmp_path / "env")
    assert len(recorder.commands) == 2


def _stub_runs(monkeypatch, tmp_path, f1=0.5):
    monkeypatch.setattr(reproduce, "check_input", lambda dataset, *a, **k: None)
    monkeypatch.setattr(
        reproduce,
        "run_dataset",
        lambda python, dataset, directory: _run(tmp_path, directory.name, f1=f1),
    )
    monkeypatch.setattr(
        reproduce,
        "ARCHIVED",
        tmp_path / "archive",
    )
    archive = tmp_path / "archive"
    archive.mkdir()
    _table(archive / "benchmark_cardio.csv")
    _write(archive / "split_ids_cardio.json.gz", b"s")


def test_every_level_is_reported_when_environments_can_be_built(tmp_path, monkeypatch):
    _stub_runs(monkeypatch, tmp_path)
    monkeypatch.setattr(reproduce, "build_environment", lambda prefix, extra=None: "python")
    report = reproduce.reproduce(list(reproduce.LEVELS), tmp_path / "w", "pkg==1")
    assert {k: v["status"] for k, v in report.items()} == {
        "archive": "PASS",
        "same_environment": "PASS",
        "locked_environment": "PASS",
        "version_sensitivity": "MEASURED",
    }
    assert report["version_sensitivity"]["changed"] == "pkg==1"


def test_unavailable_environments_are_not_run_never_passed(tmp_path, monkeypatch):
    _stub_runs(monkeypatch, tmp_path)

    def broken(prefix, extra=None):
        raise subprocess.CalledProcessError(1, "conda")

    monkeypatch.setattr(reproduce, "build_environment", broken)
    report = reproduce.reproduce(
        ["locked_environment", "version_sensitivity"], tmp_path / "w", "pkg==1"
    )
    assert report["locked_environment"]["status"] == "NOT_RUN"
    assert report["version_sensitivity"]["status"] == "NOT_RUN"
    assert "could not be rebuilt" in report["locked_environment"]["reason"]


def test_command_writes_the_report_and_fails_on_a_failed_level(tmp_path, monkeypatch, capsys):
    _stub_runs(monkeypatch, tmp_path, f1=0.9)
    out = tmp_path / "r.json"
    code = reproduce.main(
        ["--levels", "archive", "--workdir", str(tmp_path / "w"), "--output", str(out)]
    )
    assert code == 1
    document = json.loads(out.read_text())
    assert document["levels"]["archive"]["status"] == "FAIL"
    assert len(document["source"]["revision"]) == 40
    assert "archive: FAIL DIFFERENT" in capsys.readouterr().out


def _broken_builds(monkeypatch):
    def broken(prefix, extra=None):
        raise subprocess.CalledProcessError(1, "conda")

    monkeypatch.setattr(reproduce, "build_environment", broken)


def _run_main(tmp_path, *levels):
    out = tmp_path / "r.json"
    code = reproduce.main(
        ["--levels", *levels, "--workdir", str(tmp_path / "w"), "--output", str(out)]
    )
    return code, json.loads(out.read_text())


def test_command_exits_zero_when_every_mandatory_level_passes(tmp_path, monkeypatch):
    _stub_runs(monkeypatch, tmp_path)
    code, document = _run_main(tmp_path, "archive", "same_environment")
    assert code == 0
    assert document["outcome"] == "PASS" and document["reasons"] == []


def test_a_requested_locked_environment_that_was_not_run_is_not_a_pass(
    tmp_path, monkeypatch, capsys
):
    _stub_runs(monkeypatch, tmp_path)
    _broken_builds(monkeypatch)
    code, document = _run_main(tmp_path, "archive", "same_environment", "locked_environment")
    assert code == 1
    assert document["outcome"] == "INCOMPLETE"
    assert document["levels"]["locked_environment"]["status"] == "NOT_RUN"
    assert any("locked_environment" in reason for reason in document["reasons"])
    assert "outcome: INCOMPLETE" in capsys.readouterr().out


def test_every_mandatory_level_passing_including_the_locked_one_exits_zero(tmp_path, monkeypatch):
    _stub_runs(monkeypatch, tmp_path)
    monkeypatch.setattr(reproduce, "build_environment", lambda prefix, extra=None: "python")
    code, document = _run_main(tmp_path, "archive", "same_environment", "locked_environment")
    assert code == 0 and document["outcome"] == "PASS"
    assert document["levels"]["locked_environment"]["required"] is True


def test_the_sensitivity_experiment_never_decides_the_outcome(tmp_path, monkeypatch):
    _stub_runs(monkeypatch, tmp_path)
    _broken_builds(monkeypatch)
    code, document = _run_main(tmp_path, "archive", "version_sensitivity")
    assert code == 0 and document["outcome"] == "PASS"
    level = document["levels"]["version_sensitivity"]
    assert level["status"] == "NOT_RUN" and level["required"] is False


def test_a_sensitivity_run_alone_certifies_nothing(tmp_path, monkeypatch):
    _stub_runs(monkeypatch, tmp_path)
    monkeypatch.setattr(reproduce, "build_environment", lambda prefix, extra=None: "python")
    code, document = _run_main(tmp_path, "version_sensitivity")
    assert code == 1 and document["outcome"] == "INCOMPLETE"
    assert document["levels"]["version_sensitivity"]["status"] == "MEASURED"


def test_a_crashed_benchmark_still_writes_a_failing_report(tmp_path, monkeypatch):
    def crash(python, dataset, directory):
        raise RuntimeError("benchmark failed: boom")

    monkeypatch.setattr(reproduce, "check_input", lambda dataset, *a, **k: None)
    monkeypatch.setattr(reproduce, "run_dataset", crash)
    code, document = _run_main(tmp_path, "archive", "same_environment")
    assert code == 1 and document["outcome"] == "FAIL"
    assert document["levels"]["archive"]["status"] == "FAIL"
    assert "boom" in document["levels"]["archive"]["reason"]
    assert document["levels"]["same_environment"]["status"] == "FAIL"


def test_the_module_prints_usage():
    done = subprocess.run(
        [sys.executable, "-m", "verification.reproduce", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0 and "usage:" in done.stdout


@pytest.mark.real
def test_cardio_is_reproduced_against_the_archive_with_the_local_data(tmp_path):
    report = reproduce.reproduce(["archive", "same_environment"], tmp_path, "")
    assert report["archive"]["kind"] == "NUMERICAL" and report["archive"]["status"] == "PASS"
    assert report["same_environment"]["status"] == "PASS"


def test_a_crash_of_the_second_run_fails_only_that_level(tmp_path, monkeypatch):
    calls = []

    def second_crashes(python, dataset, directory):
        calls.append(directory.name)
        if directory.name == "second":
            raise RuntimeError("benchmark failed: second")
        return _run(tmp_path, directory.name)

    _stub_runs(monkeypatch, tmp_path)
    monkeypatch.setattr(reproduce, "run_dataset", second_crashes)
    code, document = _run_main(tmp_path, "archive", "same_environment")
    assert code == 1 and document["outcome"] == "FAIL"
    assert document["levels"]["archive"]["status"] == "PASS"
    assert "second" in document["levels"]["same_environment"]["reason"]


def test_a_failure_outranks_a_level_that_was_not_run_whatever_the_order():
    not_run = {"status": "NOT_RUN", "reason": "no network"}
    failed = {"status": "FAIL", "kind": "DIFFERENT"}
    passed = {"status": "PASS"}
    report = {"archive": failed, "same_environment": not_run, "locked_environment": not_run}
    outcome, reasons = reproduce.judge(report)
    assert outcome == "FAIL" and len(reasons) == 3
    outcome, _ = reproduce.judge({"archive": not_run, "same_environment": failed})
    assert outcome == "FAIL"
    outcome, reasons = reproduce.judge(
        {"archive": not_run, "same_environment": not_run, "locked_environment": passed}
    )
    assert outcome == "INCOMPLETE" and len(reasons) == 2


# --- other datasets, unavailable inputs and the Linux environment (#45) ---


def _linux(monkeypatch, python=(3, 11)):
    monkeypatch.setattr(reproduce.platform, "system", lambda: "Linux")
    monkeypatch.setattr(reproduce.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(reproduce.sys, "version_info", python + (0,))


def test_every_real_dataset_and_the_synthetic_experiment_can_be_selected():
    assert set(reproduce.TARGETS) == {"cardio", "water_quality", "credit_card", "synthetic"}
    for name, target in reproduce.TARGETS.items():
        assert (reproduce.ARCHIVED / target["reference_table"]).is_file(), name
        assert (reproduce.ARCHIVED / target["record"]).is_file(), name
        if target["reference_splits"]:
            assert (reproduce.ARCHIVED / target["reference_splits"]).is_file(), name


def test_the_replay_uses_the_seeds_and_rows_of_the_archived_run():
    cardio = reproduce.command_for("cardio", "python", Path("out"))
    assert cardio[:3] == ["python", "experiments/run_benchmark.py", "--dataset"]
    assert cardio[cardio.index("--seeds") + 1 :][:5] == ["42", "1", "2", "3", "4"]
    synthetic = reproduce.command_for("synthetic", "python", Path("out"))
    assert synthetic[1] == "experiments/run_synthetic_benchmark.py"
    assert synthetic[synthetic.index("--rows") + 1] == "12000"
    # the figure of the paper is never overwritten by a replay
    assert Path(synthetic[synthetic.index("--figure") + 1]).parent == Path("out")


def test_a_missing_dataset_is_reported_as_unavailable(tmp_path):
    reason = reproduce.check_input("cardio", root=tmp_path)
    assert reason and "not available" in reason


def test_a_dataset_that_differs_from_the_archived_run_is_not_replayed(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "cardio.csv").write_text("a,b\n1,2\n")
    reason = reproduce.check_input("cardio", root=tmp_path)
    assert reason and "differs" in reason


def test_the_exact_archived_dataset_is_accepted(tmp_path):
    import hashlib

    data = tmp_path / "data"
    data.mkdir()
    (data / "cardio.csv").write_text("a,b\n1,2\n")
    digest = hashlib.sha256((data / "cardio.csv").read_bytes()).hexdigest()
    archived = tmp_path / "evidence"
    archived.mkdir()
    (archived / "run_benchmark_cardio.json").write_text(json.dumps({"dataset": {"sha256": digest}}))
    assert reproduce.check_input("cardio", root=tmp_path, archived=archived) is None


def test_the_synthetic_experiment_needs_no_input_file():
    assert reproduce.check_input("synthetic") is None


def test_unavailable_data_marks_every_requested_level_not_run_and_exits_nonzero(
    tmp_path, monkeypatch
):
    _stub_runs(monkeypatch, tmp_path)
    monkeypatch.setattr(
        reproduce, "check_input", lambda dataset, *a, **k: "data/x.csv is not available"
    )
    code, document = _run_main(tmp_path, "archive", "same_environment")
    assert code == 1 and document["outcome"] == "INCOMPLETE"
    assert {v["status"] for v in document["levels"].values()} == {"NOT_RUN"}
    assert "not available" in document["levels"]["archive"]["reason"]


def test_the_report_records_what_an_independent_replay_needs(tmp_path, monkeypatch):
    _stub_runs(monkeypatch, tmp_path)
    code, document = _run_main(tmp_path, "archive")
    assert code == 0
    assert document["dataset"] == "cardio" and document["seeds"] == [42, 1, 2, 3, 4]
    assert document["archived_run"]["source_revision"] and document["archived_run"]["file"]
    assert len(document["archived_run"]["dataset_sha256"]) == 64
    assert "standard deviation" in document["tolerance"]["statistical"]
    assert "never" in document["tolerance"]["timing"]
    assert document["environment"]["platform"] and document["lock"]["strategy"]


def test_other_datasets_get_their_own_default_report_path(tmp_path, monkeypatch):
    _stub_runs(monkeypatch, tmp_path)
    assert reproduce.default_output("cardio").name == "reproducibility.json"
    assert reproduce.default_output("water_quality").name == "reproducibility_water_quality.json"


def test_linux_rebuilds_a_virtual_environment_from_the_hashed_lock(tmp_path, monkeypatch):
    _linux(monkeypatch)
    recorder = _Recorder()
    monkeypatch.setattr(reproduce.subprocess, "run", recorder)
    python = reproduce.build_environment(tmp_path / "env", ["scikit-learn==1.8.0"])
    assert python == str(tmp_path / "env" / "bin" / "python")
    venv, install, extra = recorder.commands
    assert venv[1:4] == ["-m", "venv", str(tmp_path / "env")]
    assert "--require-hashes" in install and "--no-deps" in install
    assert install[-1].endswith("linux-x86_64-py311.lock.txt")
    assert "--require-hashes" not in extra and extra[-1] == "scikit-learn==1.8.0"


def test_the_linux_lock_is_refused_under_another_python(tmp_path, monkeypatch):
    _linux(monkeypatch, python=(3, 12))
    monkeypatch.setattr(reproduce.subprocess, "run", _Recorder())
    with pytest.raises(RuntimeError, match="3.11"):
        reproduce.build_environment(tmp_path / "env")


def test_a_platform_without_a_recorded_lock_cannot_rebuild(tmp_path, monkeypatch):
    monkeypatch.setattr(reproduce.platform, "system", lambda: "Windows")
    monkeypatch.setattr(reproduce.platform, "machine", lambda: "AMD64")
    with pytest.raises(RuntimeError, match="no recorded lock"):
        reproduce.build_environment(tmp_path / "env")
    assert reproduce.lock_strategy() is None


def test_lock_strategy_names_the_file_and_its_hash(monkeypatch):
    _linux(monkeypatch)
    strategy = reproduce.lock_strategy()
    assert strategy["strategy"] == "pip-hashes" and strategy["file"].endswith(".lock.txt")
    assert len(strategy["sha256"]) == 64
    monkeypatch.setattr(reproduce.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(reproduce.platform, "machine", lambda: "arm64")
    assert reproduce.lock_strategy()["strategy"] == "conda-explicit"


def test_an_experiment_without_archived_split_ids_is_judged_on_its_table_alone(tmp_path):
    a, b = _run(tmp_path, "a"), _run(tmp_path, "b")
    level = reproduce._level({**a, "splits": None}, {**b, "splits": None})
    assert level["status"] == "PASS" and level["artifact_identical"] is None
    level = reproduce._level(a, {**b, "splits": None})
    assert level["status"] == "PASS" and level["artifact_identical"] is None


def test_a_replay_that_wrote_no_split_ids_fails_when_the_archive_has_them(tmp_path):
    a, b = _run(tmp_path, "a"), _run(tmp_path, "b")
    level = reproduce._level({**a, "splits": None}, b)
    assert level["status"] == "FAIL" and level["artifact_identical"] is False
