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
