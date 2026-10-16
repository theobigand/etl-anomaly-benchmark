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
for last; do :; done
printf 'detector,f1_mean,f1_std,detect_s_mean\\na,0.5,0.1,0.01\\n' > "$last/benchmark_cardio_1.csv"
printf 's' > "$last/split_ids_cardio_1.json.gz"
"""


def _fake_python(tmp_path, body=FAKE):
    path = tmp_path / "fake_python"
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def test_run_cardio_collects_the_table_and_the_split_archive(tmp_path):
    files = reproduce.run_cardio(_fake_python(tmp_path), tmp_path / "out")
    assert files["table"].name == "benchmark_cardio_1.csv"
    assert files["splits"].read_bytes() == b"s"


def test_run_cardio_reports_a_failed_benchmark(tmp_path):
    python = _fake_python(tmp_path, "#!/bin/sh\necho boom >&2\nexit 3\n")
    with pytest.raises(RuntimeError, match="boom"):
        reproduce.run_cardio(python, tmp_path / "out")


class _Recorder:
    def __init__(self):
        self.commands = []

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")


def test_the_environment_is_rebuilt_from_the_recorded_lock(tmp_path, monkeypatch):
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
    monkeypatch.setattr(
        reproduce, "run_cardio", lambda python, directory: _run(tmp_path, directory.name, f1=f1)
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


def test_command_exits_zero_when_every_level_passes_or_is_not_run(tmp_path, monkeypatch):
    _stub_runs(monkeypatch, tmp_path)
    out = tmp_path / "r.json"
    assert reproduce.main(["--levels", "archive", "same_environment", "--output", str(out)]) == 0


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
