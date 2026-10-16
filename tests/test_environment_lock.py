"""The recorded lock must describe the environment the results depend on."""

import json
import re
import sys
import tomllib
from pathlib import Path

from verification import lock_environment

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "verification" / "environment"
EXPLICIT = (
    "# header\n@EXPLICIT\n"
    "https://conda.anaconda.org/conda-forge/noarch/foo_bar-1.0-pyh_0.conda#abc\n"
    "https://conda.anaconda.org/conda-forge/osx-arm64/matplotlib-base-3.1-py311_1.conda#def\n"
)
ITEMS = [
    {"name": "foo-bar", "version": "1.0", "channel": "conda-forge"},
    {"name": "Foo_Bar", "version": "0.9", "channel": "pypi"},
    {"name": "matplotlib", "version": "3.0", "channel": "pypi"},
    {"name": "pyod", "version": "3.6", "channel": "pypi"},
    {"name": "etl-benchmark", "version": "0.1", "channel": "pypi"},
]


def _canned(monkeypatch, explicit=EXPLICIT):
    def fake(command, **kwargs):
        return json.dumps(ITEMS) if "--json" in command else explicit

    monkeypatch.setattr(lock_environment.subprocess, "check_output", fake)


def test_conda_names_include_the_parent_of_a_base_build():
    assert lock_environment.conda_names(EXPLICIT) == {"foo-bar", "matplotlib-base", "matplotlib"}


def test_pip_lock_leaves_out_conda_owned_names_and_the_project_itself(monkeypatch):
    _canned(monkeypatch)
    text = lock_environment.pip_lock("env", EXPLICIT)
    assert text == (
        "# installed by conda as well, not pinned here: Foo_Bar, matplotlib\npyod==3.6\n"
    )


def test_command_writes_both_lock_files(tmp_path, monkeypatch):
    _canned(monkeypatch)
    assert lock_environment.main(["--conda-env", "env", "--output", str(tmp_path)]) == 0
    names = sorted(path.name for path in tmp_path.iterdir())
    assert names[1] == "pip-freeze.txt" and names[0].startswith("conda-")
    assert (tmp_path / names[0]).read_text() == EXPLICIT


def test_the_module_prints_usage():
    import subprocess

    done = subprocess.run(
        [sys.executable, "-m", "verification.lock_environment", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0 and "usage:" in done.stdout


def _locked():
    text = "".join(path.read_text() for path in LOCK.iterdir())
    return {
        re.sub(r"[-_.]+", "-", name.lower()): version
        for name, version in re.findall(r"/([A-Za-z0-9_.+-]+?)-(\d[^-]*)-[^/]*\.conda#", text)
    } | {
        re.sub(r"[-_.]+", "-", line.split("==")[0].lower()): line.split("==")[1]
        for line in text.splitlines()
        if "==" in line
    }


def test_the_lock_pins_every_direct_dependency_and_python():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    direct = list(project["dependencies"]) + project["optional-dependencies"]["dev"]
    direct += project["optional-dependencies"]["deep"]
    locked = _locked()
    assert locked["python"].startswith("3.11.")
    for requirement in direct:
        name = re.split(r"[<>=!~ ]", requirement)[0]
        key = re.sub(r"[-_.]+", "-", name.lower())
        assert key in locked or f"{key}-base" in locked, name


def test_the_lock_matches_the_versions_the_archived_runs_recorded():
    locked = _locked()
    record = json.loads((ROOT / "verification/evidence/run_benchmark_cardio.json").read_text())
    for name, version in record["packages"].items():
        assert locked[name] == version, name
