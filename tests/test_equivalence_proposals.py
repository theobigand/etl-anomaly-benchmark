"""The proposals file holds claims for the owner to decide; it never contains an approval."""

import json
from pathlib import Path

from verification import mutation_policy

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "docs/thesis-remediation/equivalence/lstm_proposals_2026-11-11.json"
LIVE = ROOT / "verification/mutation_equivalence.json"


def test_every_proposal_is_undecided_and_carries_no_approver():
    document = json.loads(PROPOSALS.read_text())
    assert document["review_mode"] == mutation_policy.REVIEW_MODE
    assert (
        document["owner"]
        == json.loads((ROOT / "verification/mutation_risk_policy.json").read_text())["governance"][
            "owner"
        ]
    )
    assert len(document["records"]) == 9
    for record in document["records"]:
        assert record["verdict"] == "proposed"
        assert record["approver"] == "" and record["decision_date"] == ""
        assert record["environment"] and record["assessments"]


def test_a_proposal_is_never_counted_even_when_it_matches_a_survivor():
    document = json.loads(PROPOSALS.read_text())
    policy = json.loads((ROOT / "verification/mutation_risk_policy.json").read_text())
    path = "research/lstm_detector.py"
    keys = [record["id"] for record in document["records"]]
    catalog = {path: keys}
    records = [{"id": key, "path": path, "outcome": "survived"} for key in keys]
    for record in document["records"]:
        record["catalog_sha256"] = mutation_policy.catalog_digest(keys)
    sources = {path: document["records"][0]["source_sha256"]}
    accepted = mutation_policy.accepted_equivalents(
        document, {path: policy["units"][path]}, sources, catalog, records, policy["governance"], {}
    )
    assert accepted == {}


def test_the_live_approval_file_if_present_records_only_the_owners_decisions():
    if not LIVE.exists():
        return
    document = json.loads(LIVE.read_text())
    assert document["owner"] == "theobigand"
    for record in document["records"]:
        assert record["verdict"] in mutation_policy.VERDICTS
        if record["verdict"] != "proposed":
            assert record["approver"] == document["owner"] and record["decision_date"]
