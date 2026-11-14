# ruff: noqa: E501
"""What the environment lock writes: names, pins, the Linux resolution command, the header and the command."""

import json
import subprocess
from pathlib import Path

import pytest

from verification import lock_environment as le


def test_the_constants_name_the_linux_target():
    assert le.LINUX_LOCK == "linux-x86_64-py311.lock.txt" and le.LINUX_PYTHON == "3.11"
    assert le.LINUX_PLATFORMS == (
        "manylinux2014_x86_64",
        "manylinux_2_17_x86_64",
        "manylinux_2_28_x86_64",
    )
    assert le.TARGET == le.ROOT / "verification" / "environment"


def test_the_conda_lock_is_the_explicit_listing_with_hashes_of_the_named_environment(monkeypatch):
    seen = {}

    def output(command, text=False):
        seen.update(command=command, text=text)
        return "listing"

    monkeypatch.setattr(le.subprocess, "check_output", output)
    assert le.conda_lock("env1") == "listing"
    assert seen == {
        "command": ["conda", "list", "-n", "env1", "--explicit", "--sha256"],
        "text": True,
    }


@pytest.mark.parametrize(
    ("raw", "norm"), [("Foo_Bar", "foo-bar"), ("a_b_C", "a-b-c"), ("x-y", "x-y")]
)
def test_names_are_compared_lower_case_with_dashes(raw, norm):
    assert le._norm(raw) == norm


def test_conda_names_come_from_the_urls_and_a_base_build_counts_for_its_parent():
    explicit = "\n".join(
        [
            "@EXPLICIT",
            "https://c/noarch/Scikit_Learn-1.5.2-py311_0.conda#abc",
            "https://c/linux/python-base-3.11.0-h_0.conda#def",
            "not a url numpy-1-2-3",
        ]
    )
    assert le.conda_names(explicit) == {"scikit-learn", "python-base", "python"}


def _json(items):
    return json.dumps(items)


def test_pypi_packages_are_pinned_by_version_and_those_conda_owns_are_listed_apart(monkeypatch):
    items = [
        {"name": "Zeta", "version": "2", "channel": "pypi"},
        {"name": "alpha", "version": "1", "channel": "pypi"},
        {"name": "numpy", "version": "9", "channel": "pypi"},
        {"name": "etl-benchmark", "version": "0", "channel": "pypi"},
        {"name": "conda-only", "version": "3", "channel": "conda-forge"},
    ]
    seen = {}

    def output(command, text=False):
        seen.update(command=command, text=text)
        return _json(items)

    monkeypatch.setattr(le.subprocess, "check_output", output)
    explicit = "https://c/noarch/numpy-1.0-py_0.conda#a"
    out = le.pip_lock("env1", explicit)
    assert seen == {"command": ["conda", "list", "-n", "env1", "--json"], "text": True}
    assert out == "# installed by conda as well, not pinned here: numpy\nalpha==1\nZeta==2\n"


def test_an_environment_with_no_clash_has_an_empty_skipped_list(monkeypatch):
    monkeypatch.setattr(
        le.subprocess,
        "check_output",
        lambda command, text=False: _json([{"name": "a", "version": "1", "channel": "pypi"}]),
    )
    assert le.pip_lock("e", "") == "# installed by conda as well, not pinned here: \na==1\n"


def test_the_project_requirements_are_the_runtime_ones_then_every_extra_without_torch(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "p"\ndependencies = ["numpy>=1", "torch>=2", "pandas"]\n'
        '[project.optional-dependencies]\nml = ["scikit-learn", "numpy>=1"]\ndeep = ["torchvision", "pyod"]\n'
    )
    assert le.project_requirements(pyproject) == ["numpy>=1", "pandas", "scikit-learn", "pyod"]
    bare = tmp_path / "bare.toml"
    bare.write_text('[project]\nname = "p"\ndependencies = ["a"]\n')
    assert le.project_requirements(bare) == ["a"]


def test_the_repository_requirements_leave_out_every_torch_package():
    found = le.project_requirements()
    assert found and not any(req.startswith("torch") for req in found)


def test_the_linux_resolution_runs_pip_for_the_target_wheels_with_the_held_versions(
    monkeypatch, tmp_path
):
    seen = {}

    def run(command, **kwargs):
        seen.update(command=command, kwargs=kwargs)
        (tmp_path / "report.json").write_text('{"install": []}')
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(le.subprocess, "run", run)
    report = le.resolve_linux(
        ["numpy>=1", "pandas"], {"pandas": "3.0.6", "numpy": "2.0.1"}, tmp_path
    )
    assert report == {"install": []}
    assert (tmp_path / "constraints.txt").read_text() == "numpy==2.0.1\npandas==3.0.6\n"
    expected = [
        "python", "-m", "pip", "install", "--dry-run", "--ignore-installed", "--quiet",
        "--report", str(tmp_path / "report.json"), "--target", str(tmp_path / "target"),
        "--only-binary=:all:", "--python-version", "3.11", "--implementation", "cp", "--abi", "cp311",
        "--platform", "manylinux2014_x86_64", "--platform", "manylinux_2_17_x86_64",
        "--platform", "manylinux_2_28_x86_64",
        "-c", str(tmp_path / "constraints.txt"), "numpy>=1", "pandas",
    ]  # fmt: skip
    assert seen["command"] == expected
    assert seen["kwargs"] == {"check": True, "capture_output": True, "text": True, "timeout": 900}


def _item(name, version, digest="a" * 64):
    return {
        "metadata": {"name": name, "version": version},
        "download_info": {"archive_info": {"hashes": {"sha256": digest}}},
    }


def test_the_linux_lock_has_its_header_and_one_hashed_line_per_wheel_sorted_by_normalised_name():
    report = {"install": [_item("Zeta_pkg", "2", "b" * 64), _item("alpha.pkg", "1")]}
    text = le.format_linux_lock(report, {"numpy": "2.0.1", "pandas": "3.0.6"})
    assert text == (
        "# Linux x86_64, CPython 3.11 (cp311), manylinux wheels only.\n"
        "# Resolved by pip for that platform, not on a Linux machine; install with\n"
        "#   pip install --require-hashes --no-deps -r <this file>\n"
        "# Held to the versions recorded in the macOS lock: numpy==2.0.1, pandas==3.0.6\n"
        f"alpha-pkg==1 --hash=sha256:{'a' * 64}\n"
        f"zeta-pkg==2 --hash=sha256:{'b' * 64}\n"
    )


def test_a_wheel_without_a_hash_is_refused_by_name():
    broken = {"metadata": {"name": "nohash", "version": "1"}, "download_info": {}}
    with pytest.raises(ValueError) as refused:
        le.format_linux_lock({"install": [broken]}, {})
    assert str(refused.value) == "no sha256 hash for nohash"


def test_the_conda_command_writes_the_explicit_lock_and_the_pip_pins_for_this_platform(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(le, "conda_lock", lambda name: f"explicit of {name}")
    monkeypatch.setattr(le, "pip_lock", lambda name, explicit: f"pip of {name} given {explicit}")
    monkeypatch.setattr(le.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(le.platform, "machine", lambda: "arm64")
    out = tmp_path / "new" / "env"
    assert le.main(["--conda-env", "mine", "--output", str(out)]) == 0
    assert (out / "conda-darwin-arm64.explicit.txt").read_text() == "explicit of mine"
    assert (out / "pip-freeze.txt").read_text() == "pip of mine given explicit of mine"
    assert capsys.readouterr().out == f"wrote the lock of mine to {out}\n"


def test_the_default_environment_and_folder_are_the_repository_ones(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(le, "conda_lock", lambda name: seen.setdefault("env", name) and "x")
    monkeypatch.setattr(le, "pip_lock", lambda name, explicit: "y")
    monkeypatch.setattr(Path, "mkdir", lambda self, **kw: seen.setdefault("mkdir", (self, kw)))
    monkeypatch.setattr(
        Path, "write_text", lambda self, text: seen.setdefault("wrote", []).append(self)
    )
    le.main([])
    assert seen["env"] == "etl-benchmark" and seen["mkdir"] == (
        le.TARGET,
        {"parents": True, "exist_ok": True},
    )
    assert all(path.parent == le.TARGET for path in seen["wrote"])


def test_the_linux_command_resolves_with_the_held_versions_and_writes_the_lock(
    monkeypatch, tmp_path, capsys
):
    from verification import release

    seen = {}
    monkeypatch.setattr(release, "locked_versions", lambda: {"numpy": "2"})
    monkeypatch.setattr(le, "project_requirements", lambda: ["numpy"])

    def resolve(requirements, held, workdir):
        seen.update(requirements=requirements, held=held, workdir=Path(workdir).is_dir())
        return {"install": [_item("numpy", "2")]}

    monkeypatch.setattr(le, "resolve_linux", resolve)
    out = tmp_path / "lin"
    assert le.main(["--linux", "--output", str(out)]) == 0
    assert seen == {"requirements": ["numpy"], "held": {"numpy": "2"}, "workdir": True}
    assert (out / le.LINUX_LOCK).read_text().endswith(f"numpy==2 --hash=sha256:{'a' * 64}\n")
    assert capsys.readouterr().out == f"wrote the Linux lock to {out / le.LINUX_LOCK}\n"


def test_the_help_describes_the_lock_and_the_linux_option(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "300")
    with pytest.raises(SystemExit):
        le.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "Write the exact conda and pip package lists of the active environment." in text
    assert "--linux write the Linux lock instead" in text
    assert "--conda-env CONDA_ENV" in text
