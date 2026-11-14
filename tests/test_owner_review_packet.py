"""The owner review packet lists candidates only: no approval is created, arithmetic is exact."""

import json
from pathlib import Path

from verification import mutation_policy

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/thesis-remediation/evidence/mutation-survivors-2026-11-12.json"
CANDIDATES = ROOT / "docs/thesis-remediation/equivalence/owner_review_candidates_2026-11-12.json"
PACKET = ROOT / "docs/thesis-remediation/OWNER_EQUIVALENCE_REVIEW_2026-11-12.md"
LIVE = ROOT / "verification/mutation_equivalence.json"


def _survivors():
    document = json.loads(EVIDENCE.read_text())
    return document, {
        survivor["id"]: (module, survivor)
        for module in document["modules"]
        for survivor in module["survivors"]
    }


def test_every_candidate_is_a_collected_survivor_bound_to_its_module_digests():
    _, survivors = _survivors()
    records = json.loads(CANDIDATES.read_text())["records"]
    survived = {k for k, (_, s) in survivors.items() if s["outcome"] == "survived"}
    assert {r["id"] for r in records} == survived and len(records) == len(survived)
    for record in records:
        module, survivor = survivors[record["id"]]
        assert record["path"] == module["path"]
        assert record["source_sha256"] == module["source_sha256"]
        assert record["catalog_sha256"] == module["catalog_sha256"]
        assert record["diff"] == survivor["diff"] and record["risk"] == "L4"


def test_no_candidate_carries_an_approval_and_none_is_in_the_live_decision_file():
    document = json.loads(CANDIDATES.read_text())
    live_ids = {r["id"] for r in json.loads(LIVE.read_text())["records"]}
    for record in document["records"]:
        assert record["verdict"] == "proposed"
        assert record["approver"] == "" and record["decision_date"] == ""
        assert record["id"] not in live_ids
        assert record["assessments"] == [] and "not an owner decision" in record["reason"]


def test_proposals_are_never_counted_as_accepted_equivalents():
    document = json.loads(CANDIDATES.read_text())
    policy = json.loads((ROOT / "verification/mutation_risk_policy.json").read_text())
    by_path: dict[str, list[dict]] = {}
    for record in document["records"]:
        by_path.setdefault(record["path"], []).append(record)
    for path, records in by_path.items():
        keys = [r["id"] for r in records]
        for record in records:  # even a record bound to the digests it would need is not counted
            record["catalog_sha256"] = mutation_policy.catalog_digest(keys)
        sources = {path: records[0]["source_sha256"]}
        outcomes = [{"id": key, "path": path, "outcome": "survived"} for key in keys]
        accepted = mutation_policy.accepted_equivalents(
            {**document, "records": records},
            {path: policy["units"][path]},
            sources,
            {path: keys},
            outcomes,
            policy["governance"],
            {},
        )
        assert accepted == {}


def test_the_threshold_arithmetic_matches_the_policy_function_for_every_module():
    document, _ = _survivors()
    for module in document["modules"]:
        counts, total = module["counts"], module["total"]
        outcomes = [{"outcome": name} for name, n in counts.items() for _ in range(n)]
        assert len(outcomes) == total
        status = mutation_policy._summary(outcomes, total, 98)["status"]
        assert (status == "PASS") == (counts.get("killed", 0) * 100 >= 98 * total)


def test_the_stated_hypothetical_temporal_and_typed_run_scores_are_exact():
    assert 571 * 100 < 98 * (589 - 6) and 571 * 100 >= 98 * (589 - 7)
    assert 343 * 100 >= 98 * (351 - 1) and 343 * 100 < 98 * 351
    assert 343 * 10000 // 350 == 9800  # 98.00 percent exactly


def test_the_packet_names_every_candidate_and_states_that_it_decides_nothing():
    text = PACKET.read_text()
    for record in json.loads(CANDIDATES.read_text())["records"]:
        assert record["id"] in text
    assert "No owner decision exists" in text and "Hypothetical" in text
