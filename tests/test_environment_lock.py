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


# the conda package that provides a PyPI distribution of another name
CONDA_NAME = {"torch": "pytorch"}


def _locked():
    # the macOS lock; the Linux lock is checked on its own below
    text = "".join(
        path.read_text() for path in LOCK.iterdir() if not path.name.startswith("linux-")
    )
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
        key = CONDA_NAME.get(key, key)
        assert key in locked or f"{key}-base" in locked, name


def test_the_lock_matches_the_versions_the_archived_runs_recorded():
    locked = _locked()
    record = json.loads((ROOT / "verification/evidence/run_benchmark_cardio.json").read_text())
    for name, version in record["packages"].items():
        assert locked[name] == version, name


# --- Linux lock by cross-platform resolution (#45) ---

REPORT = {
    "install": [
        {
            "metadata": {"name": "Zeta_Pkg", "version": "2.0"},
            "download_info": {"archive_info": {"hashes": {"sha256": "b" * 64}}},
        },
        {
            "metadata": {"name": "alpha", "version": "1.0"},
            "download_info": {"archive_info": {"hashes": {"sha256": "a" * 64}}},
        },
    ]
}


def test_requirements_cover_the_project_and_every_extra():
    requirements = lock_environment.project_requirements(ROOT / "pyproject.toml")
    names = {re.split(r"[<>=!~ ]", item, maxsplit=1)[0].lower() for item in requirements}
    assert {"pandas", "numpy", "scikit-learn", "pyod", "pytest", "mutmut"} <= names
    assert len(requirements) == len(set(requirements))
    assert not any(req.startswith("torch") for req in requirements)  # the CUDA build is not locked


def test_the_lock_text_pins_every_wheel_by_version_and_hash_in_name_order():
    text = lock_environment.format_linux_lock(REPORT, {"alpha": "1.0"})
    lines = [line for line in text.splitlines() if not line.startswith("#")]
    assert lines == [
        f"alpha==1.0 --hash=sha256:{'a' * 64}",
        f"zeta-pkg==2.0 --hash=sha256:{'b' * 64}",
    ]
    assert "linux" in text and "cp311" in text and "alpha==1.0" in text


def test_a_package_without_a_hash_cannot_be_locked():
    broken = {"install": [{"metadata": {"name": "x", "version": "1"}, "download_info": {}}]}
    import pytest

    with pytest.raises(ValueError, match="hash"):
        lock_environment.format_linux_lock(broken, {})


def test_the_resolver_is_asked_for_linux_wheels_of_the_supported_python(monkeypatch, tmp_path):
    seen = {}

    def fake(command, **kwargs):
        seen["command"] = command
        report = command[command.index("--report") + 1]
        Path(report).write_text(json.dumps(REPORT))

    monkeypatch.setattr(lock_environment.subprocess, "run", fake)
    found = lock_environment.resolve_linux(["alpha"], {"alpha": "1.0"}, tmp_path)
    assert found == REPORT
    command = seen["command"]
    assert "--only-binary=:all:" in command and "--dry-run" in command
    assert command[command.index("--python-version") + 1] == "3.11"
    assert command[command.index("--abi") + 1] == "cp311"
    assert command.count("--platform") == 3
    constraint = Path(command[command.index("-c") + 1]).read_text()
    assert constraint == "alpha==1.0\n"


def test_the_command_writes_the_linux_lock_with_the_result_versions_held_to_the_recorded_ones(
    tmp_path, monkeypatch
):
    seen = {}

    def fake(requirements, held, workdir):
        seen["held"] = held
        return REPORT

    monkeypatch.setattr(lock_environment, "resolve_linux", fake)
    assert lock_environment.main(["--linux", "--output", str(tmp_path)]) == 0
    assert set(seen["held"]) == {"numpy", "pandas", "scikit-learn", "pyod"}
    written = (tmp_path / lock_environment.LINUX_LOCK).read_text()
    assert "alpha==1.0" in written


def test_the_committed_linux_lock_is_hashed_and_agrees_with_the_macos_result_versions():
    from verification import release

    text = (LOCK / lock_environment.LINUX_LOCK).read_text()
    entries = [line for line in text.splitlines() if line and not line.startswith("#")]
    assert entries and all(
        re.fullmatch(r"[\w.-]+==[\w.!+-]+ --hash=sha256:[0-9a-f]{64}", e) for e in entries
    )
    pinned = {line.split("==")[0]: line.split("==")[1].split()[0] for line in entries}
    for package, found in release.locked_versions().items():
        assert pinned[package] == found, package
