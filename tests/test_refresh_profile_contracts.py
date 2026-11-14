# ruff: noqa: E501
"""What the profile refresh copies, derives and writes, and what its command requires."""

import json
import sys

import pytest

from verification import refresh_profile as rp

COVERAGE = {
    "totals": {
        "covered_lines": 90,
        "num_statements": 100,
        "covered_branches": 8,
        "num_branches": 10,
    },
    "files": {
        "b.py": {
            "summary": {
                "covered_lines": 3,
                "num_statements": 4,
                "covered_branches": 1,
                "num_branches": 2,
            }
        },
        "a.py": {
            "summary": {
                "covered_lines": 5,
                "num_statements": 5,
                "covered_branches": 0,
                "num_branches": 0,
            }
        },
    },
}
TEMPLATE = {
    "policy": {"scope": ["x"]},
    "coverage": {"line": {}, "branch": {}, "per_unit": [], "keep": 1},
    "source_revision": "old",
}


def test_the_profile_gets_the_revision_the_time_and_the_totals_and_keeps_everything_else():
    result = rp.build_profile(
        TEMPLATE, COVERAGE, revision="abc", generated_at="2026-01-01T00:00:00+00:00"
    )
    assert (
        result["source_revision"] == "abc" and result["generated_at"] == "2026-01-01T00:00:00+00:00"
    )
    assert result["coverage"]["line"] == {"covered": 90, "coverable": 100}
    assert result["coverage"]["branch"] == {"covered": 8, "coverable": 10}
    assert result["policy"] == {"scope": ["x"]} and result["coverage"]["keep"] == 1


def test_each_unit_is_listed_by_sorted_path_with_its_own_line_and_branch_counts():
    result = rp.build_profile(TEMPLATE, COVERAGE, revision="r", generated_at="t")
    assert result["coverage"]["per_unit"] == [
        {
            "unit": "a.py",
            "line": {"covered": 5, "coverable": 5},
            "branch": {"covered": 0, "coverable": 0},
        },
        {
            "unit": "b.py",
            "line": {"covered": 3, "coverable": 4},
            "branch": {"covered": 1, "coverable": 2},
        },
    ]


def test_the_template_is_not_changed_and_the_result_does_not_share_its_parts():
    before = json.dumps(TEMPLATE, sort_keys=True)
    result = rp.build_profile(TEMPLATE, COVERAGE, revision="r", generated_at="t")
    result["policy"]["scope"].append("y")
    result["coverage"]["keep"] = 2
    assert json.dumps(TEMPLATE, sort_keys=True) == before


def _files(tmp_path):
    coverage, template = tmp_path / "c.json", tmp_path / "t.json"
    coverage.write_text(json.dumps(COVERAGE))
    template.write_text(json.dumps(TEMPLATE))
    return coverage, template


def test_the_command_writes_a_sorted_indented_profile_for_the_head_revision_in_a_new_folder(
    monkeypatch, tmp_path
):
    coverage, template = _files(tmp_path)
    seen = {}

    def output(command, text=False):
        seen.update(command=command, text=text)
        return "deadbeef\n"

    monkeypatch.setattr(rp.subprocess, "check_output", output)
    out = tmp_path / "deep" / "new" / "profile.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["rp", "--coverage", str(coverage), "--template", str(template), "--output", str(out)],
    )
    rp.main()
    assert seen == {"command": ["git", "rev-parse", "HEAD"], "text": True}
    text = out.read_text()
    document = json.loads(text)
    assert text == json.dumps(document, indent=2, sort_keys=True) + "\n"
    assert document["source_revision"] == "deadbeef"
    assert document["generated_at"].endswith("+00:00")
    assert document["generated_at"] > "2020"
    assert document["coverage"]["line"] == {"covered": 90, "coverable": 100}


def test_the_command_may_write_into_an_existing_folder(monkeypatch, tmp_path):
    coverage, template = _files(tmp_path)
    monkeypatch.setattr(rp.subprocess, "check_output", lambda command, text=False: "abc\n")
    out = tmp_path / "profile.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["rp", "--coverage", str(coverage), "--template", str(template), "--output", str(out)],
    )
    rp.main()
    rp.main()
    assert out.is_file()


def test_the_time_is_taken_when_the_command_runs(monkeypatch, tmp_path):
    coverage, template = _files(tmp_path)
    monkeypatch.setattr(rp.subprocess, "check_output", lambda command, text=False: "abc\n")
    out = tmp_path / "p.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["rp", "--coverage", str(coverage), "--template", str(template), "--output", str(out)],
    )

    class Clock:
        @staticmethod
        def now(tz=None):
            Clock.tz = tz
            from datetime import datetime

            return datetime(2026, 5, 6, 7, 8, 9, tzinfo=tz)

    monkeypatch.setattr(rp, "datetime", Clock)
    rp.main()
    assert (
        Clock.tz is rp.UTC
        and json.loads(out.read_text())["generated_at"] == "2026-05-06T07:08:09+00:00"
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["--template", "t", "--output", "o"],
        ["--coverage", "c", "--output", "o"],
        ["--coverage", "c", "--template", "t"],
    ],
)
def test_each_option_is_required(monkeypatch, argv, capsys):
    monkeypatch.setattr(sys, "argv", ["rp", *argv])
    with pytest.raises(SystemExit) as stop:
        rp.main()
    assert stop.value.code == 2


def test_the_help_names_the_purpose_and_the_options(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["rp", "--help"])
    with pytest.raises(SystemExit):
        rp.main()
    text = " ".join(capsys.readouterr().out.split())
    assert "Attach the current coverage and revision to the verification profile." in text
    assert (
        "--coverage COVERAGE" in text
        and "--template TEMPLATE" in text
        and "--output OUTPUT" in text
    )
