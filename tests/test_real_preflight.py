"""The REAL preflight is read-only: it judges the machine and never runs the benchmark."""

import hashlib
import json
import runpy
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from verification import real_preflight as pf

ROOT = Path(__file__).resolve().parents[1]


def _status(results, name):
    return next(r.status for r in results if r.name == name)


def test_a_python_minor_other_than_the_locked_one_fails():
    assert pf.check_python((3, 11, 9), "3.11").status == "PASS"
    assert pf.check_python((3, 12, 1), "3.11").status == "FAIL"


def test_only_linux_x86_64_matches_the_hash_locked_environment():
    assert pf.check_platform("Linux", "x86_64").status == "PASS"
    other = pf.check_platform("Darwin", "arm64")
    assert other.status == "WARN" and "statistical" in other.detail


def test_dependencies_must_match_the_lock_and_missing_ones_fail():
    locked = {"numpy": "2.0.0", "pandas": "2.2.0"}
    assert pf.check_dependencies({"numpy": "2.0.0", "pandas": "2.2.0"}, locked).status == "PASS"
    drift = pf.check_dependencies({"numpy": "2.0.1", "pandas": None}, locked)
    assert drift.status == "FAIL"
    assert "numpy 2.0.1 != 2.0.0" in drift.detail and "pandas not installed" in drift.detail


def _dataset(tmp_path, name="cardio", content=b"a,b\n1,2\n", mode=0o600):
    path = tmp_path / f"{name}.csv"
    path.write_bytes(content)
    path.chmod(mode)
    return path


def test_datasets_are_verified_by_hash_without_printing_their_content(tmp_path):
    path = _dataset(tmp_path, content=b"secret,rows\n1,2\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    ok = pf.check_datasets({"cardio": path}, {"cardio": {"sha256": digest}})
    assert [r.status for r in ok] == ["PASS", "PASS"]
    assert all("secret" not in r.detail for r in ok)
    bad = pf.check_datasets({"cardio": path}, {"cardio": {"sha256": "0" * 64}})
    assert bad[0].status == "FAIL" and "differs" in bad[0].detail


def test_an_absent_dataset_fails_without_a_hash_attempt(tmp_path):
    result = pf.check_datasets({"cardio": tmp_path / "gone.csv"}, {"cardio": {"sha256": "0" * 64}})
    assert [r.status for r in result] == ["FAIL"]
    assert "absent" in result[0].detail


@pytest.mark.parametrize(
    ("mode", "expected"), [(0o600, "PASS"), (0o644, "WARN"), (0o666, "FAIL"), (0o660, "FAIL")]
)
def test_dataset_permissions(tmp_path, mode, expected):
    path = _dataset(tmp_path, mode=mode)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    results = pf.check_datasets({"cardio": path}, {"cardio": {"sha256": digest}})
    assert _status(results, "dataset permissions cardio") == expected


def test_resources_below_the_minimum_fail():
    big = pf.Resources(free_bytes=50 * 2**30, cpus=8, ram_bytes=32 * 2**30)
    assert pf.check_resources(big).status == "PASS"
    small = pf.Resources(free_bytes=2**30, cpus=1, ram_bytes=2**30)
    failed = pf.check_resources(small)
    assert failed.status == "FAIL"
    assert "disk" in failed.detail and "cpu" in failed.detail and "memory" in failed.detail


def test_measured_resources_are_positive(tmp_path):
    measured = pf.measure_resources(tmp_path)
    assert measured.free_bytes > 0 and measured.cpus >= 1 and measured.ram_bytes > 0


def test_revision_must_be_the_approved_one_on_a_clean_tree():
    sha = "a" * 40
    assert pf.check_revision(sha, sha, False).status == "PASS"
    assert pf.check_revision(sha, "b" * 40, False).status == "FAIL"
    assert pf.check_revision(sha, sha, True).status == "FAIL"
    assert pf.check_revision(sha, "", False).status == "FAIL"


def test_the_real_bundle_carries_only_the_two_reports():
    assert pf.check_bundle_allowlist().status == "PASS"
    assert pf.check_bundle_allowlist({"real": ("data/cardio.csv",)}).status == "FAIL"
    assert pf.check_bundle_allowlist({"real": ("x.json", "y.gz")}).status == "FAIL"
    assert pf.check_bundle_allowlist({}).status == "FAIL"


def test_the_real_job_uploads_nothing_but_the_evidence_bundle():
    assert (
        pf.check_upload_paths((ROOT / ".github/workflows/verify-release.yml").read_text()).status
        == "PASS"
    )
    leaking = (
        "  real:\n    steps:\n      - uses: actions/upload-artifact@v4\n"
        "        with:\n          path: data/\n  release:\n"
    )
    assert pf.check_upload_paths(leaking).status == "FAIL"
    assert pf.check_upload_paths("jobs:\n").status == "FAIL"


def test_the_runner_must_be_self_hosted_when_inside_one():
    assert pf.check_runner({"RUNNER_ENVIRONMENT": "self-hosted"}).status == "PASS"
    assert pf.check_runner({"RUNNER_ENVIRONMENT": "github-hosted"}).status == "FAIL"
    assert pf.check_runner({}).status == "WARN"


def test_registration_needs_an_online_self_hosted_runner_with_the_label():
    listing = {
        "runners": [
            {
                "name": "r",
                "status": "online",
                "labels": [{"name": "self-hosted"}, {"name": "thesis-real"}],
            }
        ]
    }
    assert pf.check_registration("thesis-real", listing).status == "PASS"
    offline = {
        "runners": [
            {
                "name": "r",
                "status": "offline",
                "labels": [{"name": "self-hosted"}, {"name": "thesis-real"}],
            }
        ]
    }
    assert pf.check_registration("thesis-real", offline).status == "FAIL"
    assert pf.check_registration("thesis-real", {"runners": []}).status == "FAIL"
    assert pf.check_registration("thesis-real", None).status == "WARN"


def test_fetching_the_registrations_reports_an_api_refusal_as_unknown(monkeypatch):
    refused = SimpleNamespace(returncode=1, stdout="", stderr="HTTP 403")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: refused)
    assert pf.fetch_registrations("o/r") is None
    served = SimpleNamespace(returncode=0, stdout=json.dumps({"runners": []}), stderr="")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: served)
    assert pf.fetch_registrations("o/r") == {"runners": []}


def test_git_state_is_read_with_read_only_commands(monkeypatch):
    calls = []

    def fake(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(
            returncode=0, stdout="abc\n" if "rev-parse" in command else "", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake)
    assert pf.git_state(ROOT) == ("abc", False)
    assert all(c[1] in {"rev-parse", "status"} for c in calls)


def test_the_cli_exits_nonzero_on_any_failure_and_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        pf, "run_checks", lambda args: [pf.Result("a", "PASS", "ok"), pf.Result("b", "FAIL", "no")]
    )
    assert pf.main([]) == 1
    out = capsys.readouterr().out
    assert "FAIL b" in out and "preflight: FAIL" in out
    monkeypatch.setattr(pf, "run_checks", lambda args: [pf.Result("a", "WARN", "meh")])
    assert pf.main([]) == 0
    assert "preflight: PASS (1 warning)" in capsys.readouterr().out


def test_the_checks_assemble_from_the_real_machine(monkeypatch):
    args = pf.parse_args(["--expect-sha", "a" * 40])
    monkeypatch.setattr(pf, "git_state", lambda root: ("a" * 40, False))
    results = pf.run_checks(args)
    names = [r.name for r in results]
    for needle in (
        "python",
        "platform",
        "dependencies",
        "resources",
        "revision",
        "bundle allowlist",
        "upload paths",
        "runner",
    ):
        assert needle in names
    assert _status(results, "revision") == "PASS"
    with_label = pf.parse_args(["--check-registration", "thesis-real"])
    monkeypatch.setattr(pf, "fetch_registrations", lambda repo: {"runners": []})
    assert _status(pf.run_checks(with_label), "registration thesis-real") == "FAIL"


def test_a_missing_package_is_reported_as_not_installed():
    found = pf._installed(["numpy", "no-such-distribution-xyz"])
    assert found["numpy"] and found["no-such-distribution-xyz"] is None


def test_the_module_runs_as_a_script(monkeypatch):
    monkeypatch.setattr("sys.argv", ["real_preflight", "--help"])
    with pytest.raises(SystemExit) as stop:
        runpy.run_path(str(Path(pf.__file__)), run_name="__main__")
    assert stop.value.code == 0
