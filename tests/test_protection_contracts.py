# ruff: noqa: E501
"""Exact job names, payload refusals, differences and command output of the branch-protection proposal."""

import json
import subprocess

import pytest

from verification import protection as bp


def _workflow(directory, name, text):
    (directory / name).write_text(text)


def test_job_names_follow_each_workflow_in_file_order_with_the_name_line_replacing_the_key(
    tmp_path,
):
    _workflow(
        tmp_path,
        "b.yml",
        'name: b\njobs:\n  first:\n    runs-on: x\n  second:\n    name: "Second job"\n    steps: []\n',
    )
    _workflow(
        tmp_path, "a.yml", "jobs:\n  only:\n    name: 'Quoted'\n  last-job_1:\n    runs-on: y\n"
    )
    assert bp.job_names(tmp_path) == {
        "a.yml": ["Quoted", "last-job_1"],
        "b.yml": ["first", "Second job"],
    }


def test_lines_before_the_jobs_section_and_name_lines_with_other_indentation_are_not_jobs(tmp_path):
    _workflow(
        tmp_path,
        "w.yml",
        "name: top\n  fake:\n    name: nope\njobs:\n  real:\n      name: deeper-indent\n    name:   spaced   \n  other:\n",
    )
    assert bp.job_names(tmp_path) == {"w.yml": ["spaced", "other"]}


def test_a_name_line_before_any_job_is_ignored_and_only_yml_files_are_read(tmp_path):
    _workflow(tmp_path, "w.yml", "jobs:\n    name: early\n  job:\n")
    _workflow(tmp_path, "x.yaml", "jobs:\n  skipped:\n")
    assert bp.job_names(tmp_path) == {"w.yml": ["job"]}


def test_the_repository_workflows_provide_every_required_context_once():
    assert bp.problems_for_contexts() == []
    assert (
        bp.REQUIRED_CONTEXTS == ("test", "faults") and bp.REPO == "theobigand/etl-anomaly-benchmark"
    )


def test_a_missing_and_an_ambiguous_context_are_named_apart(tmp_path):
    _workflow(tmp_path, "a.yml", "jobs:\n  faults:\n  extra:\n")
    _workflow(tmp_path, "b.yml", "jobs:\n  faults:\n")
    assert bp.problems_for_contexts(tmp_path) == [
        "required context 'test': no job provides it",
        "required context 'faults' is provided by more than one job",
    ]


def test_the_proposed_payload_is_exactly_the_documented_one():
    assert bp.proposed_payload() == {
        "required_status_checks": {"strict": True, "contexts": ["test", "faults"]},
        "enforce_admins": False,
        "required_pull_request_reviews": {
            "required_approving_review_count": 0,
            "dismiss_stale_reviews": True,
        },
        "restrictions": None,
        "required_conversation_resolution": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }
    assert bp.validate_payload(bp.proposed_payload()) == []


def _payload(**over):
    payload = bp.proposed_payload()
    payload.update(over)
    return payload


def test_each_missing_top_level_key_is_named_in_order():
    assert bp.validate_payload({}) == [
        "required_status_checks is required",
        "enforce_admins is required",
        "required_pull_request_reviews is required",
        "restrictions is required",
    ]
    only_checks = {"required_status_checks": {"strict": True, "contexts": ["a"]}}
    assert bp.validate_payload(only_checks) == [
        "enforce_admins is required",
        "required_pull_request_reviews is required",
        "restrictions is required",
    ]


@pytest.mark.parametrize("contexts", [[], None, "test", ("a",)])
def test_the_contexts_must_be_a_non_empty_list(contexts):
    checks = {"strict": True, "contexts": contexts}
    assert bp.validate_payload(_payload(required_status_checks=checks)) == [
        "required_status_checks.contexts must be a non-empty list"
    ]


@pytest.mark.parametrize("strict", [None, 1, "yes"])
def test_strict_must_be_a_boolean(strict):
    checks = {"strict": strict, "contexts": ["a"]}
    assert bp.validate_payload(_payload(required_status_checks=checks)) == [
        "required_status_checks.strict must be a boolean"
    ]


def test_both_check_problems_are_reported_together_and_a_non_mapping_is_skipped():
    both = {"strict": "x", "contexts": []}
    assert len(bp.validate_payload(_payload(required_status_checks=both))) == 2
    assert bp.validate_payload(_payload(required_status_checks=None)) == []


@pytest.mark.parametrize("value", [None, 1, "false"])
def test_enforce_admins_must_be_a_boolean_and_null_is_refused(value):
    assert bp.validate_payload(_payload(enforce_admins=value)) == [
        "enforce_admins must be a boolean (null is refused)"
    ]


@pytest.mark.parametrize("count", [-1, 7, "1", None, 1.5])
def test_the_review_count_is_an_integer_from_zero_to_six(count):
    reviews = {"required_approving_review_count": count}
    assert bp.validate_payload(_payload(required_pull_request_reviews=reviews)) == [
        "required_approving_review_count must be between 0 and 6"
    ]


@pytest.mark.parametrize("count", [0, 6, 3])
def test_the_limits_of_the_review_count_are_accepted(count):
    reviews = {"required_approving_review_count": count}
    assert bp.validate_payload(_payload(required_pull_request_reviews=reviews)) == []


def _actual(**over):
    actual = {
        "required_status_checks": {"strict": True, "contexts": ["faults", "test"]},
        "required_pull_request_reviews": {"required_approving_review_count": 0},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
        "required_conversation_resolution": {"enabled": True},
        "enforce_admins": {"enabled": False},
    }
    actual.update(over)
    return actual


def test_the_protection_that_matches_the_proposal_has_no_difference_whatever_the_context_order():
    assert bp.compare(_actual(), bp.proposed_payload()) == []


def test_each_difference_is_named_exactly():
    payload = bp.proposed_payload()
    assert bp.compare(
        _actual(required_status_checks={"strict": False, "contexts": ["test"]}), payload
    ) == [
        "required contexts are ['test'], not ['test', 'faults']",
        "required_status_checks.strict differs",
    ]
    assert bp.compare(
        _actual(required_pull_request_reviews={"required_approving_review_count": 2}), payload
    ) == ["required_approving_review_count is 2"]
    assert bp.compare(_actual(allow_force_pushes={"enabled": True}), payload) == [
        "allow_force_pushes is True, not False"
    ]
    assert bp.compare(_actual(allow_deletions={"enabled": True}), payload) == [
        "allow_deletions is True, not False"
    ]
    assert bp.compare(_actual(required_conversation_resolution={"enabled": False}), payload) == [
        "required_conversation_resolution is False, not True"
    ]
    assert bp.compare(_actual(enforce_admins={"enabled": True}), payload) == [
        "enforce_admins differs"
    ]


def test_a_protection_that_reports_nothing_differs_on_every_point_in_order():
    assert bp.compare({}, bp.proposed_payload()) == [
        "required contexts are None, not ['test', 'faults']",
        "required_status_checks.strict differs",
        "required_approving_review_count is None",
        "allow_force_pushes is None, not False",
        "allow_deletions is None, not False",
        "required_conversation_resolution is None, not True",
        "enforce_admins differs",
    ]


def test_the_print_command_prints_the_payload_indented_by_two(capsys):
    assert bp.main(["print"]) == 0
    assert capsys.readouterr().out == json.dumps(bp.proposed_payload(), indent=2) + "\n"


def test_the_check_command_reads_main_through_the_api_and_reports_each_difference(
    monkeypatch, capsys
):
    seen = {}

    def run(command, **kwargs):
        seen.update(command=command, kwargs=kwargs)
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps(_actual(enforce_admins={"enabled": True})), stderr=""
        )

    monkeypatch.setattr(bp.subprocess, "run", run)
    assert bp.main(["check", "--repo", "o/r"]) == 1
    assert seen["command"] == ["gh", "api", "repos/o/r/branches/main/protection"]
    assert seen["kwargs"] == {"capture_output": True, "text": True, "check": False}
    assert capsys.readouterr().out == "protection: enforce_admins differs\n"


def test_a_matching_protection_passes_and_the_default_repository_is_used(monkeypatch, capsys):
    seen = {}

    def run(command, **kwargs):
        seen["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(_actual()), stderr="")

    monkeypatch.setattr(bp.subprocess, "run", run)
    assert bp.main(["check"]) == 0
    assert seen["command"][2] == f"repos/{bp.REPO}/branches/main/protection"
    assert capsys.readouterr().out == "protection: the applied protection matches the proposal\n"


def test_a_refused_read_is_reported_with_the_trimmed_error(monkeypatch, capsys):
    monkeypatch.setattr(
        bp.subprocess,
        "run",
        lambda command, **kw: subprocess.CompletedProcess(
            command, 1, stdout="", stderr="  HTTP 404  \n"
        ),
    )
    assert bp.main(["check"]) == 1
    assert (
        capsys.readouterr().out == "main is not protected, or the API refused the read: HTTP 404\n"
    )


def test_a_command_is_required_and_the_help_describes_each(capsys):
    with pytest.raises(SystemExit) as stop:
        bp.main([])
    assert stop.value.code == 2
    capsys.readouterr()
    with pytest.raises(SystemExit):
        bp.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "print print the proposed payload" in text
    assert "check read the protection of main and compare it (read-only)" in text
    assert (
        "The proposed protection of ``main``: build it, check it, compare it. Never apply it."
        in text
    )
