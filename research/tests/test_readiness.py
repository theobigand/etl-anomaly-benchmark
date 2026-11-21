import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import readiness as rd  # noqa: E402


def full(**over):
    facts = {
        "id": "x:1",
        "source": "https://example.org",
        "licence_class": "open",
        "upstream_status": "verified",
        "files_verified": True,
        "structure_passed": True,
        "independent_group": "g",
        "privacy": "not_needed",
        "baseline_properties": [],
        "anomaly_origin": "controlled_injection",
        "units": 5000,
        "min_units": 1000,
        "protocol_id": "P-REL",
        "detection_unit": "row",
        "partitions": "70/15/15 chronological",
        "view_sha256": "ab" * 32,
        "view_preprocessing": "views.py@abc",
        "personal_fields_remaining": [],
    }
    facts.update(over)
    return facts


def test_a_complete_dataset_reaches_experiment_ready():
    assert rd.assess(full())["status"] == "experiment_ready"


def test_every_status_requires_the_previous_ones_and_names_what_failed():
    cases = {
        "discovered": full(source=None),
        "rights_verified": full(upstream_status="not_verified"),
        "acquired": full(files_verified=False),
        "structurally_valid": full(structure_passed=False),
        "scientifically_eligible": full(independent_group=None),
        "protocol_ready": full(protocol_id=None),
    }
    for stopped_at, facts in cases.items():
        result = rd.assess(facts)
        previous = (
            rd.STATUSES[rd.STATUSES.index(stopped_at) - 1] if stopped_at != "discovered" else None
        )
        assert result["status"] == previous
        assert result["failed"]["status"] == stopped_at and result["failed"]["reasons"]


def test_licence_class_and_privacy_and_size_gate_the_right_statuses():
    assert rd.assess(full(licence_class="unclear"))["status"] == "discovered"
    assert rd.assess(full(licence_class="research_only"))["status"] == "experiment_ready"
    assert rd.assess(full(privacy="unreviewed"))["status"] == "structurally_valid"
    assert rd.assess(full(units=10))["status"] == "structurally_valid"
    assert rd.assess(full(anomaly_origin=None))["status"] == "structurally_valid"
    assert rd.assess(full(personal_fields_remaining=["name"]))["status"] == "protocol_ready"
    assert rd.assess(full(view_sha256=None))["status"] == "protocol_ready"
    assert rd.assess(full(first_party=True, upstream_status=None))["status"] == "experiment_ready"


def test_summary_counts_datasets_reaching_each_status_and_groups_by_stratum():
    rows = [
        {"stratum": "C5", "status": "experiment_ready"},
        {"stratum": "C5", "status": "acquired"},
        {"stratum": "C6", "status": "protocol_ready"},
    ]
    table = rd.summarise(rows)
    assert table["C5"]["acquired"] == 2 and table["C5"]["experiment_ready"] == 1
    assert table["C6"]["protocol_ready"] == 1 and table["C6"]["experiment_ready"] == 0
    assert table["C6"]["discovered"] == 1


def test_facts_are_assembled_from_the_entry_the_declared_facts_and_the_view_manifest():
    entry = {
        "id": "a:1",
        "publisher": "pub",
        "stratum": "C5",
        "licence_class": "open",
        "eligible": True,
        "stages": {"data_acquired": True, "structural_validation": True},
    }
    declared = {
        "first_party": True,
        "independent_group": "g",
        "privacy": "handled",
        "baseline_properties": [],
        "anomaly_origin": "controlled_injection",
        "units": 5000,
        "min_units": 1000,
        "protocol_id": "P-REL",
        "partitions": "hash 70/15/15",
        "view": "v",
    }
    views = {"v": {"files": {"a.csv": {"sha256": "aa"}, "b.csv": {"sha256": "bb"}}}}
    protocols = {"P-REL": {"detection_unit": "relationship"}}
    facts = rd.facts_from(entry, declared, views, protocols)
    assert facts["detection_unit"] == "relationship" and len(facts["view_sha256"]) == 64
    assert rd.assess(facts)["status"] == "experiment_ready"
    no_view = rd.facts_from(entry, {**declared, "view": None}, views, protocols)
    assert rd.assess(no_view)["status"] == "protocol_ready"
    assert rd.facts_from(entry, None, views, protocols)["protocol_id"] is None
    ineligible = rd.facts_from({**entry, "eligible": False}, declared, views, protocols)
    assert rd.assess(ineligible)["status"] == "acquired"


def test_ready_groups_count_each_independent_group_once_per_stratum():
    rows = [
        {"stratum": "C4", "group": "loghub", "status": "experiment_ready"},
        {"stratum": "C4", "group": "loghub", "status": "experiment_ready"},
        {"stratum": "C4", "group": "other", "status": "protocol_ready"},
        {"stratum": "C5", "group": "oa", "status": "experiment_ready"},
    ]
    assert rd.ready_groups(rows) == {"C4": ["loghub"], "C5": ["oa"]}
