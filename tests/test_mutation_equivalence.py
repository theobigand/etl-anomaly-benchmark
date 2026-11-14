"""Owner-reviewed equivalences adjust the eligible denominator only under strict binding."""

from __future__ import annotations

import copy
import hashlib

import pytest

from tests.test_mutation_risk_policy import _api, _campaign, _policy

SOURCE = hashlib.sha256(b"def compute(value):\n    return value + 1\n").hexdigest()
OWNER = "the-owner"
ENV = {"numpy": "2.4.6", "pandas": "3.0.6"}


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
        "author": OWNER,
        "verdict": "accepted",
        "approver": OWNER,
        "decision_date": "2026-11-11",
        "policy_version": 2,
        "environment": dict(ENV),
        "assessments": [{"assessor": "assistant", "verdict": "ACCEPT", "note": "preliminary"}],
    }
    record.update(change)
    return record


def _document(*records, **change):
    document = {
        "version": 2,
        "review_mode": "sole_author_owner_review",
        "owner": OWNER,
        "records": list(records),
    }
    document.update(change)
    return document


def _setup(tmp_path, killed=97, total=100):
    policy = _policy(tmp_path, ("L4",))
    catalog, records = _campaign(policy, [(killed, total)])
    survivor = next(r["id"] for r in records if r["outcome"] == "survived")
    return policy, catalog, records, survivor


def _evaluate(policy, tmp_path, catalog, records, document=None, environment=ENV):
    return _api().evaluate(policy, tmp_path, catalog, records, document, environment)


def test_the_owner_may_approve_an_equivalence_they_also_proposed(tmp_path):
    policy, catalog, records, survivor = _setup(tmp_path, killed=96, total=99)
    assert _evaluate(policy, tmp_path, catalog, records)["status"] == "FAIL"
    record = _record(policy, catalog, survivor)
    assert record["author"] == record["approver"] == OWNER
    result = _evaluate(policy, tmp_path, catalog, records, _document(record))
    module = result["modules"]["app/unit0.py"]
    assert module["eligible"] == 99 and module["survived"] == 3 and module["killed"] == 96
    assert module["equivalent_accepted"] == 1 and module["adjusted_eligible"] == 98
    assert module["raw_score"] == pytest.approx(100 * 96 / 99)
    assert module["score"] == pytest.approx(100 * 96 / 98) and module["status"] == "FAIL"
    assert result["accepted_equivalents"] == {"app/unit0.py": [survivor]}
    assert result["review_mode"] == "sole_author_owner_review"


def test_enough_accepted_equivalents_can_reach_the_exact_threshold(tmp_path):
    policy, catalog, records, _ = _setup(tmp_path, killed=96, total=100)
    survivors = [r["id"] for r in records if r["outcome"] == "survived"]
    assert _evaluate(policy, tmp_path, catalog, records)["status"] == "FAIL"
    two = _document(*(_record(policy, catalog, key) for key in survivors[:2]))
    assert _evaluate(policy, tmp_path, catalog, records, two)["status"] == "FAIL"
    four = _document(*(_record(policy, catalog, key) for key in survivors))
    result = _evaluate(policy, tmp_path, catalog, records, four)
    assert result["status"] == "PASS"
    assert result["modules"]["app/unit0.py"]["raw_score"] == pytest.approx(96.0)


@pytest.mark.parametrize("verdict", ["proposed", "rejected", "inconclusive"])
def test_a_claim_that_is_not_accepted_never_leaves_the_denominator(tmp_path, verdict):
    policy, catalog, records, survivor = _setup(tmp_path, killed=96, total=100)
    change = {"verdict": verdict}
    if verdict == "proposed":
        change |= {"approver": "", "decision_date": ""}
    document = _document(_record(policy, catalog, survivor, **change))
    result = _evaluate(policy, tmp_path, catalog, records, document)
    module = result["modules"]["app/unit0.py"]
    assert module["equivalent_accepted"] == 0 and module["adjusted_eligible"] == 100
    assert module["score"] == pytest.approx(96.0) and result["accepted_equivalents"] == {}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"verdict": "approved"}, "invalid equivalence verdict"),
        ({"approver": "someone-else"}, "recorded by the declared owner"),
        ({"approver": ""}, "recorded by the declared owner"),
        ({"decision_date": "yesterday"}, "ISO 8601"),
        ({"decision_date": ""}, "ISO 8601"),
        ({"policy_version": 1}, "policy version or risk level"),
        ({"risk": "L1"}, "policy version or risk level"),
        ({"source_sha256": "0" * 64}, "stale"),
        ({"catalog_sha256": "0" * 64}, "stale"),
        ({"id": "app.unit0.x_compute__mutmut_999"}, "unknown"),
        ({"path": "app/other.py"}, "unknown"),
        ({"reason": " "}, "nonempty text"),
        ({"evidence": []}, "supporting evidence"),
        ({"evidence": [""]}, "supporting evidence"),
        ({"environment": {}}, "dependency versions"),
        ({"environment": {"numpy": ""}}, "dependency versions"),
        ({"assessments": [{"assessor": "x", "verdict": "MAYBE", "note": "n"}]}, "assessments"),
        ({"assessments": "preliminary"}, "assessments"),
    ],
)
def test_invalid_or_unsupported_records_reject_the_evidence(tmp_path, change, message):
    policy, catalog, records, survivor = _setup(tmp_path)
    document = _document(_record(policy, catalog, survivor, **change))
    with pytest.raises(ValueError, match=message):
        _evaluate(policy, tmp_path, catalog, records, document)


def test_a_proposed_claim_must_not_carry_an_approver_or_date(tmp_path):
    policy, catalog, records, survivor = _setup(tmp_path)
    for field in ("approver", "decision_date"):
        record = _record(
            policy, catalog, survivor, verdict="proposed", approver="", decision_date=""
        )
        record[field] = OWNER if field == "approver" else "2026-11-11"
        with pytest.raises(ValueError, match="must not carry"):
            _evaluate(policy, tmp_path, catalog, records, _document(record))


@pytest.mark.parametrize(
    "document_change",
    [
        {"review_mode": "independent_review"},
        {"owner": "another-person"},
        {"version": 1},
    ],
)
def test_the_document_must_match_the_declared_review_mode_owner_and_version(
    tmp_path, document_change
):
    policy, catalog, records, survivor = _setup(tmp_path)
    document = _document(_record(policy, catalog, survivor), **document_change)
    with pytest.raises(ValueError, match="review mode and owner|version 2"):
        _evaluate(policy, tmp_path, catalog, records, document)


def test_a_policy_without_the_declared_review_mode_cannot_accept_any_record(tmp_path):
    policy, catalog, records, survivor = _setup(tmp_path)
    document = _document(_record(policy, catalog, survivor))
    del policy["governance"]
    with pytest.raises(ValueError, match="does not declare"):
        _evaluate(policy, tmp_path, catalog, records, document)
    policy["governance"] = {"review_mode": "independent_review", "owner": OWNER}
    with pytest.raises(ValueError, match="governance"):
        _evaluate(policy, tmp_path, catalog, records, document)


def test_an_accepted_claim_is_rejected_when_the_dependencies_differ(tmp_path):
    policy, catalog, records, survivor = _setup(tmp_path)
    document = _document(_record(policy, catalog, survivor))
    for environment in ({**ENV, "pandas": "3.1.0"}, {"numpy": "2.4.6"}, {}, None):
        with pytest.raises(ValueError, match="incompatible with the campaign environment"):
            _evaluate(policy, tmp_path, catalog, records, document, environment)
    assert _evaluate(policy, tmp_path, catalog, records, document, {**ENV, "torch": "2"})


def test_a_claim_that_is_not_accepted_does_not_depend_on_the_environment(tmp_path):
    policy, catalog, records, survivor = _setup(tmp_path)
    record = _record(policy, catalog, survivor, verdict="proposed", approver="", decision_date="")
    assert _evaluate(policy, tmp_path, catalog, records, _document(record), None)["status"]


def test_only_a_surviving_mutant_can_be_accepted(tmp_path):
    policy, catalog, records, _ = _setup(tmp_path)
    killed = next(r["id"] for r in records if r["outcome"] == "killed")
    document = _document(_record(policy, catalog, killed))
    with pytest.raises(ValueError, match="only a surviving mutant"):
        _evaluate(policy, tmp_path, catalog, records, document)
    changed = [dict(r, outcome="killed") if r["outcome"] == "survived" else r for r in records]
    survivor = next(r["id"] for r in records if r["outcome"] == "survived")
    with pytest.raises(ValueError, match="only a surviving mutant"):
        _evaluate(policy, tmp_path, catalog, changed, _document(_record(policy, catalog, survivor)))


def test_duplicate_identities_and_extra_fields_are_rejected(tmp_path):
    policy, catalog, records, survivor = _setup(tmp_path)
    record = _record(policy, catalog, survivor)
    with pytest.raises(ValueError, match="duplicate"):
        _evaluate(policy, tmp_path, catalog, records, _document(record, copy.deepcopy(record)))
    with pytest.raises(ValueError, match="shape"):
        _evaluate(policy, tmp_path, catalog, records, _document({**record, "note": "free"}))
    with pytest.raises(ValueError, match="shape"):
        _evaluate(policy, tmp_path, catalog, records, _document({**record, "reviewer": "x"}))


def test_a_changed_source_or_catalog_invalidates_an_approved_record(tmp_path):
    policy, catalog, records, survivor = _setup(tmp_path)
    document = _document(_record(policy, catalog, survivor))
    (tmp_path / "app/unit0.py").write_text("def compute(value):\n    return value + 2\n")
    with pytest.raises(ValueError, match="stale"):
        _evaluate(policy, tmp_path, catalog, records, document)


def test_without_a_document_nothing_is_waived_and_raw_equals_adjusted(tmp_path):
    policy, catalog, records, _ = _setup(tmp_path)
    module = _evaluate(policy, tmp_path, catalog, records)["modules"]["app/unit0.py"]
    assert module["equivalent_accepted"] == 0 and module["raw_score"] == module["score"]


def test_the_policy_governance_block_is_validated():
    api = _api()
    base = {
        "version": 2,
        "thresholds": {"L1": 80, "L2": 90, "L3": 95, "L4": 98},
        "roots": ["app"],
        "units": {"app/a.py": {"level": "L4", "reason": "r"}},
    }
    api._validate_declarations(
        {**base, "governance": {"review_mode": api.REVIEW_MODE, "owner": "o"}}
    )
    for bad in (
        {"review_mode": api.REVIEW_MODE},
        {"review_mode": "other", "owner": "o"},
        {"review_mode": api.REVIEW_MODE, "owner": " "},
        {"review_mode": api.REVIEW_MODE, "owner": "o", "extra": 1},
        "owner",
    ):
        with pytest.raises(ValueError, match="governance"):
            api._validate_declarations({**base, "governance": bad})


def _claim(policy, catalog, key, verdict):
    change = {"verdict": verdict}
    if verdict == "proposed":
        change |= {"approver": "", "decision_date": ""}
    return _record(policy, catalog, key, **change)


@pytest.mark.parametrize("verdict", ["proposed", "rejected", "inconclusive"])
def test_a_claim_that_is_not_accepted_may_be_killed_by_better_tests(tmp_path, verdict):
    policy, catalog, records, survivor = _setup(tmp_path, killed=96, total=100)
    improved = [dict(r, outcome="killed") if r["id"] == survivor else r for r in records]
    document = _document(_claim(policy, catalog, survivor, verdict))
    result = _evaluate(policy, tmp_path, catalog, improved, document)
    module = result["modules"]["app/unit0.py"]
    assert module["killed"] == 97 and module["survived"] == 3
    assert module["equivalent_accepted"] == 0 and module["adjusted_eligible"] == 100
    assert module["raw_score"] == module["score"] == pytest.approx(97.0)
    assert result["accepted_equivalents"] == {}


def test_a_non_accepted_claim_is_still_bound_to_identity_and_provenance(tmp_path):
    policy, catalog, records, survivor = _setup(tmp_path)
    improved = [dict(r, outcome="killed") if r["id"] == survivor else r for r in records]
    stale = _claim(policy, catalog, survivor, "inconclusive") | {"source_sha256": "0" * 64}
    with pytest.raises(ValueError, match="stale"):
        _evaluate(policy, tmp_path, catalog, improved, _document(stale))
    unknown = _claim(policy, catalog, survivor, "rejected") | {
        "id": "app.unit0.x_compute__mutmut_999"
    }
    with pytest.raises(ValueError, match="unknown"):
        _evaluate(policy, tmp_path, catalog, improved, _document(unknown))
    twice = _claim(policy, catalog, survivor, "inconclusive")
    with pytest.raises(ValueError, match="duplicate"):
        _evaluate(policy, tmp_path, catalog, improved, _document(twice, copy.deepcopy(twice)))


def test_killing_an_inconclusive_mutant_changes_raw_and_adjusted_scores_exactly(tmp_path):
    policy, catalog, records, _ = _setup(tmp_path, killed=96, total=100)
    survivors = [r["id"] for r in records if r["outcome"] == "survived"]
    accepted, inconclusive = survivors[0], survivors[1]
    document = _document(
        _record(policy, catalog, accepted), _claim(policy, catalog, inconclusive, "inconclusive")
    )
    before = _evaluate(policy, tmp_path, catalog, records, document)["modules"]["app/unit0.py"]
    assert (before["killed"], before["adjusted_eligible"]) == (96, 99)
    improved = [dict(r, outcome="killed") if r["id"] == inconclusive else r for r in records]
    after = _evaluate(policy, tmp_path, catalog, improved, document)["modules"]["app/unit0.py"]
    assert (after["killed"], after["eligible"], after["adjusted_eligible"]) == (97, 100, 99)
    assert after["raw_score"] == pytest.approx(97.0)
    assert after["score"] == pytest.approx(100 * 97 / 99)
