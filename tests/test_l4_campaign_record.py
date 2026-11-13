"""The recorded L4 measurement reconciles with the policy and with its own arithmetic."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/thesis-remediation/evidence/l4-campaign-2026-11-13/final-measurement.json"
REPORT = ROOT / "docs/thesis-remediation/L4_CAMPAIGN_REPORT_2026-11-13.md"
POLICY = ROOT / "verification/mutation_risk_policy.json"
RESOLVED = ("killed", "survived")


@pytest.fixture(scope="module")
def record():
    return json.loads(EVIDENCE.read_text())


@pytest.fixture(scope="module")
def policy():
    return json.loads(POLICY.read_text())


def test_the_measurement_holds_exactly_the_classified_units_with_their_current_levels(
    record, policy
):
    assert set(record["modules"]) == set(policy["units"])
    for path, unit in policy["units"].items():
        assert record["modules"][path]["level"] == unit["level"], path
        assert record["modules"][path]["threshold"] == policy["thresholds"][unit["level"]]


def test_every_unit_accounts_for_each_of_its_mutants_exactly_once(record):
    for path, unit in record["modules"].items():
        assert sum(unit["counts"].values()) == unit["eligible"], path
        assert unit["killed"] == unit["counts"].get("killed", 0), path
    assert sum(u["eligible"] for u in record["modules"].values()) == record["mutants"]
    assert sum(u["killed"] for u in record["modules"].values()) == record["killed"]


def test_each_status_follows_the_integer_rule_and_never_hides_an_unresolved_mutant(record):
    for path, unit in record["modules"].items():
        counts, total = unit["counts"], unit["eligible"]
        unresolved = sum(n for key, n in counts.items() if key not in RESOLVED)
        adjusted = total - len(unit["accepted_equivalents"])
        if not total:
            expected = "NO_MUTANTS" if unit["status"] == "NO_MUTANTS" else "INCOMPLETE"
        elif unresolved:
            expected = "INCOMPLETE"
        elif unit["killed"] * 100 >= unit["threshold"] * total:
            expected = "PASS_RAW"
        elif adjusted and unit["killed"] * 100 >= unit["threshold"] * adjusted:
            expected = "PASS_ADJUSTED"
        else:
            expected = "FAIL"
        assert unit["status"] == expected, path


def test_a_unit_without_mutants_declares_a_technical_reason_in_the_policy(record, policy):
    for path, unit in record["modules"].items():
        if unit["status"] == "NO_MUTANTS":
            assert "no_mutants" in policy["units"][path], path


def test_the_summary_and_the_report_tables_equal_the_unit_records(record):
    counted = {}
    for unit in record["modules"].values():
        counted[unit["status"]] = counted.get(unit["status"], 0) + 1
    assert counted == record["summary"]
    text = REPORT.read_text()
    for level in ("L2", "L3", "L4"):
        units = [u for u in record["modules"].values() if u["level"] == level]
        passed = sum(u["status"] in ("PASS_RAW", "PASS_ADJUSTED") for u in units)
        failed = sum(u["status"] == "FAIL" for u in units)
        other = len(units) - passed - failed
        row = rf"\| {level} \| {len(units)} \| {passed} \| {failed} \| {other} \| "
        assert re.search(
            row + rf"{sum(u['killed'] for u in units)}/{sum(u['eligible'] for u in units)} \|", text
        )


def test_the_equivalence_exclusions_used_are_a_subset_of_the_accepted_owner_records(record):
    live = json.loads((ROOT / "verification/mutation_equivalence.json").read_text())["records"]
    accepted = {r["id"] for r in live if r["verdict"] == "accepted"}
    for unit in record["modules"].values():
        assert set(unit["accepted_equivalents"]) <= accepted
