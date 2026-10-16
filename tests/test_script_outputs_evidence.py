"""Exact content of the evidence files written by provenance.py and verification_report.py."""

import gzip
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timedelta
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as installed_version
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import provenance  # noqa: E402
import verification_report  # noqa: E402

from etl_benchmark.split import stratified_split  # noqa: E402


def _message(text):
    return f"^{re.escape(text)}$"


# --- provenance -------------------------------------------------------------


def _git_repo(root):
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "mod.py").write_text("VALUE = 1\n")
    (root / "experiments").mkdir()
    (root / "experiments" / "run.py").write_text("pass\n")
    (root / "environment.yml").write_text("name: env\n")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "p"\nversion = "1"\ndependencies = ["pandas"]\n\n[tool.x]\ny = 1\n'
    )
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org"}
    env |= {
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.org",
        "PATH": "/usr/bin:/bin",
    }
    for command in (["init", "-q"], ["add", "."], ["commit", "-q", "-m", "first"]):
        subprocess.run(["git", *command], cwd=root, env=env, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_source_fingerprint_is_the_documented_recipe(tmp_path, monkeypatch):
    monkeypatch.setattr(provenance, "ROOT", tmp_path)
    _git_repo(tmp_path)
    digest = hashlib.sha256()
    for name in ("environment.yml", "experiments/run.py", "src/pkg/mod.py"):
        digest.update(name.encode())
        digest.update((tmp_path / name).read_bytes())
    project = {"name": "p", "version": "1", "dependencies": ["pandas"]}
    digest.update(json.dumps(project, sort_keys=True).encode())
    assert provenance._source_fingerprint() == digest.hexdigest()


def test_record_lists_every_field_of_the_run(tmp_path, monkeypatch):
    revision = _git_repo(tmp_path)
    monkeypatch.setattr(provenance, "ROOT", tmp_path)
    data = tmp_path / "data.csv"
    data.write_text("x,label\n1,0\n2,1\n")
    output = tmp_path / "out" / "more" / "run.json"
    provenance.write_record(
        output,
        experiment="benchmark",
        seeds=[4, 5],
        dataset="toy",
        data_path=data,
        settings={"split": [0.7, 0.15, 0.15]},
        outputs=["metrics.csv"],
    )
    text = output.read_text()
    record = json.loads(text)
    assert text == json.dumps(record, indent=2, sort_keys=True) + "\n"
    assert datetime.fromisoformat(record.pop("captured_at")).utcoffset() == timedelta(0)
    assert record == {
        "schema_version": 1,
        "experiment": "benchmark",
        "source_revision": revision,
        "source_fingerprint": provenance._source_fingerprint(),
        "fingerprint_recipe": 2,
        "scientific_fingerprint": provenance.scientific_fingerprint(),
        "worktree_dirty": True,  # data.csv and out/ are not committed
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": {
            name: installed_version(name)
            for name in ("numpy", "pandas", "scikit-learn", "pyod", "great-expectations")
        },
        "environment_lock": provenance._environment_lock(),
        "dataset": {
            "identity": "toy",
            "path": str(data),
            "sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
            "bytes": data.stat().st_size,
        },
        "seeds": [4, 5],
        "settings": {"split": [0.7, 0.15, 0.15]},
        "outputs": ["metrics.csv"],
    }


def test_record_reports_a_clean_worktree_as_clean(tmp_path, monkeypatch):
    _git_repo(tmp_path)
    monkeypatch.setattr(provenance, "ROOT", tmp_path)
    output = tmp_path.parent / f"{tmp_path.name}_run.json"
    provenance.write_record(
        output, experiment="e", seeds=[], dataset="d", data_path=None, settings={}, outputs=[]
    )
    assert json.loads(output.read_text())["worktree_dirty"] is False


def test_record_marks_any_missing_package_as_none(tmp_path, monkeypatch):
    _git_repo(tmp_path)
    monkeypatch.setattr(provenance, "ROOT", tmp_path)

    def missing(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr(provenance, "version", missing)
    output = tmp_path.parent / f"{tmp_path.name}_missing.json"
    provenance.write_record(
        output, experiment="e", seeds=[], dataset="d", data_path=None, settings={}, outputs=[]
    )
    packages = json.loads(output.read_text())["packages"]
    assert packages == dict.fromkeys(
        ("numpy", "pandas", "scikit-learn", "pyod", "great-expectations")
    )


def test_split_archive_is_deterministic_compact_json_with_integer_positions(tmp_path):
    frame = pd.DataFrame({"is_anomaly": [0] * 80 + [1] * 20})
    path = tmp_path / "deeper" / "still" / "splits.json.gz"
    provenance.write_split_ids(path, frame, "is_anomaly", [3, 4], (0.7, 0.15, 0.15), fit_sample=10)
    raw = path.read_bytes()
    assert raw[4:8] == bytes(4)  # gzip header carries no timestamp
    document = gzip.decompress(raw).decode()
    record = json.loads(document)
    assert document == json.dumps(record, sort_keys=True, separators=(",", ":"))
    assert record["schema_version"] == 1
    assert record["row_count"] == 100
    for seed in (3, 4):
        parts = record["seeds"][str(seed)]
        assert all(isinstance(i, int) for key in parts for i in parts[key])
        train = stratified_split(
            frame.assign(_split_row_id=range(100)), "is_anomaly", (0.7, 0.15, 0.15), seed
        )[0]
        expected = train["_split_row_id"].sample(n=10, random_state=seed).tolist()
        assert parts["fit"] == expected


def test_split_archive_accepts_a_one_row_fit_and_skips_a_full_size_one(tmp_path):
    frame = pd.DataFrame({"is_anomaly": [0] * 80 + [1] * 20})
    ratios = (0.7, 0.15, 0.15)
    one = tmp_path / "one.json.gz"
    provenance.write_split_ids(one, frame, "is_anomaly", [3], ratios, fit_sample=1)
    assert len(provenance.read_split_ids(one)["seeds"]["3"]["fit"]) == 1
    train_size = len(provenance.read_split_ids(one)["seeds"]["3"]["train"])
    full = tmp_path / "full.json.gz"
    provenance.write_split_ids(full, frame, "is_anomaly", [3], ratios, fit_sample=train_size)
    assert "fit" not in provenance.read_split_ids(full)["seeds"]["3"]


def test_split_archive_messages_name_the_failed_check(tmp_path):
    frame = pd.DataFrame({"is_anomaly": [0] * 80 + [1] * 20})
    ratios = (0.7, 0.15, 0.15)
    with pytest.raises(ValueError, match=_message("fit_sample must be positive")):
        provenance.write_split_ids(tmp_path / "a.gz", frame, "is_anomaly", [3], ratios, 0)
    with pytest.raises(
        ValueError, match=_message("reserved split marker '_split_row_id' is already present")
    ):
        provenance.write_split_ids(
            tmp_path / "b.gz", frame.assign(_split_row_id=1), "is_anomaly", [3], ratios
        )


def test_file_hash_covers_files_larger_than_one_read(tmp_path):
    big = tmp_path / "big.bin"
    big.write_bytes(bytes(range(256)) * 9000)  # about 2.3 MB
    assert provenance._hash_file(big) == hashlib.sha256(big.read_bytes()).hexdigest()


# --- verification_report ----------------------------------------------------


def _evidence(
    tmp_path, suites='<testsuite tests="3" failures="0" errors="0" skipped="0"/>', **totals
):
    summary = {"covered_lines": 8, "num_statements": 8, "covered_branches": 4, "num_branches": 4}
    summary.update(totals)
    coverage = tmp_path / "coverage.json"
    coverage.write_text(
        json.dumps(
            {
                "totals": summary,
                "files": {
                    "src/a.py": {
                        "summary": {
                            "covered_lines": 5,
                            "num_statements": 6,
                            "covered_branches": 1,
                            "num_branches": 2,
                        }
                    }
                },
            }
        )
    )
    junit = tmp_path / "junit.xml"
    junit.write_text(suites)
    return coverage, junit


class _Git:
    def __init__(self, revision="abc123\n", status=" M file.py\n"):
        self.calls = []
        self.answers = {"rev-parse": revision, "status": status}

    def __call__(self, command, **options):
        self.calls.append((command, options))
        return self.answers[command[1]]


def test_report_lists_every_field(tmp_path, monkeypatch):
    git = _Git()
    monkeypatch.setattr(verification_report.subprocess, "check_output", git)
    versions = {"pytest": "1", "pytest-cov": "2", "numpy": "3", "pandas": "4", "scikit-learn": "5"}

    def fake_version(name):
        if name not in versions:
            raise PackageNotFoundError(name)
        return versions[name]

    monkeypatch.setattr(verification_report, "version", fake_version)
    report = verification_report.build_report(*_evidence(tmp_path))
    assert datetime.fromisoformat(report.pop("captured_at")).utcoffset() == timedelta(0)
    assert report == {
        "schema_version": 1,
        "status": "PASS",
        "source_revision": "abc123",
        "dirty": True,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "packages": {**versions, "pyod": None},
        "tests": {"total": 3, "failures": 0, "errors": 0, "skipped": 0},
        "coverage": {
            "line": {"covered": 8, "coverable": 8},
            "branch": {"covered": 4, "coverable": 4},
            "per_file": {
                "src/a.py": {
                    "line": {"covered": 5, "coverable": 6},
                    "branch": {"covered": 1, "coverable": 2},
                }
            },
        },
    }
    assert git.calls == [
        (["git", "rev-parse", "HEAD"], {"text": True}),
        (["git", "status", "--porcelain"], {"text": True}),
    ]


def test_report_reads_a_clean_worktree_and_files_without_a_per_file_section(tmp_path, monkeypatch):
    monkeypatch.setattr(verification_report.subprocess, "check_output", _Git(status="\n"))
    coverage, junit = _evidence(tmp_path)
    data = json.loads(coverage.read_text())
    del data["files"]
    coverage.write_text(json.dumps(data))
    report = verification_report.build_report(coverage, junit)
    assert report["dirty"] is False
    assert report["coverage"]["per_file"] == {}


def test_report_sums_suites_and_defaults_absent_counts_to_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(verification_report.subprocess, "check_output", _Git())
    suites = (
        '<testsuites><testsuite tests="2" failures="1"/>'
        '<testsuite tests="3" errors="1" skipped="2"/></testsuites>'
    )
    report = verification_report.build_report(*_evidence(tmp_path, suites))
    assert report["tests"] == {"total": 5, "failures": 1, "errors": 1, "skipped": 2}
    assert report["status"] == "FAIL"
    single = verification_report.build_report(*_evidence(tmp_path, '<testsuite tests="3"/>'))
    assert single["tests"] == {"total": 3, "failures": 0, "errors": 0, "skipped": 0}


def test_report_messages_name_the_failed_check(tmp_path):
    coverage, junit = _evidence(tmp_path)
    for lone in (coverage, junit):
        other = junit if lone is coverage else coverage
        other.rename(tmp_path / "renamed")
        with pytest.raises(ValueError, match=_message("missing coverage or test evidence")):
            verification_report.build_report(coverage, junit)
        (tmp_path / "renamed").rename(other)
    empty = _evidence(tmp_path, '<testsuite tests="0"/>')
    with pytest.raises(ValueError, match=_message("zero tests executed")):
        verification_report.build_report(*empty)
    for zeroed in (
        {"num_statements": 0, "covered_lines": 0},
        {"num_branches": 0, "covered_branches": 0},
    ):
        with pytest.raises(
            ValueError, match=_message("zero instrumented production lines or branches")
        ):
            verification_report.build_report(*_evidence(tmp_path, **zeroed))
    coverage, junit = _evidence(tmp_path)
    coverage.write_text("{}")
    with pytest.raises(ValueError, match=_message("malformed verification evidence")):
        verification_report.build_report(coverage, junit)


def test_command_writes_a_stable_report_and_prints_the_verdict(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(verification_report.subprocess, "check_output", _Git())
    coverage, junit = _evidence(tmp_path)
    output = tmp_path / "deep" / "er" / "still" / "report.json"
    argv = ["verification_report", "--coverage", str(coverage), "--junit", str(junit)]
    monkeypatch.setattr(sys, "argv", [*argv, "--output", str(output)])
    assert verification_report.main() == 0
    assert capsys.readouterr().out == "verification: PASS (3 tests)\n"
    text = output.read_text()
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
    junit.write_text('<testsuite tests="1" failures="1"/>')
    assert verification_report.main() == 1
    assert capsys.readouterr().out == "verification: FAIL (1 tests)\n"


def test_command_help_shows_its_purpose(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["verification_report", "--help"])
    with pytest.raises(SystemExit):
        verification_report.main()
    assert "Machine-readable verification evidence" in capsys.readouterr().out


def test_report_command_requires_all_three_paths(monkeypatch, capsys):
    full = ["--coverage", "c.json", "--junit", "j.xml", "--output", "o.json"]
    for drop in range(0, 6, 2):
        argv = ["verification_report", *full[:drop], *full[drop + 2 :]]
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as stopped:
            verification_report.main()
        assert stopped.value.code == 2
        assert "required" in capsys.readouterr().err


def test_record_asks_git_for_the_revision_and_the_status_of_the_repository(tmp_path, monkeypatch):
    calls = []

    def fake_git(command, **options):
        calls.append((command, options))
        return {"rev-parse": "feedface\n", "status": ""}[command[1]]

    monkeypatch.setattr(provenance.subprocess, "check_output", fake_git)
    output = tmp_path / "a" / "b" / "run.json"
    provenance.write_record(
        output, experiment="e", seeds=[], dataset="d", data_path=None, settings={}, outputs=[]
    )
    assert calls == [
        (["git", "rev-parse", "HEAD"], {"cwd": provenance.ROOT, "text": True}),
        (["git", "status", "--porcelain"], {"cwd": provenance.ROOT, "text": True}),
    ]
    record = json.loads(output.read_text())
    assert record["source_revision"] == "feedface"
    assert record["worktree_dirty"] is False


def test_fingerprint_reads_the_project_table_from_pyproject(tmp_path, monkeypatch):
    _git_repo(tmp_path)
    monkeypatch.setattr(provenance, "ROOT", tmp_path)
    opened = []
    original = Path.read_text

    def spy(self, *args, **kwargs):
        opened.append(str(self))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", spy)
    provenance._source_fingerprint()
    assert str(tmp_path / "pyproject.toml") in opened
