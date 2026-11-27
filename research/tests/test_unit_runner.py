"""Synthetic execution of the five unit-level protocol runners (#135, #137, #138, #139)."""

import copy
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compatibility_model as cm  # noqa: E402
import obs_failures as of  # noqa: E402
import unit_runner as ur  # noqa: E402

PROTOCOLS = sorted(ur.RUNNERS)


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_every_runner_passes_its_contract_on_its_synthetic_fixture(protocol):
    run = ur.execute(ur.fixture(protocol, 3), 3, 3)
    assert run.protocol == protocol and run.synthetic is True
    assert all(run.checks.values()) and set(run.checks) == {
        "truth_inside_units",
        "exactly_the_truth_changed",
        "input_unmodified",
        "deterministic",
        "fault_count",
    }
    assert len(run.truth) == 3 and run.units > 3


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_the_unit_and_its_status_come_from_the_compatibility_model(protocol):
    run = ur.execute(ur.fixture(protocol, 0), 2, 0)
    assert run.unit == ur.RUNNERS[protocol].unit
    assert run.unit_status == cm.UNITS[run.unit][1] == cm.PROTOCOL_DEFINED


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_a_run_is_deterministic_and_the_seed_changes_the_faults(protocol):
    first = ur.execute(ur.fixture(protocol, 5), 3, 5)
    assert first == ur.execute(ur.fixture(protocol, 5), 3, 5)
    others = {tuple(ur.execute(ur.fixture(protocol, 5), 3, s).truth) for s in range(8)}
    assert len(others) > 1


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_a_scientific_run_is_refused_whatever_the_fixture(protocol):
    with pytest.raises(ur.Refused, match="experiment freeze is active"):
        ur.execute(ur.fixture(protocol, 0), 1, 0, scientific=True)


def test_only_a_synthetic_fixture_can_be_built():
    with pytest.raises(ur.Refused, match="only synthetic fixtures are accepted, not 'real'"):
        ur.Fixture("P-TAB", pd.DataFrame(), 0, origin="real")


def test_an_unknown_protocol_or_object_is_inapplicable():
    with pytest.raises(of.InapplicableFailure, match="no runner for protocol 'P-XYZ'"):
        ur.fixture("P-XYZ", 0)
    with pytest.raises(of.InapplicableFailure):
        ur.execute(ur.Fixture("P-XYZ", None, 0), 1, 0)
    with pytest.raises(of.InapplicableFailure):
        ur.execute("not a fixture", 1, 0)  # type: ignore[arg-type]


def test_zero_faults_is_a_data_quality_failure():
    with pytest.raises(of.DataQualityFailure, match="at least one fault"):
        ur.execute(ur.fixture("P-TAB", 0), 0, 0)


@pytest.mark.parametrize(
    ("protocol", "too_many"), [("P-TAB", 500), ("P-SEQ", 500), ("P-NEST", 500)]
)
def test_a_precondition_that_does_not_hold_is_reported_as_inapplicable(protocol, too_many):
    with pytest.raises(of.InapplicableFailure, match="precondition"):
        ur.execute(ur.fixture(protocol, 0), too_many, 0)


def test_a_relational_fixture_reports_its_natural_orphans_apart_from_the_truth():
    run = ur.execute(ur.fixture("P-REL", 2), 4, 2)
    assert run.baseline == 2
    assert not {"0", "1"} & set(run.truth)


@pytest.mark.parametrize("protocol", [p for p in PROTOCOLS if p != "P-REL"])
def test_the_other_fixtures_have_no_natural_baseline(protocol):
    assert ur.execute(ur.fixture(protocol, 2), 2, 2).baseline == 0


def test_the_time_series_unit_is_a_window_of_one_series():
    run = ur.execute(ur.fixture("P-TS", 4), 2, 4)
    assert all(t.startswith("('s0', ") for t in run.truth)
    assert run.units == 2 * 12


def test_the_nested_unit_is_a_record_path_pair():
    run = ur.execute(ur.fixture("P-NEST", 4), 2, 4)
    assert all(t.endswith(", 'meta.owner.name')") for t in run.truth)


def test_a_broken_operator_is_reported_with_the_checks_that_failed(monkeypatch):
    runner = ur.RUNNERS["P-TAB"]

    def sloppy(data, k, seed):
        out, rows = runner.inject(data, k, seed)
        out = out.copy()
        out.loc[out.index[0], "amount"] = -1.0
        return out, rows

    broken = ur.Runner(**{**runner.__dict__, "inject": sloppy})
    monkeypatch.setitem(ur.RUNNERS, "P-TAB", broken)
    with pytest.raises(of.ProcessingFailure, match="^P-TAB contract broken: "):
        ur.execute(ur.fixture("P-TAB", 0), 2, 0)


def test_an_operator_that_modifies_its_input_is_caught(monkeypatch):
    runner = ur.RUNNERS["P-SEQ"]

    def mutating(data, k, seed):
        out, truth = runner.inject(data, k, seed)
        data[next(iter(data))].append("extra")
        return out, truth

    monkeypatch.setitem(ur.RUNNERS, "P-SEQ", ur.Runner(**{**runner.__dict__, "inject": mutating}))
    with pytest.raises(of.ProcessingFailure, match="input_unmodified"):
        ur.execute(ur.fixture("P-SEQ", 0), 2, 0)


def test_a_nondeterministic_operator_is_caught(monkeypatch):
    runner = ur.RUNNERS["P-NEST"]
    calls = []

    def drifting(data, k, seed):
        calls.append(1)
        return runner.inject(data, k, seed + len(calls))

    monkeypatch.setitem(ur.RUNNERS, "P-NEST", ur.Runner(**{**runner.__dict__, "inject": drifting}))
    with pytest.raises(of.ProcessingFailure, match="deterministic"):
        ur.execute(ur.fixture("P-NEST", 0), 2, 0)


def test_coverage_is_computed_from_the_registry_protocols_not_from_a_fixed_list():
    registry = {
        "P-TAB": {"detection_unit": "row"},
        "P-REL": {"detection_unit": "relational_load"},
        "P-NEW": {"detection_unit": "x"},
    }
    assert ur.coverage(registry) == {
        "P-NEW": "no runner",
        "P-REL": "unit mismatch: runner relationship, registry relational_load",
        "P-TAB": "runner",
    }


def test_the_committed_registry_protocols_all_have_a_runner_for_their_detection_unit():
    root = Path(__file__).resolve().parents[2]
    protocols = json.loads(
        (root / "verification/evidence/dataset_registry_v2/anomaly_protocols.json").read_text()
    )["protocols"]
    assert set(ur.coverage(protocols).values()) == {"runner"}


def test_the_fixtures_do_not_mention_ground_truth_vocabulary():
    import obs_redaction as orr

    for protocol in PROTOCOLS:
        data = ur.fixture(protocol, 0).data
        names = set()
        if isinstance(data, pd.DataFrame):
            names |= set(data.columns)
        elif isinstance(data, dict):
            names |= {str(k) for k in data}
            for value in data.values():
                if isinstance(value, pd.DataFrame):
                    names |= set(value.columns)
        assert not [n for n in names if orr.GROUND_TRUTH_NAME.search(str(n))]


def test_report_runs_every_protocol_and_main_prints_it(capsys):
    assert ur.main(["--seed", "1", "--faults", "2"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["synthetic"] is True
    assert [r["protocol"] for r in printed["runs"]] == PROTOCOLS
    assert printed == json.loads(json.dumps(ur.report(1, 2)))


def test_the_parser_defaults():
    args = ur.build_parser().parse_args([])
    assert (args.seed, args.faults) == (0, 3)


def test_execute_does_not_change_the_fixture():
    item = ur.fixture("P-REL", 1)
    before = copy.deepcopy(item.data)
    ur.execute(item, 3, 1)
    assert all(item.data[k].equals(before[k]) for k in before)


def test_the_run_records_the_seed_and_the_fault_count_it_was_given():
    run = ur.execute(ur.fixture("P-TAB", 1), 3, 9)
    assert (run.seed, run.faults) == (9, 3)
    assert ur.execute(ur.fixture("P-TAB", 1), 1, 0).faults == 1


def test_every_unit_may_be_a_fault():
    run = ur.execute(ur.fixture("P-TAB", 0), 80, 0)
    assert run.units == 80 and len(run.truth) == 80


def test_the_fixtures_have_the_documented_shape():
    tab = ur.fixture("P-TAB", 0).data
    assert list(tab.columns) == ["amount", "ident"] and len(tab) == 80
    assert tab["amount"].between(1, 100).all()
    ts = ur.fixture("P-TS", 0).data
    assert list(ts.columns) == ["s0", "s1"] and len(ts) == 12 * ur.WINDOW
    seq = ur.fixture("P-SEQ", 0).data
    assert 20 <= len(seq) < 30 and list(seq)[0] == "case-00"
    assert seq["case-04"] == ["create", "validate", "load", "verify", "publish", "close-1"]
    assert {t[-1] for t in seq.values()} == {"close-0", "close-1", "close-2"}
    rel = ur.fixture("P-REL", 0).data
    assert list(rel["parent"]["parent_id"]) == list(range(1, 21))
    assert len(rel["child"]) == 60 and list(rel["child"]["parent_id"][:2]) == [900, 901]
    nest = ur.fixture("P-NEST", 0).data
    assert len(nest) == 40
    assert nest[3]["meta"]["owner"] == {"name": "o3", "tags": [1, 2]}
    assert all(0 <= r["meta"]["n"] < 9 for r in nest)


def test_the_fixture_remembers_its_seed():
    assert ur.fixture("P-TAB", 11).seed == 11


def test_the_operators_apply_the_documented_changes():
    tab = ur.fixture("P-TAB", 0).data
    out, rows = ur.RUNNERS["P-TAB"].inject(tab, 2, 0)
    assert all(out["amount"].iloc[i] == tab["amount"].iloc[i] * 5.0 for i in rows)
    ts = ur.fixture("P-TS", 0).data
    out, windows = ur.RUNNERS["P-TS"].inject(ts, 1, 0)
    (_, w) = windows[0]
    span = slice(w * ur.WINDOW, (w + 1) * ur.WINDOW)
    shift = (out["s0"].iloc[span] - ts["s0"].iloc[span]).to_numpy()
    assert shift == pytest.approx([4.0] * ur.WINDOW)
    seq = ur.fixture("P-SEQ", 0).data
    out, names = ur.RUNNERS["P-SEQ"].inject(seq, 1, 7)
    swapped, original = out[names[0]], seq[names[0]]
    assert swapped[2:4] == original[2:4][::-1] and swapped[:2] == original[:2]


def test_the_run_emits_a_started_and_a_completed_event_with_the_unit_count(caplog):
    caplog.set_level("INFO", logger="etl.unit_runner")
    run = ur.execute(ur.fixture("P-REL", 0), 2, 0)
    events = [(r.getMessage(), r.stage, getattr(r, "rows", None)) for r in caplog.records]
    assert events == [
        ("stage.started", "unit_runner.P-REL", None),
        ("stage.completed", "unit_runner.P-REL", run.units),
    ]


def test_two_broken_checks_are_both_named_in_the_failure(monkeypatch):
    runner = ur.RUNNERS["P-TAB"]

    def sloppy(data, k, seed):
        out, rows = runner.inject(data, k, seed)
        out = out.copy()
        out.loc[out.index[0], "amount"] = -1.0
        data.loc[data.index[1], "ident"] = -5
        return out, rows

    monkeypatch.setitem(ur.RUNNERS, "P-TAB", ur.Runner(**{**runner.__dict__, "inject": sloppy}))
    with pytest.raises(of.ProcessingFailure) as error:
        ur.execute(ur.fixture("P-TAB", 0), 2, 0)
    assert (
        str(error.value)
        == "P-TAB contract broken: exactly_the_truth_changed, input_unmodified, deterministic"
    )


def test_an_operator_with_the_same_truth_but_a_different_result_is_not_deterministic(monkeypatch):
    runner = ur.RUNNERS["P-TAB"]
    calls = []

    def drifting(data, k, seed):
        out, rows = runner.inject(data, k, seed)
        calls.append(1)
        if len(calls) > 1:
            out = out.copy()
            out.loc[out.index[rows[0]], "amount"] += 1.0
        return out, rows

    monkeypatch.setitem(ur.RUNNERS, "P-TAB", ur.Runner(**{**runner.__dict__, "inject": drifting}))
    with pytest.raises(of.ProcessingFailure, match="deterministic"):
        ur.execute(ur.fixture("P-TAB", 0), 2, 0)


def test_same_compares_frames_and_tables_by_content_and_keys():
    a = {"x": pd.DataFrame({"v": [1]}), "y": pd.DataFrame({"v": [2]})}
    assert ur._same(a, {"x": a["x"].copy(), "y": a["y"].copy()})
    assert not ur._same(a, {"x": a["x"].copy(), "z": a["y"].copy()})
    assert not ur._same(a, {"x": a["x"].copy(), "y": pd.DataFrame({"v": [3]})})
    assert ur._same(a["x"], a["x"].copy()) and not ur._same(a["x"], a["y"])
    assert ur._same({"k": [1]}, {"k": [1]}) and not ur._same({"k": [1]}, {"k": [2]})
    assert ur._same({}, {})


def test_the_command_prints_the_report_indented_with_sorted_keys(capsys):
    ur.main(["--faults", "1"])
    text = capsys.readouterr().out
    assert text.startswith('{\n "runs": [\n  {\n   "baseline": ')
    assert text == json.dumps(ur.report(0, 1), indent=1, sort_keys=True) + "\n"


def test_the_parser_describes_itself_with_the_first_line_of_the_module_documentation():
    assert ur.build_parser().description == (
        "Registry-driven synthetic runner of the unit-level protocols (#135, #137, #138, #139)."
    )
