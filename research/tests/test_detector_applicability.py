"""Detector applicability matrix and potential contrast eligibility (design only)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import detector_applicability as da  # noqa: E402
import unit_runner as ur  # noqa: E402

import etl_benchmark.quality as quality  # noqa: E402


def test_the_existing_detector_names_are_the_exports_of_the_quality_package():
    exported = {
        getattr(quality, name).name
        for name in quality.__all__
        if hasattr(getattr(quality, name), "name") and name != "Detector"
    }
    existing = {*da.RULES, *da.CLASSICAL, *da.NEURAL}
    assert exported - existing == {
        "drift"
    }  # the temporal-drift detector is opt-in, not a unit detector
    assert existing <= exported and len(existing) == 17
    assert set(da.FAMILY) == existing | set(da.CONSTRAINT_RULES)


def test_the_protocols_and_units_are_those_of_the_synthetic_runners():
    assert {p: r.unit for p, r in ur.RUNNERS.items()} == da.UNITS


def test_the_tabular_row_unit_uses_the_existing_adapter_for_every_detector():
    cells = [c for c in da.matrix() if c["protocol"] == "P-TAB"]
    assert len(cells) == 17
    assert {c["status"] for c in cells} == {"supported_existing_adapter"}
    assert {c["scientific"] for c in cells} == {"pending_unit_approval"}


def test_featurized_units_are_implemented_but_never_scientifically_approved():
    for protocol in ("P-TS", "P-SEQ", "P-REL", "P-NEST"):
        implemented = [
            c
            for c in da.matrix()
            if c["protocol"] == protocol and c["technical"] == "adapter_implemented"
        ]
        assert implemented
        assert {c["scientific"] for c in implemented} == {"pending_representation_approval"}
        assert all(c["representation"] for c in implemented)


def test_a_detector_that_cannot_answer_the_units_question_is_inappropriate_not_applicable():
    cells = {(c["detector"], c["protocol"]): c for c in da.matrix()}
    for protocol in ("P-SEQ", "P-REL", "P-NEST"):
        cell = cells[("great_expectations", protocol)]
        assert cell["status"] == "scientifically_inappropriate" and cell["note"]
    assert cells[("great_expectations", "P-TS")]["status"] == "adapter_implemented_pending_approval"
    assert "degenerates" in cells[("zscore", "P-SEQ")]["note"]


def test_the_unit_specific_constraint_rules_exist_for_one_unit_each_and_need_implementation():
    cells = [c for c in da.matrix() if c["kind"] == "constraint_rule_deterministic"]
    assert {(c["detector"], c["protocol"]) for c in cells} == {
        ("sequence_constraints", "P-SEQ"),
        ("fk_integrity", "P-REL"),
        ("schema_path_rules", "P-NEST"),
    }
    assert {c["status"] for c in cells} == {"requires_implementation"}
    assert all("declared" in c["note"] for c in cells)


def test_no_cell_is_listed_for_a_detector_defined_for_another_unit():
    assert all(c["status"] != "not_applicable" for c in da.matrix())
    assert len(da.matrix()) == 5 * 17 + 3


def test_every_runner_operator_has_a_representation_verdict():
    assert set(da.MECHANISMS) == set(da.UNITS)
    for ops in da.MECHANISMS.values():
        assert {v for v, _ in ops.values()} <= {"visible", "limited", "invisible"}
    assert da.MECHANISMS["P-REL"]["referential_violation"][0] == "visible"
    assert "constraint itself" in da.MECHANISMS["P-REL"]["referential_violation"][1]
    assert da.MECHANISMS["P-TAB"]["missing_values"][0] == "invisible"


def test_a_rule_counts_as_the_rule_side_only_where_it_is_a_meaningful_baseline():
    cells = da.matrix()
    now = da.protocols_for_contrast(cells, "F1a rule vs classical", da._usable)
    later = da.protocols_for_contrast(cells, "F1a rule vs classical", da._possible)
    assert now == ["P-TAB", "P-TS"] and later == list(da.UNITS)
    assert da.protocols_for_contrast(cells, "F1b classical vs neural", da._usable) == list(da.UNITS)
    assert da.protocols_for_contrast(cells, "F1c rule vs neural", da._usable) == ["P-TAB", "P-TS"]


def _row(cluster, category, floor=True):
    return {
        "categories": [category],
        "floor": floor,
        "domain": f"d{cluster}",
        "schema_family": f"s{cluster}",
        "curator": f"c{cluster}",
        "cluster": cluster,
        "exposed": False,
    }


def _compat(protocol):
    return {"participations": [{"category": "x", "protocol": protocol, "units": []}]}


def test_potential_eligibility_excludes_exposed_pilot_and_below_floor_clusters():
    table = {
        "tab1": _row("tab1", "C1"),
        "tab2": _row("tab2", "C1"),
        "tab3": _row("tab3", "C1", floor=False),
        "ts1": _row("ts1", "C3"),
        "rel1": _row("rel1", "C5"),
        "tabx": _row("tabx", "C1"),
    }
    compat = {
        "tab1": _compat("P-TAB"),
        "tab2": _compat("P-TAB"),
        "tab3": _compat("P-TAB"),
        "tabx": _compat("P-TAB"),
        "ts1": _compat("P-TS"),
        "rel1": _compat("P-REL"),
    }
    out = da.potential_eligibility(table, compat, {"tab2"}, ["tabx"])
    assert out["pool_clusters"] == 3  # tab1, ts1, rel1
    assert out["per_protocol"] == {"P-TAB": 1, "P-TS": 1, "P-SEQ": 0, "P-REL": 1, "P-NEST": 0}
    assert out["contrasts"]["F1a rule vs classical"]["now"] == {
        "protocols": ["P-TAB", "P-TS"],
        "clusters": 2,
    }
    assert out["contrasts"]["F1a rule vs classical"]["after_implementation"]["clusters"] == 3


def test_a_cluster_with_several_protocols_is_counted_once_per_contrast():
    table = {"a": _row("a", "C4")}
    compat = {"a": {"participations": [{"protocol": "P-TAB"}, {"protocol": "P-SEQ"}]}}
    out = da.potential_eligibility(table, compat, set(), [])
    assert out["per_protocol"]["P-TAB"] == out["per_protocol"]["P-SEQ"] == 1
    assert out["contrasts"]["F1b classical vs neural"]["now"]["clusters"] == 1


def test_the_committed_evidence_is_the_current_build_and_marks_everything_as_potential():
    path = da.EVIDENCE / "detector_applicability.json"
    committed = json.loads(path.read_text())
    assert committed == json.loads(json.dumps(da.build()))
    assert "not verified eligibility" in committed["note"]
    pool = committed["eligibility"]["plus_outcome_studies"]["pool_clusters"]
    assert pool < committed["eligibility"]["registry_exposed_only"]["pool_clusters"]


def test_the_command_line_prints_sorted_json(capsys):
    assert da.main([]) == 0
    text = capsys.readouterr().out
    assert text == json.dumps(json.loads(text), indent=1, sort_keys=True) + "\n"


def test_the_command_line_writes_a_file(tmp_path):
    target = tmp_path / "m.json"
    assert da.main(["--output", str(target)]) == 0
    assert json.loads(target.read_text())["pilot_size"] == 24


def test_cells_are_pinned_exactly():
    tab = da.cell("zscore", "P-TAB")
    assert tab == {
        "detector": "zscore",
        "protocol": "P-TAB",
        "unit": "row",
        "family": "rule",
        "kind": "statistical_rule",
        "technical": "existing_adapter",
        "scientific": "pending_unit_approval",
        "status": "supported_existing_adapter",
        "representation": "numeric columns of the row",
        "note": "",
    }
    seq = da.cell("isolation_forest", "P-SEQ")
    assert (seq["technical"], seq["scientific"], seq["status"], seq["kind"]) == (
        "adapter_implemented",
        "pending_representation_approval",
        "adapter_implemented_pending_approval",
        "learned",
    )
    assert seq["representation"].startswith("unit_scoring.SequenceFeaturizer")
    gx = da.cell("great_expectations", "P-REL")
    assert (gx["technical"], gx["scientific"], gx["status"]) == (
        "requires_implementation",
        "inappropriate",
        "scientifically_inappropriate",
    )
    fk = da.cell("fk_integrity", "P-REL")
    assert fk["technical"] == "requires_implementation" and fk["family"] == "rule"
    assert fk["scientific"] == "pending_unit_approval" and "never" not in fk["note"]
    other = da.cell("fk_integrity", "P-TAB")
    assert (other["status"], other["technical"], other["scientific"]) == ("not_applicable",) * 3
    assert other["note"] == "defined for another unit"


def test_the_status_filters_are_exact():
    usable = {"supported_existing_adapter", "adapter_implemented_pending_approval"}
    for status in usable:
        assert da._usable(status) and da._possible(status)
    assert not da._usable("requires_implementation") and da._possible("requires_implementation")
    for status in ("scientifically_inappropriate", "not_applicable"):
        assert not da._usable(status) and not da._possible(status)


def test_the_build_documents_its_inputs_and_scenarios():
    out = da.build(seed=5, pilot_size=16)
    assert (out["seed"], out["pilot_size"]) == (5, 16)
    assert set(out) == {"note", "seed", "pilot_size", "matrix", "mechanisms", "eligibility"}
    assert set(out["eligibility"]) == {"registry_exposed_only", "plus_outcome_studies"}
    assert out["mechanisms"]["P-TS"]["level_shift"] == {
        "representation": "visible",
        "note": "window mean changes",
    }
    assert (
        out["eligibility"]["registry_exposed_only"]["pool_clusters"]
        > out["eligibility"]["plus_outcome_studies"]["pool_clusters"]
    )


def test_the_rule_baseline_test_is_exact():
    rule = {"family": "rule", "protocol": "P-SEQ", "kind": "statistical_rule"}
    assert not da._is_baseline(rule)
    assert da._is_baseline({**rule, "kind": "constraint_rule_deterministic"})
    assert da._is_baseline({**rule, "protocol": "P-TS"})
    assert da._is_baseline({**rule, "protocol": "P-TAB"})
    assert da._is_baseline({"family": "classical", "protocol": "P-SEQ", "kind": "learned"})
