"""Compatibility model: units by protocol, labels, registry-only computation; synthetic registry."""

import ast
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compatibility_model as cm  # noqa: E402
import pipeline_batch as pb  # noqa: E402
import registry_units as ru  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS = {
    "P-TS": {"detection_unit": "time_window", "mechanisms": ["level_shift"]},
    "P-TAB": {"detection_unit": "row", "mechanisms": ["duplicate_rows", "scale"]},
    "P-REL": {"detection_unit": "relationship", "mechanisms": ["broken_reference"]},
}


def _setup(tmp_path, protocols=None):
    ev = tmp_path / "ev"
    ev.mkdir()
    fact = {"anomaly_origin": "controlled_injection", "units": 9, "min_units": 1}
    facts = {
        "a": {**fact, "independent_group": "ga", "protocol_id": "P-TS", "view": "va"},
        "b": {**fact, "independent_group": "gb", "protocol_id": "P-TAB", "view": "vb"},
        "c": {**fact, "independent_group": "gc", "protocol_id": "P-REL", "view": "vc"},
        "d": {**fact, "independent_group": "gc", "protocol_id": "P-TAB", "view": "vc"},
    }
    (ev / "readiness_facts.json").write_text(json.dumps({"facts": facts}))
    ready = {"C3": ["ga"], "C1": ["gb", "gc"], "C5": ["gc"]}
    stratum = {"a": "C3", "b": "C1", "c": "C5", "d": "C1"}  # gc is P-REL in C5 and P-TAB in C1
    datasets = [{"id": i, "stratum": c} for i, c in stratum.items()]
    (ev / "readiness.json").write_text(json.dumps({"ready_groups": ready, "datasets": datasets}))
    ok = {"eligible": True, "reasons": []}
    no = {"eligible": False, "reasons": ["no parseable time column"]}
    audit = {"ga": ok, "gb": no, "gc": no}
    (ev / "batch_eligibility.json").write_text(json.dumps({"groups": audit}))
    (ev / "anomaly_protocols.json").write_text(json.dumps({"protocols": protocols or PROTOCOLS}))
    return ev


def test_every_unit_is_labelled_natural_replayed_or_logical_and_new_units_are_provisional(
    tmp_path,
):
    units = cm.build(_setup(tmp_path))["units"]
    assert {u["kind"] for u in units.values()} == {"natural", "replayed", "logical"}
    assert units["temporal_batch"] == {
        "kind": "replayed",
        "status": "registered",
        "basis": "timestamped records replayed in time order as loads",
    }
    provisional = {n for n, u in units.items() if u["status"] == "provisional"}
    assert provisional == {"observed_load", "event_window", "relational_load", "document_batch"}
    assert {n for n, u in units.items() if u["status"] == "registered"} == {"temporal_batch"}
    assert units["row"]["status"] == "protocol_defined"


def test_the_unit_table_agrees_with_the_registry_units_and_detectors_run_on_registered_ones_only():
    assert set(ru.UNITS) <= set(cm.UNITS)
    for name, (status, _mechanisms) in ru.UNITS.items():
        expected = "registered" if status == ru.REGISTERED else "provisional"
        assert cm.UNITS[name][1] == expected
    assert all(cm.UNITS[unit][1] == "registered" for unit in ru.DETECTOR_UNITS)


def test_a_protocol_row_lists_its_own_unit_without_a_runner_and_the_registered_batch_unit(tmp_path):
    cells = cm.build(_setup(tmp_path))["protocols"]["P-TS"]
    own, batch = cells
    assert own == {
        "unit": "time_window",
        "operators": ["level_shift"],
        "detectors": [],
        "metrics": ["tp", "fp", "fn"],
        "executable": False,
    }
    assert batch["unit"] == "temporal_batch" and batch["executable"] is True
    assert batch["detectors"] == list(pb.DETECTORS)
    assert batch["operators"] == list(pb.MECHANISMS)
    assert batch["metrics"] == ["recall", "false_alert_rate", "roc_auc", "ap"]


def test_a_provisional_unit_is_listed_but_never_executable_or_given_detectors(tmp_path):
    rel = cm.build(_setup(tmp_path))["protocols"]["P-REL"]
    provisional = next(c for c in rel if c["unit"] == "relational_load")
    assert provisional["executable"] is False and provisional["detectors"] == []
    assert "referential_integrity" in provisional["operators"]


def test_groups_get_their_units_per_participation_from_protocol_and_audit_only(tmp_path):
    groups = cm.build(_setup(tmp_path))["groups"]
    (ga,) = groups["ga"]["participations"]
    assert ga["category"] == "C3" and ga["protocol"] == "P-TS"
    assert ga["units"] == [
        {"unit": "time_window", "runnable": False, "reason": "no registry-driven runner"},
        {"unit": "temporal_batch", "runnable": True, "reason": ""},
    ]
    (gb,) = groups["gb"]["participations"]
    assert gb["units"][1] == {
        "unit": "temporal_batch",
        "runnable": False,
        "reason": "no parseable time column",
    }
    c1, c5 = groups["gc"]["participations"]
    assert (c1["category"], c1["protocol"]) == ("C1", "P-TAB")
    assert (c5["category"], c5["protocol"]) == ("C5", "P-REL")
    assert [u["unit"] for u in c5["units"]] == ["relationship", "temporal_batch", "relational_load"]
    assert c5["units"][2]["reason"].startswith("unsupported")


def test_the_matrix_counts_participations_and_runnable_ones_by_category_protocol_and_unit(
    tmp_path,
):
    matrix = cm.build(_setup(tmp_path))["matrix"]
    assert matrix["C3"]["P-TS"]["temporal_batch"] == {"groups": 1, "runnable": 1}
    assert matrix["C3"]["P-TS"]["time_window"] == {"groups": 1, "runnable": 0}
    assert matrix["C1"]["P-TAB"]["temporal_batch"] == {"groups": 2, "runnable": 0}
    assert matrix["C5"]["P-REL"]["relational_load"] == {"groups": 1, "runnable": 0}
    assert matrix["C5"]["P-REL"]["relationship"] == {"groups": 1, "runnable": 0}
    assert "P-REL" not in matrix["C1"]  # the protocol of the participation, not of the group


def test_a_ready_participation_without_a_protocol_fact_is_refused(tmp_path):
    ev = _setup(tmp_path)
    ready = json.loads((ev / "readiness.json").read_text())
    ready["ready_groups"]["C3"].append("ghost")
    (ev / "readiness.json").write_text(json.dumps(ready))
    with pytest.raises(ValueError, match=r"participations without a protocol fact: \['ghost/C3'\]"):
        cm.build(ev)


def test_a_protocol_without_a_definition_is_refused(tmp_path):
    ev = _setup(tmp_path, protocols={k: v for k, v in PROTOCOLS.items() if k != "P-REL"})
    with pytest.raises(ValueError, match=r"^protocols without a definition: \['P-REL'\]$"):
        cm.build(ev)


def test_the_model_is_deterministic_and_main_prints_or_writes_it(tmp_path, capsys):
    ev = _setup(tmp_path)
    assert cm.main(["--evidence", str(ev)]) == 0
    first = capsys.readouterr().out
    out = tmp_path / "m.json"
    assert cm.main(["--evidence", str(ev), "--output", str(out)]) == 0
    assert out.read_text() == first
    assert first == json.dumps(cm.build(ev), indent=1, sort_keys=True) + "\n"
    args = cm.build_parser().parse_args([])
    assert args.evidence == cm.EVIDENCE and args.output is None


def test_no_dataset_view_or_group_name_appears_in_the_module():
    registry = ROOT / "verification/evidence/dataset_registry_v2"
    facts = json.loads((registry / "readiness_facts.json").read_text())["facts"]
    names = {n for f in facts.values() for n in (f.get("independent_group"), f.get("view")) if n}
    names |= set(facts)
    tree = ast.parse((ROOT / "research/compatibility_model.py").read_text())
    literals = {
        n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    assert len(names) > 200  # the real registry is read, not an empty stand-in
    assert sorted(literals & names) == []


def test_the_committed_model_matches_the_committed_registry():
    registry = ROOT / "verification/evidence/dataset_registry_v2"
    committed = json.loads((registry / "compatibility_model.json").read_text())
    assert committed == json.loads(json.dumps(cm.build(registry)))
