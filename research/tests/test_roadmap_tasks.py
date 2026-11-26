"""Roadmap task validation: dynamic, cross-reference aware, no fixed total (#200)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import roadmap_tasks as rt  # noqa: E402


def _roadmap(tmp_path, files, task_range="T001–T003"):
    (tmp_path / "tracking.json").write_text(
        json.dumps({"task_range": task_range}, ensure_ascii=False), encoding="utf-8"
    )
    for name, lines in files.items():
        (tmp_path / name).write_text("# Part\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path


BASE = {
    "01-a.md": ["- [ ] T001 First.", "- [x] T002 Second."],
    "02-b.md": ["- [ ] T003 Third."],
}


def test_a_valid_roadmap_passes_and_reports_its_dynamic_count(tmp_path):
    result = rt.validate(_roadmap(tmp_path, BASE))
    assert result.errors == [] and result.count == 3


def test_extra_tasks_and_a_longer_sequence_need_no_validator_change(tmp_path):
    files = {**BASE, "03-c.md": [f"- [ ] T{n:03d} Added." for n in range(4, 40)]}
    files["04-d.md"] = ["- [ ] T1000 Far future."] + []
    result = rt.validate(_roadmap(tmp_path, files))
    assert result.count == 40 and result.errors == [
        "T1000: the identifiers above T003 must be contiguous; T040 to T999 are missing"
    ]
    files["04-d.md"] = [f"- [ ] T{n:03d} More." for n in range(40, 1001)]
    assert rt.validate(_roadmap(tmp_path, files)).errors == []


def test_a_promoted_cross_reference_to_a_defined_task_is_legitimate(tmp_path):
    files = {**BASE, "03-c.md": ["- [ ] T002 (promoted, see 01) Second."]}
    files["01-a.md"] = ["- [ ] T001 First.", "- [ ] T002 Second."]
    result = rt.validate(_roadmap(tmp_path, files))
    assert result.errors == [] and result.count == 3


def test_a_reference_with_a_different_state_is_refused(tmp_path):
    files = {**BASE, "03-c.md": ["- [ ] T002 (promoted, see 01) Second."]}
    errors = rt.validate(_roadmap(tmp_path, files)).errors
    assert errors == ["T002: 03-c.md is unchecked but its definition in 01-a.md is checked"]


def test_a_reference_to_a_file_that_does_not_define_the_task_is_refused(tmp_path):
    files = {**BASE, "03-c.md": ["- [ ] T003 (promoted, see 01) Third."]}
    errors = rt.validate(_roadmap(tmp_path, files)).errors
    assert errors == ["T003: 03-c.md points to file 01, which does not define it"]


def test_two_canonical_definitions_conflict(tmp_path):
    files = {**BASE, "03-c.md": ["- [ ] T002 Second again."]}
    assert rt.validate(_roadmap(tmp_path, files)).errors == ["T002: defined in 01-a.md and 03-c.md"]
    files = {"01-a.md": ["- [ ] T001 One.", "- [ ] T001 Two.", "- [ ] T002 x."]}
    files["02-b.md"] = BASE["02-b.md"]
    (tmp_path / "03-c.md").unlink()
    assert rt.validate(_roadmap(tmp_path, files)).errors == ["T001: defined in 01-a.md and 01-a.md"]


@pytest.mark.parametrize("line", ["- [ ] T12 Short.", "- [ ] T0001 Long.", "- [ ] T01a Mixed."])
def test_an_invalid_identifier_is_refused(tmp_path, line):
    files = {**BASE, "03-c.md": [line]}
    errors = rt.validate(_roadmap(tmp_path, files)).errors
    assert len(errors) == 1 and errors[0].startswith("03-c.md: invalid task identifier")


def test_a_missing_historical_task_is_refused(tmp_path):
    files = {"01-a.md": BASE["01-a.md"]}
    assert rt.validate(_roadmap(tmp_path, files)).errors == [
        "T003: required by the historical range T001–T003 but not defined"
    ]


def test_a_gap_above_the_historical_range_is_refused(tmp_path):
    files = {**BASE, "03-c.md": ["- [ ] T004 Four.", "- [ ] T006 Six."]}
    assert rt.validate(_roadmap(tmp_path, files)).errors == [
        "T006: the identifiers above T003 must be contiguous; T005 to T005 are missing"
    ]


def test_the_historical_range_comes_from_the_tracking_file(tmp_path):
    root = _roadmap(tmp_path, BASE, task_range="T001–T005")
    assert rt.validate(root).errors[:1] == [
        "T004: required by the historical range T001–T005 but not defined"
    ]
    (root / "tracking.json").write_text(json.dumps({"task_range": "all of them"}))
    with pytest.raises(ValueError, match="task_range"):
        rt.validate(root)


def test_other_checkbox_lines_and_prose_are_not_tasks(tmp_path):
    files = {**BASE, "03-c.md": ["- [ ] Test the thing", "- [ ] Tasks later", "T9 prose"]}
    assert rt.validate(_roadmap(tmp_path, files)).errors == []


def test_the_command_prints_the_count_and_fails_on_errors(tmp_path):
    root = _roadmap(tmp_path, BASE)
    ok = subprocess.run(
        [sys.executable, rt.__file__, str(root)], capture_output=True, text=True, check=False
    )
    assert ok.returncode == 0 and ok.stdout.strip() == "Verified 3 tasks"
    (root / "03-c.md").write_text("- [ ] T002 Again.\n")
    bad = subprocess.run(
        [sys.executable, rt.__file__, str(root)], capture_output=True, text=True, check=False
    )
    assert bad.returncode == 1 and "T002: defined in 01-a.md and 03-c.md" in bad.stderr


def test_the_repository_roadmap_is_valid():
    root = Path(__file__).resolve().parents[2] / "docs" / "thesis-remediation"
    assert rt.validate(root).errors == []


def test_an_invalid_line_does_not_hide_the_valid_lines_after_it(tmp_path):
    files = {**BASE, "03-c.md": ["- [ ] T12 Bad.", "- [ ] T002 Again."]}
    assert rt.validate(_roadmap(tmp_path, files)).errors == [
        "03-c.md: invalid task identifier 'T12'",
        "T002: defined in 01-a.md and 03-c.md",
    ]


def test_the_first_task_is_required_and_a_missing_range_key_is_refused(tmp_path):
    root = _roadmap(tmp_path, {"01-a.md": ["- [ ] T002 x."], "02-b.md": BASE["02-b.md"]})
    assert rt.validate(root).errors == [
        "T001: required by the historical range T001–T003 but not defined"
    ]
    (root / "tracking.json").write_text("{}")
    with pytest.raises(ValueError, match="got None$"):
        rt.validate(root)


def test_the_range_may_use_non_ascii_text_in_the_tracking_file(tmp_path):
    root = _roadmap(tmp_path, BASE)
    assert "–" in (root / "tracking.json").read_text(encoding="utf-8")
    assert rt.validate(root).count == 3


def test_a_checked_reference_to_an_unchecked_definition_is_refused(tmp_path):
    files = {**BASE, "03-c.md": ["- [x] T001 (promoted, see 01) First."]}
    assert rt.validate(_roadmap(tmp_path, files)).errors == [
        "T001: 03-c.md is checked but its definition in 01-a.md is unchecked"
    ]


def test_main_reports_in_process(tmp_path, capsys):
    root = _roadmap(tmp_path, BASE)
    assert rt.main(["x", str(root)]) == 0
    assert capsys.readouterr().out == "Verified 3 tasks\n"
    (root / "03-c.md").write_text("- [ ] T002 Again.\n")
    assert rt.main(["x", str(root)]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "T002: defined in 01-a.md and 03-c.md\n"
