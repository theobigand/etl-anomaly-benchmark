import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import check_mutation  # noqa: E402


def test_mutation_gate_rejects_missing_incomplete_and_low_score():
    with pytest.raises(ValueError):
        check_mutation.classify({})
    with pytest.raises(ValueError):
        check_mutation.classify({"total": 10, "killed": 9, "survived": 0})
    assert check_mutation.classify(
        {
            "total": 20,
            "killed": 19,
            "survived": 1,
            "no_tests": 0,
            "skipped": 0,
            "suspicious": 0,
            "timeout": 0,
            "check_was_interrupted_by_user": 0,
            "segfault": 0,
        }
    ) == ("PASS", 95.0)
    assert check_mutation.classify(
        {
            "total": 20,
            "killed": 18,
            "survived": 2,
            "no_tests": 0,
            "skipped": 0,
            "suspicious": 0,
            "timeout": 0,
            "check_was_interrupted_by_user": 0,
            "segfault": 0,
        }
    ) == ("FAIL", 90.0)


def test_mutation_command_exit_matches_recorded_outcomes(tmp_path, monkeypatch):
    stats = tmp_path / "mutation.json"
    monkeypatch.setattr(sys, "argv", ["check_mutation", str(stats)])
    result = {key: 0 for key in check_mutation.OUTCOMES}
    result.update(total=20, killed=19, survived=1)
    stats.write_text(json.dumps(result))
    assert check_mutation.main() == 0
    result.update(killed=18, survived=2)
    stats.write_text(json.dumps(result))
    assert check_mutation.main() == 1


def test_mutation_gate_rejects_zero_or_inconsistent_campaign(tmp_path):
    result = {key: 0 for key in check_mutation.OUTCOMES}
    result["total"] = 0
    with pytest.raises(ValueError, match="incomplete"):
        check_mutation.classify(result)
    result["total"] = 2
    result["killed"] = 1
    with pytest.raises(ValueError, match="incomplete"):
        check_mutation.classify(result)

    stats = tmp_path / "mutation.json"
    result["survived"] = 1
    stats.write_text(json.dumps(result))
    command = subprocess.run(
        [sys.executable, str(Path(check_mutation.__file__)), str(stats)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert command.returncode == 1
    assert "FAIL" in command.stdout


def _stats(**changes):
    result = {key: 0 for key in check_mutation.OUTCOMES}
    result.update(total=100, killed=100)
    result.update(changes)
    return result


@pytest.mark.parametrize(
    "stats",
    [
        _stats(total=95, killed=100, survived=-5),  # negative count offsets the sum
        _stats(total=100, killed=-1, survived=101),
        _stats(total=100, killed=95.0, survived=5),  # not an integer count
        _stats(total=100, killed=99, survived=1.0),
        _stats(total=True, killed=True),  # bool is not a count
        _stats(total="100", killed=100),
        _stats(total=100, killed=None),
        _stats(total=100, killed=101),  # more killed than mutants
    ],
)
def test_mutation_gate_rejects_invalid_counts(stats):
    with pytest.raises(ValueError):
        check_mutation.classify(stats)


@pytest.mark.parametrize(
    "outcome", ["check_was_interrupted_by_user", "segfault", "no_tests", "skipped"]
)
def test_mutation_gate_rejects_an_unreliable_campaign_despite_a_high_score(outcome):
    # 99% killed, but the campaign was interrupted, crashed, left a mutant
    # without tests or skipped one: the score cannot be trusted.
    with pytest.raises(ValueError, match=outcome):
        check_mutation.classify(_stats(killed=99, **{outcome: 1}))


def test_mutation_gate_counts_timeouts_and_suspicious_against_the_score():
    assert check_mutation.classify(_stats(killed=94, timeout=6)) == ("FAIL", 94.0)
    assert check_mutation.classify(_stats(killed=94, suspicious=6)) == ("FAIL", 94.0)


def test_mutation_gate_threshold_is_exact_at_the_boundary():
    # 95.0% is accepted, anything below fails, with no floating-point slack.
    assert check_mutation.classify(_stats(total=1000, killed=950, survived=50))[0] == "PASS"
    assert check_mutation.classify(_stats(total=1000, killed=949, survived=51))[0] == "FAIL"
    assert check_mutation.THRESHOLD >= 95.0


@pytest.mark.parametrize("content", [None, "", "not json", "[]", '"text"', "null"])
def test_mutation_command_reports_unreadable_stats_without_a_traceback(tmp_path, content):
    stats = tmp_path / "mutation.json"
    if content is not None:
        stats.write_text(content)
    command = subprocess.run(
        [sys.executable, str(Path(check_mutation.__file__)), str(stats)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert command.returncode == 1
    assert "INVALID" in command.stdout
    assert "Traceback" not in command.stderr


def test_mutation_command_rejects_an_interrupted_campaign(tmp_path):
    stats = tmp_path / "mutation.json"
    stats.write_text(json.dumps(_stats(killed=99, check_was_interrupted_by_user=1)))
    command = subprocess.run(
        [sys.executable, str(Path(check_mutation.__file__)), str(stats)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert command.returncode == 1
    assert "INVALID" in command.stdout
