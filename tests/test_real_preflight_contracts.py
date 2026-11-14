# ruff: noqa: E501
"""Exact verdicts, details, defaults and wiring of the read-only REAL preflight."""

import json
import subprocess
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace

import pytest

from verification import real_preflight as pf

GIB = 2**30


def test_the_python_check_names_both_versions_exactly():
    assert pf.check_python((3, 11, 9), "3.11") == pf.Result(
        "python", "PASS", "3.11 (locked environment uses 3.11)"
    )
    assert pf.check_python((3, 10, 0), "3.11") == pf.Result(
        "python", "FAIL", "3.10 (locked environment uses 3.11)"
    )


def test_the_platform_check_states_its_reason_for_each_outcome():
    assert pf.check_platform("Linux", "x86_64") == pf.Result(
        "platform", "PASS", "Linux x86_64, the platform of the hash-locked environment"
    )
    for system, machine in (("Linux", "aarch64"), ("Darwin", "x86_64")):
        assert pf.check_platform(system, machine) == pf.Result(
            "platform",
            "WARN",
            f"{system} {machine}: only a statistical match with the archive can be expected",
        )


def test_dependency_problems_are_listed_in_lock_order_and_a_pass_lists_the_pins():
    locked = {"a": "1", "b": "2"}
    assert pf.check_dependencies({"a": "1", "b": "2"}, locked) == pf.Result(
        "dependencies", "PASS", "a 1, b 2"
    )
    assert pf.check_dependencies({"a": "9"}, locked) == pf.Result(
        "dependencies", "FAIL", "a 9 != 1; b not installed"
    )
    assert pf.check_dependencies({"a": "1", "b": "2", "c": "3"}, {}) == pf.Result(
        "dependencies", "PASS", ""
    )


def test_the_lock_pins_are_read_from_pinned_lines_and_comments_are_skipped(tmp_path):
    lock = tmp_path / "lock.txt"
    lock.write_text(
        "# numpy==9.9\nnumpy==2.0.1 \\\n    --hash=sha256:aa\npandas == 3.0.6 ; x\nplain line\n\nscipy==1.2\n"
    )
    pins = pf.linux_lock_pins(lock)
    assert pins["numpy"] == "2.0.1" and pins["scipy"] == "1.2"
    assert pins["pandas"] == "3.0.6" and "# numpy" not in pins and "plain line" not in pins


def test_the_environment_lock_lists_at_most_ten_problems_and_counts_a_pass():
    pins = {f"p{i}": "1" for i in range(12)}
    failed = pf.check_lock({}, pins)
    assert failed.name == "environment lock" and failed.status == "FAIL"
    assert failed.detail == "; ".join(f"p{i} not installed" for i in range(10))
    assert pf.check_lock({"x": "1"}, {"x": "2"}).detail == "x 1 != 2"
    assert pf.check_lock({"x": "1", "y": "2"}, {"x": "1", "y": "2"}) == pf.Result(
        "environment lock", "PASS", "all 2 pinned packages match"
    )


def test_the_lock_is_judged_on_linux_only():
    assert pf.check_lock_for("Darwin", {}, {"x": "1"}) == pf.Result(
        "environment lock", "WARN", "the hash-pinned lock describes Linux only"
    )
    assert pf.check_lock_for("Linux", {"x": "1"}, {"x": "1"}).status == "PASS"
    assert pf.check_lock_for("Linux", {}, {"x": "1"}).status == "FAIL"


@pytest.mark.parametrize(
    ("mode", "status", "detail"),
    [
        (0o600, "PASS", "mode 600"),
        (0o640, "WARN", "mode 640 is readable beyond the owner"),
        (0o604, "WARN", "mode 604 is readable beyond the owner"),
        (0o620, "FAIL", "mode 620 is writable beyond the owner"),
        (0o602, "FAIL", "mode 602 is writable beyond the owner"),
        (0o666, "FAIL", "mode 666 is writable beyond the owner"),
    ],
)
def test_dataset_permissions_judge_write_before_read_beyond_the_owner(
    tmp_path, mode, status, detail
):
    path = tmp_path / "d.csv"
    path.write_bytes(b"x")
    path.chmod(mode)
    import hashlib

    digest = hashlib.sha256(b"x").hexdigest()
    results = pf.check_datasets({"d": path}, {"d": {"sha256": digest}})
    assert results[0] == pf.Result("dataset d", "PASS", "sha256 matches the reference")
    assert results[1] == pf.Result("dataset permissions d", status, detail)


def test_a_dataset_that_differs_or_is_absent_is_named_exactly(tmp_path):
    path = tmp_path / "d.csv"
    path.write_bytes(b"x")
    path.chmod(0o600)
    differs = pf.check_datasets({"d": path}, {"d": {"sha256": "0" * 64}})
    assert differs[0] == pf.Result("dataset d", "FAIL", "sha256 differs from the reference")
    absent = pf.check_datasets({"d": tmp_path / "none"}, {"d": {"sha256": "0" * 64}})
    assert absent == [pf.Result("dataset d", "FAIL", "file absent")]


def test_resources_are_measured_from_the_machine(tmp_path):
    found = pf.measure_resources(tmp_path)
    assert found.free_bytes > 0 and found.cpus >= 1 and found.ram_bytes > 0
    import os
    import shutil

    assert found.free_bytes <= shutil.disk_usage(tmp_path).total
    assert found.cpus == (os.cpu_count() or 1)


@pytest.mark.parametrize(
    ("free", "cpus", "ram", "detail"),
    [
        (5 * GIB, 2, 8 * GIB, "5 GiB free, 2 cpu, 8 GiB memory"),
        (5 * GIB - 1, 2, 8 * GIB, "disk 4 GiB free, 5 needed"),
        (5 * GIB, 1, 8 * GIB, "cpu 1, 2 needed"),
        (5 * GIB, 2, 8 * GIB - 1, "memory 7 GiB, 8 needed"),
        (0, 1, 0, "disk 0 GiB free, 5 needed; cpu 1, 2 needed; memory 0 GiB, 8 needed"),
    ],
)
def test_each_resource_limit_is_inclusive_and_reported_alone_or_together(free, cpus, ram, detail):
    result = pf.check_resources(pf.Resources(free, cpus, ram))
    assert result.name == "resources" and result.detail == detail
    assert result.status == ("PASS" if detail.startswith("5 GiB") else "FAIL")


def _repo(tmp_path):
    for command in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", *command], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "f").write_text("1")
    subprocess.run(["git", "add", "f"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "c"], cwd=tmp_path, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_the_git_state_is_the_head_commit_and_whether_the_worktree_is_dirty(tmp_path):
    head = _repo(tmp_path)
    assert pf.git_state(tmp_path) == (head, False)
    (tmp_path / "untracked").write_text("x")
    assert pf.git_state(tmp_path) == (head, True)
    with pytest.raises(subprocess.CalledProcessError):
        pf.git_state(tmp_path / "missing" if (tmp_path / "missing").exists() else Path("/"))


def test_the_revision_check_orders_its_refusals_and_shortens_the_hashes():
    head = "a" * 40
    assert pf.check_revision(head, "", False) == pf.Result(
        "revision", "FAIL", "no approved revision given (--expect-sha)"
    )
    assert pf.check_revision(head, "b" * 40, False) == pf.Result(
        "revision", "FAIL", f"HEAD {'a' * 12} is not the approved {'b' * 12}"
    )
    assert pf.check_revision(head, head, True) == pf.Result(
        "revision", "FAIL", "the worktree is not clean"
    )
    assert pf.check_revision(head, head, False) == pf.Result(
        "revision", "PASS", f"{'a' * 12}, clean worktree"
    )


def test_the_bundle_allowlists_must_match_each_real_bundle_exactly():
    good = {"real": pf.REAL_REPORTS, "real-hosted": pf.HOSTED_REPORTS}
    assert pf.check_bundle_allowlist(good) == pf.Result(
        "bundle allowlist", "PASS", "the real bundles allow their JSON reports only"
    )
    wide = {"real": [*pf.REAL_REPORTS, "x"], "real-hosted": pf.HOSTED_REPORTS}
    assert (
        pf.check_bundle_allowlist(wide).detail
        == f"the real bundle allows {sorted([*pf.REAL_REPORTS, 'x'])}"
    )
    narrow = {"real": pf.REAL_REPORTS, "real-hosted": []}
    assert pf.check_bundle_allowlist(narrow).detail == "the real-hosted bundle allows []"
    assert pf.check_bundle_allowlist({}).status == "FAIL"
    assert pf.check_bundle_allowlist().status == "PASS"


WORKFLOW = """name: w
jobs:
  real:
    steps:
      - uses: actions/upload-artifact@v4
        with:
          path: evidence-real.tgz
  real-hosted:
    steps:
      - uses: actions/upload-artifact@v4
        with:
          path: evidence-real-hosted.tgz
  other:
    steps:
      - with:
          path: anything
"""


def test_each_real_job_must_upload_exactly_its_own_bundle():
    assert pf.check_upload_paths(WORKFLOW) == pf.Result(
        "upload paths", "PASS", "the real jobs upload their evidence bundle only"
    )
    assert pf.check_upload_paths(WORKFLOW.replace("evidence-real.tgz", "x.tgz")).detail == (
        "the real job uploads ['x.tgz']"
    )
    assert (
        pf.check_upload_paths(
            WORKFLOW.replace("path: evidence-real-hosted.tgz", "path: a\n          path: b")
        ).detail
        == "the real-hosted job uploads ['a', 'b']"
    )
    missing = WORKFLOW.replace("  real-hosted:", "  hosted-gone:")
    assert pf.check_upload_paths(missing) == pf.Result(
        "upload paths", "FAIL", "no real-hosted job in the workflow"
    )
    assert pf.check_upload_paths("jobs:\n  x:\n") == pf.Result(
        "upload paths", "FAIL", "no real job in the workflow"
    )


def test_the_job_text_stops_at_the_next_job_and_is_none_when_absent():
    text = pf._job_text(WORKFLOW, "real")
    assert "evidence-real.tgz" in text and "real-hosted" not in text
    assert "anything" in pf._job_text(WORKFLOW, "other")
    assert pf._job_text(WORKFLOW, "nothing") is None


def test_the_runner_check_distinguishes_outside_hosted_and_self_hosted():
    assert pf.check_runner({}) == pf.Result(
        "runner", "WARN", "not inside a GitHub Actions job (advisory)"
    )
    assert pf.check_runner({"RUNNER_ENVIRONMENT": "github-hosted"}) == pf.Result(
        "runner", "FAIL", "RUNNER_ENVIRONMENT is github-hosted, not self-hosted"
    )
    assert pf.check_runner({"RUNNER_ENVIRONMENT": "self-hosted"}) == pf.Result(
        "runner", "PASS", "self-hosted"
    )


def _runner(status, *labels):
    return {"status": status, "labels": [{"name": n} for n in labels]}


def test_a_registration_needs_an_online_self_hosted_runner_with_the_label():
    ok = pf.check_registration("lab", {"runners": [_runner("online", "self-hosted", "lab", "x")]})
    assert ok == pf.Result(
        "registration lab", "PASS", "an online self-hosted runner carries the label"
    )
    for runner in (
        _runner("offline", "self-hosted", "lab"),
        _runner("online", "lab"),
        _runner("online", "self-hosted"),
    ):
        refused = pf.check_registration("lab", {"runners": [runner]})
        assert refused == pf.Result(
            "registration lab", "FAIL", "no online self-hosted runner carries the label"
        )
    assert pf.check_registration("lab", {}).status == "FAIL"
    later = {"runners": [_runner("offline", "lab"), _runner("online", "self-hosted", "lab")]}
    assert pf.check_registration("lab", later).status == "PASS"
    assert pf.check_registration("lab", None) == pf.Result(
        "registration lab", "WARN", "the runner list could not be read; registration is unknown"
    )


def test_the_runner_list_is_read_through_the_github_api_and_a_refusal_is_unknown(monkeypatch):
    seen = {}

    def run(command, **kwargs):
        seen.update(command=command, kwargs=kwargs)
        return subprocess.CompletedProcess(command, seen.get("code", 0), '{"runners": []}', "")

    monkeypatch.setattr(pf.subprocess, "run", run)
    assert pf.fetch_registrations("o/r") == {"runners": []}
    assert seen["command"] == ["gh", "api", "repos/o/r/actions/runners"]
    assert seen["kwargs"] == {"capture_output": True, "text": True, "check": False}
    seen["code"] = 1
    assert pf.fetch_registrations("o/r") is None


def test_installed_versions_are_read_and_a_missing_package_is_none(monkeypatch):
    assert pf._installed(["numpy"])["numpy"] == metadata.version("numpy")
    assert pf._installed(["no-such-package-xyz"]) == {"no-such-package-xyz": None}
    assert list(pf._installed(["pandas", "numpy"])) == ["pandas", "numpy"]


def test_the_arguments_default_to_no_approval_no_registration_and_the_repository():
    args = pf.parse_args([])
    assert args.expect_sha == "" and args.check_registration is None
    assert args.install_only is False and args.hosted_download is False
    assert args.repo == pf.REPO == "theobigand/etl-anomaly-benchmark"
    args = pf.parse_args(
        ["--expect-sha", "abc", "--check-registration", "lab", "--install-only",
         "--hosted-download", "--repo", "o/r"]
    )  # fmt: skip
    assert (args.expect_sha, args.check_registration, args.repo) == ("abc", "lab", "o/r")
    assert args.install_only is True and args.hosted_download is True


def test_the_help_describes_each_option(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "300")
    with pytest.raises(SystemExit):
        pf.parse_args(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "commit the operator approved" in text
    assert "read the runner list" in text
    assert "install check on a machine without datasets (dataset, runner checks skipped)" in text
    assert "the datasets were just downloaded on a GitHub-hosted runner (no runner check)" in text
    assert "Read-only preflight of the machine that will run the REAL profile." in text


def _wire(monkeypatch, tmp_path, *, system="Linux", dirty=False):
    calls = []
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"datasets": {"cardio": {"sha256": "0" * 64}}}))
    workflow = tmp_path / "wf.yml"
    workflow.write_text(WORKFLOW)
    monkeypatch.setattr(pf, "MANIFEST", manifest)
    monkeypatch.setattr(pf, "WORKFLOW", workflow)
    monkeypatch.setattr(pf.release, "locked_versions", lambda: {"numpy": "1"})
    monkeypatch.setattr(pf, "linux_lock_pins", lambda: {"scipy": "2"})
    monkeypatch.setattr(pf, "git_state", lambda root: ("h" * 40, dirty))
    monkeypatch.setattr(pf.platform, "system", lambda: system)
    monkeypatch.setattr(pf.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(
        pf, "_installed", lambda names: calls.append(tuple(names)) or dict.fromkeys(names, "1")
    )
    monkeypatch.setattr(pf, "measure_resources", lambda where: pf.Resources(9 * GIB, 4, 16 * GIB))
    monkeypatch.setattr(
        pf, "check_bundle_allowlist", lambda: pf.Result("bundle allowlist", "PASS", "b")
    )
    import etl_benchmark.datasets as datasets

    csv = tmp_path / "cardio.csv"
    csv.write_bytes(b"x")
    csv.chmod(0o600)
    monkeypatch.setattr(
        datasets,
        "DATASETS",
        {"cardio": SimpleNamespace(csv=csv), "other": SimpleNamespace(csv=csv)},
    )
    return calls


def _args(**over):
    base = {"expect_sha": "", "check_registration": None, "install_only": False,
            "hosted_download": False, "repo": "o/r"}  # fmt: skip
    return SimpleNamespace(**{**base, **over})


def test_the_full_run_checks_in_a_fixed_order_and_only_the_datasets_of_the_manifest(
    monkeypatch, tmp_path
):
    calls = _wire(monkeypatch, tmp_path)
    monkeypatch.delenv("RUNNER_ENVIRONMENT", raising=False)
    names = [r.name for r in pf.run_checks(_args(expect_sha="h" * 40))]
    assert names == [
        "python", "platform", "dependencies", "environment lock", "dataset cardio",
        "dataset permissions cardio", "resources", "revision", "bundle allowlist",
        "upload paths", "runner",
    ]  # fmt: skip
    assert calls == [("numpy",), ("scipy",)]


def test_install_only_skips_datasets_resources_and_runner_with_their_reasons(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path)
    results = pf.run_checks(_args(install_only=True, expect_sha="h" * 40))
    by_name = {r.name: r for r in results}
    assert by_name["datasets"] == pf.Result(
        "datasets", "SKIP", "--install-only: no dataset is expected here"
    )
    assert by_name["resources"] == pf.Result(
        "resources", "SKIP", "--install-only: sized for the full datasets"
    )
    assert by_name["runner"] == pf.Result(
        "runner", "SKIP", "hosted run: no private runner is involved"
    )
    assert "dataset cardio" not in by_name


def test_a_hosted_download_skips_only_the_runner_and_registration_is_read_when_asked(
    monkeypatch, tmp_path
):
    _wire(monkeypatch, tmp_path)
    monkeypatch.setattr(pf, "fetch_registrations", lambda repo: {"seen": repo})
    monkeypatch.setattr(
        pf,
        "check_registration",
        lambda label, listing: pf.Result(f"registration {label}", "PASS", str(listing)),
    )
    results = pf.run_checks(_args(hosted_download=True, check_registration="lab", repo="o/r"))
    by_name = {r.name: r for r in results}
    assert by_name["runner"].status == "SKIP" and "dataset cardio" in by_name
    assert results[-1] == pf.Result("registration lab", "PASS", "{'seen': 'o/r'}")


def test_the_revision_and_dirty_state_reach_the_revision_check(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path, dirty=True)
    results = {r.name: r for r in pf.run_checks(_args(expect_sha="h" * 40))}
    assert results["revision"].detail == "the worktree is not clean"
    results = {r.name: r for r in pf.run_checks(_args(expect_sha="z" * 40))}
    assert results["revision"].detail.startswith(f"HEAD {'h' * 12} is not the approved")


def test_the_platform_name_reaches_the_lock_check(monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path, system="Darwin")
    results = {r.name: r for r in pf.run_checks(_args(install_only=True))}
    assert results["environment lock"].status == "WARN"


def test_main_prints_one_line_per_result_and_a_summary_with_the_exit_status(capsys):
    results = [pf.Result("a", "PASS", "fine"), pf.Result("b", "WARN", "hm")]
    assert pf.main([], checks=lambda args: results) == 0
    assert capsys.readouterr().out == "PASS a: fine\nWARN b: hm\npreflight: PASS (1 warning)\n"
    assert pf.main([], checks=lambda args: results[:1]) == 0
    assert capsys.readouterr().out.endswith("preflight: PASS (0 warnings)\n")
    two = [pf.Result("a", "WARN", "x"), pf.Result("b", "WARN", "y")]
    pf.main([], checks=lambda args: two)
    assert capsys.readouterr().out.endswith("preflight: PASS (2 warnings)\n")
    failing = [
        pf.Result("a", "FAIL", "bad"),
        pf.Result("b", "FAIL", "worse"),
        pf.Result("c", "SKIP", "s"),
    ]
    assert pf.main([], checks=lambda args: failing) == 1
    assert capsys.readouterr().out == (
        "FAIL a: bad\nFAIL b: worse\nSKIP c: s\npreflight: FAIL (2 failed)\n"
    )


def test_main_hands_its_parsed_arguments_to_the_checks(capsys):
    seen = []
    pf.main(["--expect-sha", "abc"], checks=lambda args: seen.append(args.expect_sha) or [])
    assert seen == ["abc"]


def test_the_repository_constants_name_the_real_files():
    assert pf.PYTHON_MINOR == "3.11" and pf.MIN_DISK == 5 * GIB and pf.MIN_CPUS == 2
    assert pf.MIN_RAM == 8 * GIB
    assert pf.LINUX_LOCK.name == "linux-x86_64-py311.lock.txt"
    assert pf.WORKFLOW == pf.ROOT / ".github" / "workflows" / "verify-release.yml"
    assert pf.MANIFEST == pf.ROOT / "verification" / "evidence" / "manifest.json"
    assert pf.LINUX_LOCK.is_file() and pf.WORKFLOW.is_file() and pf.MANIFEST.is_file()
