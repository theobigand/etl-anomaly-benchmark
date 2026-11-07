"""Reviewed equivalents adjust the eligible denominator only under strict binding."""

from __future__ import annotations

import copy
import hashlib

import pytest

from tests.test_mutation_risk_policy import _api, _campaign, _policy

SOURCE = hashlib.sha256(b"def compute(value):\n    return value + 1\n").hexdigest()


def _record(policy, catalog, key, **change):
    path = next(iter(policy["units"]))
    record = {
        "id": key,
        "path": path,
        "function": "compute",
        "diff": "-    return value + 1\n+    return 1 + value",
        "original_behavior": "adds one",
        "mutated_behavior": "adds one with commuted operands",
        "risk": policy["units"][path]["level"],
        "reason": "integer addition commutes",
        "evidence": ["tests/test_example.py::test_commutes"],
        "source_sha256": SOURCE,
        "catalog_sha256": _api().catalog_digest(catalog[path]),
        "author": "author-a",
        "reviewer": "reviewer-b",
        "approved": True,
        "review_date": "2026-11-08",
        "policy_version": 2,
    }
    record.update(change)
    return record


def _setup(tmp_path, killed=97, total=100):
    policy = _policy(tmp_path, ("L4",))
    catalog, records = _campaign(policy, [(killed, total)])
    survivor = next(r["id"] for r in records if r["outcome"] == "survived")
    return policy, catalog, records, survivor


def _document(*records):
    return {"version": 1, "records": list(records)}


def test_an_accepted_equivalent_changes_only_the_adjusted_score(tmp_path):
    policy, catalog, records, survivor = _setup(tmp_path, killed=96, total=99)
    plain = _api().evaluate(policy, tmp_path, catalog, records)
    assert plain["status"] == "FAIL"
    document = _document(_record(policy, catalog, survivor))
    result = _api().evaluate(policy, tmp_path, catalog, records, document)
    module = result["modules"]["app/unit0.py"]
    assert module["eligible"] == 99 and module["survived"] == 3 and module["killed"] == 96
    assert module["equivalent_accepted"] == 1 and module["adjusted_eligible"] == 98
    assert module["raw_score"] == pytest.approx(100 * 96 / 99)
    assert module["score"] == pytest.approx(100 * 96 / 98)
    assert module["status"] == "FAIL" and result["accepted_equivalents"] == {
        "app/unit0.py": [survivor]
    }


def test_enough_accepted_equivalents_can_reach_the_exact_threshold(tmp_path):
    policy, catalog, records, _ = _setup(tmp_path, killed=98, total=100)
    survivors = [r["id"] for r in records if r["outcome"] == "survived"]
    assert _api().evaluate(policy, tmp_path, catalog, records)["status"] == "PASS"
    policy, catalog, records, _ = _setup(tmp_path, killed=96, total=100)
    survivors = [r["id"] for r in records if r["outcome"] == "survived"]
    assert _api().evaluate(policy, tmp_path, catalog, records)["status"] == "FAIL"
    document = _document(*(_record(policy, catalog, key) for key in survivors[:2]))
    result = _api().evaluate(policy, tmp_path, catalog, records, document)
    assert result["modules"]["app/unit0.py"]["adjusted_eligible"] == 98
    assert result["status"] == "FAIL"
    document = _document(*(_record(policy, catalog, key) for key in survivors))
    result = _api().evaluate(policy, tmp_path, catalog, records, document)
    assert result["status"] == "PASS"
    assert result["modules"]["app/unit0.py"]["raw_score"] == pytest.approx(96.0)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"approved": False}, "reviewer other than the author"),
        ({"reviewer": "author-a"}, "reviewer other than the author"),
        ({"policy_version": 1}, "policy version or risk level"),
        ({"risk": "L1"}, "policy version or risk level"),
        ({"source_sha256": "0" * 64}, "stale"),
        ({"catalog_sha256": "0" * 64}, "stale"),
        ({"id": "app.unit0.x_compute__mutmut_999"}, "unknown"),
        ({"path": "app/other.py"}, "unknown"),
        ({"review_date": "yesterday"}, "ISO 8601"),
        ({"reason": " "}, "nonempty text"),
        ({"evidence": []}, "supporting evidence"),
        ({"evidence": [""]}, "supporting evidence"),
    ],
)
def test_invalid_or_unsupported_records_reject_the_evidence(tmp_path, change, message):
    policy, catalog, records, survivor = _setup(tmp_path)
    with pytest.raises(ValueError, match=message):
        _api().evaluate(
            policy,
            tmp_path,
            catalog,
            records,
            _document(_record(policy, catalog, survivor, **change)),
        )


def test_only_a_surviving_mutant_can_be_waived(tmp_path):
    policy, catalog, records, _ = _setup(tmp_path)
    killed = next(r["id"] for r in records if r["outcome"] == "killed")
    with pytest.raises(ValueError, match="only a surviving mutant"):
        _api().evaluate(
            policy, tmp_path, catalog, records, _document(_record(policy, catalog, killed))
        )


def test_duplicate_identities_and_extra_fields_are_rejected(tmp_path):
    policy, catalog, records, survivor = _setup(tmp_path)
    record = _record(policy, catalog, survivor)
    with pytest.raises(ValueError, match="duplicate"):
        _api().evaluate(
            policy, tmp_path, catalog, records, _document(record, copy.deepcopy(record))
        )
    with pytest.raises(ValueError, match="shape"):
        _api().evaluate(
            policy, tmp_path, catalog, records, _document({**record, "note": "free text"})
        )
    with pytest.raises(ValueError, match="version 1"):
        _api().evaluate(policy, tmp_path, catalog, records, {"version": 2, "records": []})


def test_a_changed_source_invalidates_an_approved_record(tmp_path):
    policy, catalog, records, survivor = _setup(tmp_path)
    document = _document(_record(policy, catalog, survivor))
    (tmp_path / "app/unit0.py").write_text("def compute(value):\n    return value + 2\n")
    with pytest.raises(ValueError, match="stale"):
        _api().evaluate(policy, tmp_path, catalog, records, document)


def test_without_a_document_nothing_is_waived_and_raw_equals_adjusted(tmp_path):
    policy, catalog, records, _ = _setup(tmp_path)
    module = _api().evaluate(policy, tmp_path, catalog, records)["modules"]["app/unit0.py"]
    assert module["equivalent_accepted"] == 0 and module["raw_score"] == module["score"]
