"""Recorded arithmetic can be checked without mistaking it for current execution."""

import copy
import hashlib
import shutil

import pytest

from tests.test_mutation_risk_policy import _campaign, _policy
from verification import mutation_policy


def _sources(policy, root):
    return {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in policy["units"]
    }


def test_recorded_arithmetic_matches_current_tree_arithmetic_after_the_tree_is_removed(tmp_path):
    policy = _policy(tmp_path)
    catalog, records = _campaign(policy, [(80, 100), (90, 100), (95, 100), (98, 100)])
    expected = mutation_policy.evaluate(policy, tmp_path, catalog, records)
    hashes = _sources(policy, tmp_path)
    shutil.rmtree(tmp_path / "app")
    with pytest.raises(ValueError, match="root does not exist"):
        mutation_policy.evaluate(policy, tmp_path, catalog, records)
    result = mutation_policy.evaluate_snapshot(policy, hashes, catalog, records)
    assert result == expected
    assert result["status"] == "PASS"
    assert result["sources"] == hashes


def test_recorded_critical_failure_cannot_be_hidden_by_stronger_lower_risk_scopes(tmp_path):
    policy = _policy(tmp_path, ("L1", "L4"))
    catalog, records = _campaign(policy, [(1000, 1000), (97, 100)])
    result = mutation_policy.evaluate_snapshot(policy, _sources(policy, tmp_path), catalog, records)
    assert result["status"] == result["levels"]["L4"]["status"] == "FAIL"
    assert result["total"]["score"] > 99


@pytest.mark.parametrize("defect", ["none", "missing", "extra", "boolean", "short", "nonhex"])
def test_recorded_sources_require_a_complete_sha256_mapping(tmp_path, defect):
    policy = _policy(tmp_path, ("L4",))
    catalog, records = _campaign(policy, [(100, 100)])
    hashes = _sources(policy, tmp_path)
    name = next(iter(hashes))
    if defect == "none":
        hashes = None
    elif defect == "missing":
        del hashes[name]
    elif defect == "extra":
        hashes["app/extra.py"] = "a" * 64
    else:
        hashes[name] = {"boolean": True, "short": "a" * 63, "nonhex": "g" * 64}[defect]
    with pytest.raises(ValueError, match="source"):
        mutation_policy.evaluate_snapshot(policy, hashes, catalog, records)


@pytest.mark.parametrize(
    "defect", ["version", "threshold", "level", "reason", "outside", "root", "exclusion"]
)
def test_recorded_policy_still_enforces_declarations_and_canonical_scope(tmp_path, defect):
    policy = _policy(tmp_path, ("L4",))
    catalog, records = _campaign(policy, [(100, 100)])
    hashes = _sources(policy, tmp_path)
    if defect == "version":
        policy["version"] = True
    elif defect == "threshold":
        policy["thresholds"]["L4"] = 97
    elif defect == "level":
        policy["units"]["app/unit0.py"]["level"] = "unknown"
    elif defect == "reason":
        policy["units"]["app/unit0.py"]["reason"] = " "
    elif defect == "outside":
        policy["units"]["elsewhere.py"] = policy["units"].pop("app/unit0.py")
    elif defect == "root":
        policy["roots"] = ["../app"]
    else:
        policy["units"]["app/unit0.py"]["no_mutants"] = " "
    with pytest.raises(ValueError):
        mutation_policy.evaluate_snapshot(policy, hashes, catalog, records)


def test_recorded_report_does_not_alias_or_modify_its_inputs(tmp_path):
    policy = _policy(tmp_path, ("L4",))
    catalog, records = _campaign(policy, [(100, 100)])
    hashes = _sources(policy, tmp_path)
    original = copy.deepcopy((policy, hashes, catalog, records))
    result = mutation_policy.evaluate_snapshot(policy, hashes, catalog, records)
    result["sources"]["app/unit0.py"] = "b" * 64
    assert (policy, hashes, catalog, records) == original


def test_current_tree_validation_remains_required_for_technical_exclusions(tmp_path):
    policy = _policy(tmp_path, ("L4", "L4"))
    policy["units"]["app/unit1.py"]["no_mutants"] = "Unverified recorded declaration"
    catalog, records = _campaign(policy, [(100, 100), (0, 0)])
    # A snapshot has no source bodies and can establish only declaration/arithmetic consistency.
    result = mutation_policy.evaluate_snapshot(policy, _sources(policy, tmp_path), catalog, records)
    assert result["status"] == "PASS"
    with pytest.raises(ValueError, match="contains functions"):
        mutation_policy.evaluate(policy, tmp_path, catalog, records)
