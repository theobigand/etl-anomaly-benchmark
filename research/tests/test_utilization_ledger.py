"""Utilization ledger: stage logic, adapter dry run, failure path per stage; synthetic registry."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import batch_panel as bp  # noqa: E402
import pipeline_batch as pb  # noqa: E402
import utilization_ledger as ul  # noqa: E402


def _series(rows=2400, seed=0):
    rng = np.random.default_rng(seed)
    stamps = pd.date_range("2021-01-01", periods=rows, freq="h").strftime("%Y-%m-%d %H:%M:%S")
    return pd.DataFrame({"when": stamps, **{f"x{i}": rng.normal(size=rows) for i in range(4)}})


def _fact(group, view, protocol, units=5000):
    return {
        "independent_group": group,
        "view": view,
        "protocol_id": protocol,
        "anomaly_origin": "controlled_injection",
        "units": units,
        "min_units": 1000,
    }


def _setup(tmp_path):
    ev, views = tmp_path / "ev", tmp_path / "views"
    ev.mkdir()
    for view in ("va", "vb", "vd"):
        (views / view).mkdir(parents=True)
    _series().to_csv(views / "va" / "t.csv", index=False)
    _series(seed=1).to_csv(views / "vd" / "t.csv", index=False)
    pd.DataFrame({"x": [1, 2]}).to_csv(views / "vb" / "t.csv", index=False)
    facts = {
        "a": _fact("ga", "va", "P-TS"),
        "b": _fact("gb", "vb", "P-TAB", units=10),
        "c": _fact("gc", "vc", "P-REL"),
        "d": _fact("gd", "vd", "P-TS"),
        "e": _fact("gc", "vc", "P-TAB"),  # the same group, another category, another protocol
    }
    (ev / "readiness_facts.json").write_text(json.dumps({"facts": facts}))
    ready = {"C3": ["ga", "gd"], "C1": ["gb", "gc"], "C5": ["gc"]}
    stratum = {"a": "C3", "b": "C1", "c": "C5", "d": "C3", "e": "C1"}
    datasets = [{"id": i, "stratum": c} for i, c in stratum.items()]
    (ev / "readiness.json").write_text(json.dumps({"ready_groups": ready, "datasets": datasets}))
    chosen = bp.audit_view(views, "va", "a", False)["table"]
    ok = {"eligible": True, "reasons": [], "view": "va", "views": ["va"], "table": chosen}
    audit = {
        "ga": ok,
        "gd": {**ok, "view": "vd", "views": ["vd"]},
        "gb": {"eligible": False, "reasons": ["only 1 continuous columns"], "table": None},
        "gc": {"eligible": False, "reasons": ["view vc is not built locally"], "table": None},
    }
    (ev / "batch_eligibility.json").write_text(json.dumps({"groups": audit}))
    protocols = {
        p: {"mechanisms": [f"m-{p}"], "detection_unit": u}
        for p, u in (("P-TS", "time_window"), ("P-TAB", "row"), ("P-REL", "relationship"))
    }
    (ev / "anomaly_protocols.json").write_text(json.dumps({"protocols": protocols}))
    manifest = {n: {"files": {"t.csv": {}}} for n in ("va", "vb", "vc", "vd")}
    (ev / "experimental_views.json").write_text(json.dumps(manifest))
    (ev / "linked_sets.json").write_text(
        json.dumps({"linked_sets": [{"groups": ["ga", "gd"]}], "exposed_groups": {"ga": "seen"}})
    )
    return ev, views


def test_the_dry_run_proves_executability_and_metadata_alone_never_does(tmp_path):
    ev, views = _setup(tmp_path)
    groups = ul.build(ev, views)["groups"]
    for ok in ("ga", "gd"):
        assert groups[ok]["stages"]["executable"]["status"] == "yes"
        assert groups[ok]["evidence_level"] == "adapter_dry_run"
        assert groups[ok]["dry_run"]["plan"]["batches"]["test"] > 0
    assert groups["gb"]["stages"]["structurally_compatible"]["status"] == "no"
    assert groups["gb"]["evidence_level"] == "none"
    assert groups["gc"]["stages"]["structurally_compatible"]["reason"] == "view not built locally"
    metadata_only = ul.build(ev, views, attempt=False)["groups"]
    assert metadata_only["ga"]["stages"]["executable"]["status"] == "no"
    assert metadata_only["ga"]["evidence_level"] == "metadata_only"


def test_no_stage_beyond_executable_holds_without_an_execution_record(tmp_path):
    ev, views = _setup(tmp_path)
    for group in ul.build(ev, views)["groups"].values():
        for stage in ("executed", "evaluated", "included", "excluded"):
            assert group["stages"][stage]["status"] == "no"
        assert group["evidence_level"] != "scientific_execution"


def test_a_failing_adapter_dry_run_is_recorded_with_its_reason_not_hidden(tmp_path):
    ev, views = _setup(tmp_path)
    pd.DataFrame({"x": [1, 2]}).to_csv(views / "vd" / "t.csv", index=False)  # audit is now stale
    group = ul.build(ev, views)["groups"]["gd"]
    assert group["dry_run"]["status"] == "failed" and group["dry_run"]["reason"]
    assert group["stages"]["executable"]["status"] == "no"
    assert group["stages"]["executable"]["reason"].startswith("the batch adapter dry run failed")
    assert group["evidence_level"] == "metadata_only"
    assert ul.WORK_UNIT_LEVEL.format(protocol="P-TS") in group["remaining_work"]


def test_a_dry_run_that_rebuilds_another_number_of_batches_fails(tmp_path):
    ev, views = _setup(tmp_path)
    audit = json.loads((ev / "batch_eligibility.json").read_text())
    audit["groups"]["ga"]["table"]["batches"] += 1
    (ev / "batch_eligibility.json").write_text(json.dumps(audit))
    dry = ul.build(ev, views)["groups"]["ga"]["dry_run"]
    assert dry["status"] == "failed" and "audited" in dry["reason"]


@pytest.mark.parametrize(
    ("record", "message"),
    [
        ({"executed": True}, "a group cannot be executed without a successful dry run"),
        ({"evaluated": True}, "a group cannot be evaluated without an execution"),
        ({"included": True}, "a group cannot be included without a successful evaluation"),
    ],
)
def test_a_later_stage_without_its_earlier_stage_is_refused(tmp_path, record, message):
    ev, views = _setup(tmp_path)
    with pytest.raises(ValueError, match=f"^{message}$"):
        ul.build(ev, views, executions={"gb": record})


def test_a_group_cannot_be_included_and_excluded(tmp_path):
    ev, views = _setup(tmp_path)
    full = {"executed": True, "evaluated": True, "included": True}
    with pytest.raises(ValueError, match="^a group cannot be both included and excluded$"):
        ul.build(ev, views, executions={"ga": full}, exclusions={"ga": "reason"})


def test_records_naming_groups_outside_the_registry_are_refused(tmp_path):
    ev, views = _setup(tmp_path)
    with pytest.raises(ValueError, match=r"^records name groups outside the registry: \['nope'\]$"):
        ul.build(ev, views, exclusions={"nope": "reason"})


def test_a_recorded_execution_and_exclusion_reach_the_stages_and_counts(tmp_path):
    ev, views = _setup(tmp_path)
    done = {"executed": True, "evaluated": True, "included": True}
    ledger = ul.build(ev, views, executions={"ga": done}, exclusions={"gc": "licence withdrawn"})
    groups, total = ledger["groups"], ledger["summary"]["total"]
    assert groups["ga"]["evidence_level"] == "scientific_execution"
    assert groups["gc"]["stages"]["excluded"] == {"status": "yes", "reason": "licence withdrawn"}
    assert total["stages"] | {} == {
        "acquired": 4,
        "structurally_compatible": 2,
        "executable": 2,
        "executed": 1,
        "evaluated": 1,
        "included": 1,
        "excluded": 1,
    }


def test_the_summary_counts_groups_clusters_categories_and_exposure_not_participations(tmp_path):
    ev, views = _setup(tmp_path)
    summary = ul.build(ev, views)["summary"]
    assert summary["total"]["groups"] == 4 and summary["total"]["clusters"] == 3
    assert summary["participations"] == 5
    assert summary["total"]["previous_exposure"] == 1
    assert summary["by_category"]["C3"]["groups"] == 2
    assert summary["by_category"]["C3"]["stage_clusters"]["executable"] == 1  # ga and gd linked
    assert summary["by_protocol"]["P-TS"]["stages"]["executable"] == 2
    assert summary["evidence_levels"] == {"adapter_dry_run": 2, "none": 2}


def test_batch_detectors_and_metrics_are_listed_only_for_an_accepted_group(tmp_path):
    ev, views = _setup(tmp_path)
    groups = ul.build(ev, views)["groups"]
    assert groups["ga"]["detectors"]["temporal_batch"] and groups["ga"]["metrics"]["temporal_batch"]
    assert groups["gb"]["detectors"]["temporal_batch"] == []
    assert groups["ga"]["detectors"]["unit_level"] == []  # no runner yet
    assert groups["ga"]["fault_operators"]["unit_level"] == {"P-TS": ["m-P-TS"]}


def test_main_is_deterministic_and_reads_the_optional_records(tmp_path, capsys):
    ev, views = _setup(tmp_path)
    exclusions = tmp_path / "x.json"
    exclusions.write_text(json.dumps({"gb": "too small"}))
    argv = ["--evidence", str(ev), "--views", str(views), "--exclusions", str(exclusions)]
    assert ul.main(argv) == 0
    first = capsys.readouterr().out
    out = tmp_path / "ledger.json"
    assert ul.main([*argv, "--output", str(out)]) == 0
    assert out.read_text() == first
    assert json.loads(first)["groups"]["gb"]["stages"]["excluded"]["reason"] == "too small"


def test_a_group_entry_is_exactly_the_documented_record_for_accepted_and_refused_groups(tmp_path):
    ev, views = _setup(tmp_path)
    groups = ul.build(ev, views)["groups"]
    assert groups["ga"] == {
        "categories": ["C3"],
        "cluster": "ga",
        "detectors": {"temporal_batch": list(pb.DETECTORS), "unit_level": []},
        "dry_run": {
            "columns": 4,
            "file": "t.csv",
            "plan": {
                "batch_rows": 24,
                "batches": {"reference": 40, "test": 40, "validation": 20},
                "evaluations": 2640,
            },
            "reason": "",
            "rows": 2400,
            "status": "ok",
        },
        "evidence_level": "adapter_dry_run",
        "fault_operators": {
            "temporal_batch": list(pb.MECHANISMS),
            "unit_level": {"P-TS": ["m-P-TS"]},
        },
        "label_origin": ["controlled_injection"],
        "limitations": ["unit-level protocol P-TS has no registry-driven runner"],
        "local_view_available": True,
        "metrics": {
            "temporal_batch": ["recall", "false_alert_rate", "roc_auc", "ap"],
            "unit_level": ["tp", "fp", "fn"],
        },
        "natural_labels": False,
        "participations": [{"category": "C3", "detection_unit": "time_window", "protocol": "P-TS"}],
        "paths": [
            {"dry_run": "ok", "path": "temporal_batch", "status": "registered"},
            {"dry_run": "not_available", "path": "unit_level", "status": "no_runner"},
        ],
        "previous_exposure": True,
        "protocols": ["P-TS"],
        "remaining_work": [],
        "stages": {
            "acquired": {"reason": "", "status": "yes"},
            "evaluated": {"reason": "not executed", "status": "no"},
            "excluded": {"reason": "", "status": "no"},
            "executable": {"reason": "", "status": "yes"},
            "executed": {"reason": "no registry-driven scientific run is recorded", "status": "no"},
            "included": {"reason": "not evaluated", "status": "no"},
            "structurally_compatible": {"reason": "", "status": "yes"},
        },
        "views": ["va"],
    }
    assert groups["gb"] == {
        "categories": ["C1"],
        "cluster": "gb",
        "detectors": {"temporal_batch": [], "unit_level": []},
        "dry_run": None,
        "evidence_level": "none",
        "fault_operators": {"temporal_batch": [], "unit_level": {"P-TAB": ["m-P-TAB"]}},
        "label_origin": ["controlled_injection"],
        "limitations": [
            "only 1 continuous columns",
            "unit-level protocol P-TAB has no registry-driven runner",
        ],
        "local_view_available": True,
        "metrics": {"temporal_batch": [], "unit_level": ["tp", "fp", "fn"]},
        "natural_labels": False,
        "participations": [{"category": "C1", "detection_unit": "row", "protocol": "P-TAB"}],
        "paths": [
            {"dry_run": "not_applicable", "path": "temporal_batch", "status": "registered"},
            {"dry_run": "not_available", "path": "unit_level", "status": "no_runner"},
        ],
        "previous_exposure": False,
        "protocols": ["P-TAB"],
        "remaining_work": [
            "repair the structural compatibility: fewer units than the minimum",
            "registry-driven unit-level runner for P-TAB (loader, partitions, detectors)",
            "provide a timestamped numeric table for the batch unit (see the limitations)",
        ],
        "stages": {
            "acquired": {"reason": "", "status": "yes"},
            "evaluated": {"reason": "not executed", "status": "no"},
            "excluded": {"reason": "", "status": "no"},
            "executable": {
                "reason": "no registered path accepts the group: only 1 continuous columns",
                "status": "no",
            },
            "executed": {"reason": "no registry-driven scientific run is recorded", "status": "no"},
            "included": {"reason": "not evaluated", "status": "no"},
            "structurally_compatible": {"reason": "fewer units than the minimum", "status": "no"},
        },
        "views": ["vb"],
    }
    assert groups["gc"] == {
        "categories": ["C1", "C5"],
        "cluster": "gc",
        "detectors": {"temporal_batch": [], "unit_level": []},
        "dry_run": None,
        "evidence_level": "none",
        "fault_operators": {
            "temporal_batch": [],
            "unit_level": {"P-REL": ["m-P-REL"], "P-TAB": ["m-P-TAB"]},
        },
        "label_origin": ["controlled_injection"],
        "limitations": [
            "view vc is not built locally",
            "unit-level protocol P-REL has no registry-driven runner",
            "unit-level protocol P-TAB has no registry-driven runner",
            "relational_load: unsupported: the unit has no approved definition",
        ],
        "local_view_available": False,
        "metrics": {"temporal_batch": [], "unit_level": ["tp", "fp", "fn"]},
        "natural_labels": False,
        "participations": [
            {"category": "C1", "detection_unit": "row", "protocol": "P-TAB"},
            {"category": "C5", "detection_unit": "relationship", "protocol": "P-REL"},
        ],
        "paths": [
            {"dry_run": "not_applicable", "path": "temporal_batch", "status": "registered"},
            {"dry_run": "not_available", "path": "unit_level", "status": "no_runner"},
        ],
        "previous_exposure": False,
        "protocols": ["P-REL", "P-TAB"],
        "remaining_work": [
            "repair the structural compatibility: view not built locally",
            "registry-driven unit-level runner for P-REL (loader, partitions, detectors)",
            "registry-driven unit-level runner for P-TAB (loader, partitions, detectors)",
            "provide a timestamped numeric table for the batch unit (see the limitations)",
            "approve and implement the relational_load unit (no approved definition)",
        ],
        "stages": {
            "acquired": {"reason": "", "status": "yes"},
            "evaluated": {"reason": "not executed", "status": "no"},
            "excluded": {"reason": "", "status": "no"},
            "executable": {
                "reason": "no registered path accepts the group: view vc is not built locally",
                "status": "no",
            },
            "executed": {"reason": "no registry-driven scientific run is recorded", "status": "no"},
            "included": {"reason": "not evaluated", "status": "no"},
            "structurally_compatible": {"reason": "view not built locally", "status": "no"},
        },
        "views": ["vc"],
    }


def test_a_dry_run_failure_names_the_error_class_and_message(tmp_path):
    ev, views = _setup(tmp_path)
    audit = json.loads((ev / "batch_eligibility.json").read_text())
    audit["groups"]["ga"]["table"]["batches"] += 1
    (ev / "batch_eligibility.json").write_text(json.dumps(audit))
    dry = ul.build(ev, views)["groups"]["ga"]["dry_run"]
    assert dry == {"status": "failed", "reason": "ValueError: 100 batches rebuilt, 101 audited"}


def test_the_ledger_header_names_stages_levels_and_paths_and_the_parser_has_safe_defaults(tmp_path):
    ev, views = _setup(tmp_path)
    ledger = ul.build(ev, views)
    assert sorted(ledger) == ["groups", "levels", "paths", "stages", "summary"]
    assert ledger["stages"] == [
        "acquired", "structurally_compatible", "executable", "executed", "evaluated",
        "included", "excluded",
    ]  # fmt: skip
    assert ledger["levels"][0] == "metadata_only" and ledger["levels"][-1] == "scientific_execution"
    assert ledger["paths"]["unit_level"]["synthetic_end_to_end"] is None
    assert ledger["paths"]["temporal_batch"]["synthetic_end_to_end"].startswith("research/tests/")
    args = ul.build_parser().parse_args([])
    assert args.evidence == ul.EVIDENCE and args.views == ul.sc.VIEWS
    assert args.executions is None and args.exclusions is None and args.output is None
    assert args.no_dry_run is False
    assert ul.build_parser().parse_args(["--no-dry-run"]).no_dry_run is True


def test_building_the_ledger_fits_no_detector_and_injects_no_fault(tmp_path, monkeypatch):
    ev, views = _setup(tmp_path)

    def refuse(*_args, **_kwargs):
        raise AssertionError("the ledger must not run a detector or a fault")

    for name in ("run_source", "apply_fault", "fit_learned", "detector_scores", "deliver"):
        monkeypatch.setattr(pb, name, refuse)
    assert ul.build(ev, views)["groups"]["ga"]["stages"]["executable"]["status"] == "yes"


def test_each_negative_stage_gives_the_reason_of_the_stage_before_it(tmp_path):
    ev, views = _setup(tmp_path)
    ran = ul.build(ev, views, executions={"ga": {"executed": True}})["groups"]["ga"]["stages"]
    assert ran["executed"] == {"status": "yes", "reason": ""}
    assert ran["evaluated"] == {"status": "no", "reason": "evaluation failed"}
    assert ran["included"] == {"status": "no", "reason": "not evaluated"}
    scored = {"executed": True, "evaluated": True}
    left = ul.build(ev, views, executions={"ga": scored})["groups"]["ga"]["stages"]["included"]
    assert left == {"status": "no", "reason": "left out of the analysis"}


def test_the_executable_reason_lists_every_audit_reason_or_says_not_attempted(tmp_path):
    ev, views = _setup(tmp_path)
    audit = json.loads((ev / "batch_eligibility.json").read_text())
    audit["groups"]["gb"]["reasons"] = ["only 1 continuous columns", "no parseable time column"]
    (ev / "batch_eligibility.json").write_text(json.dumps(audit))
    groups = ul.build(ev, views)["groups"]
    assert groups["gb"]["stages"]["executable"]["reason"] == (
        "no registered path accepts the group: only 1 continuous columns; no parseable time column"
    )
    skipped = ul.build(ev, views, attempt=False)["groups"]["ga"]["stages"]["executable"]
    assert skipped == {
        "status": "no",
        "reason": "no registered path accepts the group: not attempted",
    }


def test_an_empty_partition_fails_the_dry_run(tmp_path, monkeypatch):
    ev, views = _setup(tmp_path)
    plan = ul.ru.plan_group
    monkeypatch.setattr(
        ul.ru,
        "plan_group",
        lambda entry: {**plan(entry), "batches": {"reference": 1, "validation": 1, "test": 0}},
    )
    dry = ul.build(ev, views)["groups"]["ga"]["dry_run"]
    assert dry == {
        "status": "failed",
        "reason": "ValueError: an empty reference, validation or test partition",
    }


def test_the_remaining_work_is_counted_most_frequent_first_then_by_name(tmp_path):
    ev, views = _setup(tmp_path)
    work = ul.build(ev, views)["summary"]["remaining_work"]
    assert list(work.items()) == [
        ("provide a timestamped numeric table for the batch unit (see the limitations)", 2),
        ("registry-driven unit-level runner for P-TAB (loader, partitions, detectors)", 2),
        ("approve and implement the relational_load unit (no approved definition)", 1),
        ("registry-driven unit-level runner for P-REL (loader, partitions, detectors)", 1),
        ("repair the structural compatibility: fewer units than the minimum", 1),
        ("repair the structural compatibility: view not built locally", 1),
    ]


def test_natural_labels_are_counted_per_category_and_in_total(tmp_path):
    ev, views = _setup(tmp_path)
    facts = json.loads((ev / "readiness_facts.json").read_text())
    facts["facts"]["a"]["natural_labels"] = ["x"]
    (ev / "readiness_facts.json").write_text(json.dumps(facts))
    summary = ul.build(ev, views)["summary"]
    assert summary["total"]["natural_labels"] == 1
    assert summary["by_category"]["C3"]["natural_labels"] == 1
    assert summary["by_category"]["C1"]["natural_labels"] == 0
    assert summary["by_protocol"]["P-TS"]["natural_labels"] == 1


def test_main_passes_the_records_and_the_dry_run_switch_and_prints_sorted_indented_json(
    tmp_path, capsys
):
    ev, views = _setup(tmp_path)
    executions = tmp_path / "e.json"
    executions.write_text(json.dumps({"ga": {"executed": True}}))
    argv = ["--evidence", str(ev), "--views", str(views), "--executions", str(executions)]
    assert ul.main(argv) == 0
    text = capsys.readouterr().out
    ledger = json.loads(text)
    assert text == json.dumps(ledger, indent=1, sort_keys=True) + "\n"
    assert ledger["groups"]["ga"]["stages"]["executed"]["status"] == "yes"
    with pytest.raises(ValueError, match="without a successful dry run"):
        ul.main([*argv, "--no-dry-run"])  # an execution record needs the dry run it rests on
    assert ul.main(["--evidence", str(ev), "--views", str(views), "--no-dry-run"]) == 0
    skipped = json.loads(capsys.readouterr().out)
    assert skipped["groups"]["gd"]["dry_run"] is None
    assert skipped["groups"]["gd"]["stages"]["executable"]["status"] == "no"


def test_a_group_in_two_categories_keeps_the_protocol_of_each_participation(tmp_path):
    ev, views = _setup(tmp_path)
    assert ul.registry_participations(ev)["gc"] == {"C1": "P-TAB", "C5": "P-REL"}
    group = ul.build(ev, views)["groups"]["gc"]
    assert group["protocols"] == ["P-REL", "P-TAB"]
    assert [
        (p["category"], p["protocol"], p["detection_unit"]) for p in group["participations"]
    ] == [
        ("C1", "P-TAB", "row"),
        ("C5", "P-REL", "relationship"),
    ]
    by_protocol = ul.build(ev, views)["summary"]["by_protocol"]
    assert by_protocol["P-TAB"]["groups"] == 2 and by_protocol["P-REL"]["groups"] == 1


def test_a_participation_without_a_fact_or_with_two_protocols_is_refused(tmp_path):
    ev, _views = _setup(tmp_path)
    facts = json.loads((ev / "readiness_facts.json").read_text())
    facts["facts"]["f"] = _fact("gc", "vc", "P-TS")
    facts["facts"]["f"]["extra"] = 1
    (ev / "readiness_facts.json").write_text(json.dumps(facts))
    readiness = json.loads((ev / "readiness.json").read_text())
    readiness["datasets"].append({"id": "f", "stratum": "C5"})  # C5 of gc now has two protocols
    (ev / "readiness.json").write_text(json.dumps(readiness))
    with pytest.raises(ValueError, match=r"^participations with several protocols: \['gc/C5'\]$"):
        ul.registry_participations(ev)
    del facts["facts"]["f"], facts["facts"]["e"]  # gc/C1 loses its only fact
    (ev / "readiness_facts.json").write_text(json.dumps(facts))
    with pytest.raises(ValueError, match=r"^participations without a protocol fact: \['gc/C1'\]$"):
        ul.registry_participations(ev)


def test_provisional_units_are_listed_once_over_all_protocols_of_a_group():
    entry = {"eligible": False, "reasons": ["no parseable time column"]}
    units = ul.provisional_units(["P-REL", "P-SEQ", "P-TAB"], entry)
    assert [u["unit"] for u in units] == ["event_window", "relational_load"]
    assert all(u["reason"].startswith("unsupported") for u in units)
    assert ul.provisional_units(["P-TAB"], entry) == []
