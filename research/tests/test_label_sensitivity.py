"""Alternative anomaly-class rules: label derivation, per-problem runs, job list and the CLI."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import label_sensitivity as ls  # noqa: E402
import uci_loader as ul  # noqa: E402

META = {
    "name": "Toy",
    "tasks": ["Classification"],
    "target_col": ["t"],
    "variables": [
        {"name": "t", "role": "Target"},
        {"name": "id", "role": "ID"},
        {"name": "f1", "role": "Feature"},
    ],
}


def _frame(**counts):
    """One row per class member in the order of ``counts``; ``row`` is the original position."""
    classes = [c for c, k in counts.items() for _ in range(k)]
    n = len(classes)
    rng = np.random.default_rng(7)
    return pd.DataFrame(
        {
            "t": classes,
            "id": np.arange(n),
            "f1": rng.normal(size=n),
            "row": np.arange(n),
        }
    )


def test_the_rules_are_the_five_fixed_by_the_protocol_and_the_seeds_are_three():
    assert ls.RULES == {
        "R1": ("rarest", 0.02),
        "R2": ("rarest", 0.05),
        "R3": ("rarest", None),
        "R4": ("second_rarest", 0.10),
        "R5": ("all_minority", 0.10),
    }
    assert ls.SEEDS == (42, 1, 2)


def test_a_table_that_is_not_a_classification_task_has_no_labels():
    with pytest.raises(ul.NoLabels, match=r"^not a classification task$"):
        ls.derive_rule(_frame(A=100, B=30), {**META, "tasks": ["Regression"]}, "R3")
    with pytest.raises(ul.NoLabels, match=r"^not a classification task$"):
        ls.derive_rule(_frame(A=100, B=30), {**META, "tasks": None}, "R3")


def test_a_single_class_has_no_labels_under_any_rule():
    with pytest.raises(ul.NoLabels, match=r"^1 classes: rule R3 needs more$"):
        ls.derive_rule(_frame(A=100), META, "R3")


def test_rules_that_remove_or_group_classes_need_three_classes():
    for rule in ("R4", "R5"):
        with pytest.raises(ul.NoLabels, match=rf"^2 classes: rule {rule} needs more$"):
            ls.derive_rule(_frame(A=100, B=30), META, rule)
    ls.derive_rule(_frame(A=100, B=30, C=25), META, "R4")
    ls.derive_rule(_frame(A=100, B=30, C=25), META, "R5")
    ls.derive_rule(_frame(A=100, B=30), META, "R3")


def test_too_few_anomalies_are_refused_at_nineteen_and_accepted_at_twenty():
    with pytest.raises(ul.NoLabels, match=r"^19 anomalies under rule R3 \(at least 20\)$"):
        ls.derive_rule(_frame(A=200, B=19), META, "R3")
    features, labels, info = ls.derive_rule(_frame(A=200, B=20), META, "R3")
    assert int(labels.sum()) == 20 and info["anomalies"] == 20


def test_rarest_with_a_natural_rate_keeps_every_row_and_labels_the_rarest_class():
    frame = _frame(A=180, B=20)
    features, labels, info = ls.derive_rule(frame, META, "R3")
    assert info == {
        "rule": "R3",
        "anomaly_class": "B",
        "natural_rate": 0.1,
        "kind": "natural",
        "rows": 200,
        "anomalies": 20,
    }
    assert list(features.columns) == ["f1", "row"]
    assert list(features["row"]) == list(range(200))
    assert labels.dtype == int and labels.tolist() == [0] * 180 + [1] * 20


def test_unlabelled_targets_are_dropped_before_the_classes_are_counted():
    frame = _frame(A=180, B=20)
    frame.loc[[0, 1, 2], "t"] = np.nan
    features, labels, info = ls.derive_rule(frame, META, "R3")
    assert info["rows"] == 197 and info["anomalies"] == 20
    assert features["row"].iloc[0] == 3
    assert len(features) == len(labels) == 197
    assert list(features.index) == list(range(197))


def test_numeric_class_codes_are_ranked_as_text_classes():
    frame = _frame(A=180, B=20)
    frame["t"] = frame["t"].map({"A": 1, "B": 2})
    _, labels, info = ls.derive_rule(frame, META, "R3")
    assert info["anomaly_class"] == "2" and int(labels.sum()) == 20


def test_a_rate_above_the_target_is_downsampled_with_the_fixed_seed():
    frame = _frame(A=380, B=20)
    features, labels, info = ls.derive_rule(frame, META, "R1")
    # 380 normal rows; round(380 * 0.02 / 0.98) = 8 anomalies are kept
    assert info["kind"] == "downsampled"
    assert info["natural_rate"] == 0.05
    assert info["rows"] == 388 and info["anomalies"] == 8
    assert int(labels.sum()) == 8 and len(labels) == 388
    kept = features["row"].to_numpy()
    assert kept[:380].tolist() == list(range(380))
    assert kept[labels == 1].tolist() == ANOMALY_ROWS_R1
    assert kept.tolist() == sorted(kept.tolist())


def test_a_rate_exactly_at_the_target_is_not_downsampled():
    features, labels, info = ls.derive_rule(_frame(A=380, B=20), META, "R2")
    assert info["natural_rate"] == 0.05 and info["kind"] == "natural"
    assert info["rows"] == 400 and info["anomalies"] == 20


def test_a_rate_below_the_target_keeps_the_natural_share():
    _, _, info = ls.derive_rule(_frame(A=390, B=20), META, "R2")
    assert info["kind"] == "natural" and info["rows"] == 410


def test_second_rarest_drops_the_rarest_class_and_labels_the_second_one():
    frame = _frame(A=300, B=30, C=20)
    features, labels, info = ls.derive_rule(frame, META, "R4")
    assert info["anomaly_class"] == "B" and info["kind"] == "natural"
    assert info["rows"] == 330 and info["anomalies"] == 30
    assert info["natural_rate"] == pytest.approx(30 / 330)
    assert "C" not in set(frame.loc[features["row"], "t"])
    assert labels.sum() == 30


def test_second_rarest_above_the_target_is_downsampled_without_the_rarest_class():
    frame = _frame(A=300, B=40, C=20)
    features, labels, info = ls.derive_rule(frame, META, "R4")
    # pool = 300 normal rows, round(300 * 0.1 / 0.9) = 33 anomalies
    assert info["kind"] == "downsampled" and info["anomaly_class"] == "B"
    assert info["natural_rate"] == pytest.approx(40 / 340)
    assert info["rows"] == 333 and info["anomalies"] == 33
    assert set(frame.loc[features["row"], "t"]) == {"A", "B"}


def test_all_minority_labels_every_class_but_the_most_frequent():
    frame = _frame(A=500, B=25, C=25)
    features, labels, info = ls.derive_rule(frame, META, "R5")
    assert info["anomaly_class"] == "all but A" and info["kind"] == "natural"
    assert info["rows"] == 550 and info["anomalies"] == 50
    assert set(frame.loc[features["row"][labels == 1], "t"]) == {"B", "C"}
    _, labels, info = ls.derive_rule(_frame(A=300, B=25, C=25), META, "R5")
    assert info["kind"] == "downsampled" and info["anomalies"] == 33
    assert info["rows"] == 333


def _csv(tmp_path, frame, name="1.csv"):
    path = tmp_path / name
    frame.to_csv(path, index=False)
    return path


def _job(path, rule="R3", meta=META):
    return {"problem": "uci:1", "rule": rule, "meta": meta, "path": str(path)}


def test_run_job_reports_a_problem_without_labels_as_not_applicable(tmp_path):
    path = _csv(tmp_path, _frame(A=100))
    assert ls.run_job(_job(path)) == {
        "problem": "uci:1",
        "rule": "R3",
        "not_applicable": "1 classes: rule R3 needs more",
    }


def test_run_job_records_a_failing_run_instead_of_dropping_it(tmp_path):
    path = _csv(tmp_path, _frame(A=180, B=20))
    result = ls.run_job(_job(path), methods=["not_a_detector"])
    assert result["problem"] == "uci:1" and result["rule"] == "R3"
    assert result["failed"].startswith("ValueError(") and "not_a_detector" in result["failed"]
    assert set(result) == {"problem", "rule", "failed"}


def test_run_job_archives_the_derivation_facts_with_the_detector_results(tmp_path):
    frame = _frame(A=180, B=20)
    result = ls.run_job(_job(_csv(tmp_path, frame)), methods=["zscore"])
    assert result["problem"] == "uci:1" and result["rule"] == "R3"
    assert result["name"] == "Toy"
    assert result["rows"] == 200 and result["prevalence"] == pytest.approx(0.1)
    assert result["features"] == 2
    assert result["report"]["rule"] == "R3" and result["report"]["anomaly_class"] == "B"
    assert result["report"]["rows_in"] == 200
    assert result["seeds"] == [42, 1, 2]
    assert list(result["metrics"]) == ["zscore"] and len(result["metrics"]["zscore"]) == 3
    assert {"skipped", "errors"} <= set(result)


def test_jobs_pair_every_labelled_problem_with_every_requested_rule(tmp_path):
    registry, pool = tmp_path / "registry", tmp_path / "pool"
    registry.mkdir()
    (registry / "uci_curated.json").write_text(
        json.dumps({"kept": [{"uci_id": 1, "name": "one"}, {"uci_id": 2, "name": "two"}]})
    )
    (registry / "uci_pool.json").write_text(
        json.dumps(
            {
                "rows": [
                    {"uci_id": 1, "roles": ["labelled", "other"]},
                    {"uci_id": 2, "roles": ["flat"]},
                ]
            }
        )
    )
    got = ls.jobs(registry, pool, ["R1", "R3"])
    assert got == [
        {
            "problem": "uci:1",
            "rule": "R1",
            "meta": {"uci_id": 1, "name": "one"},
            "path": str(pool / "1.csv"),
        },
        {
            "problem": "uci:1",
            "rule": "R3",
            "meta": {"uci_id": 1, "name": "one"},
            "path": str(pool / "1.csv"),
        },
    ]


class _SerialExecutor:
    """A process pool that runs in this process and remembers its worker count."""

    workers = None

    def __init__(self, max_workers):
        type(self).workers = max_workers

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def map(self, function, items):
        return map(function, items)


@pytest.fixture
def cli(monkeypatch):
    seen = {}

    def fake_jobs(registry, pool, rules):
        seen.update(registry=registry, pool=pool, rules=rules)
        return [
            {"problem": f"uci:{i}", "rule": r, "meta": META, "path": "x"}
            for i in (1, 2)
            for r in rules
        ]

    def fake_run(job, methods=None):
        seen.setdefault("methods", methods)
        state = {"uci:1": {"not_applicable": "no"}, "uci:2": {"failed": "boom"}}[job["problem"]]
        return {"problem": job["problem"], "rule": job["rule"], **state}

    monkeypatch.setattr(ls, "jobs", fake_jobs)
    monkeypatch.setattr(ls, "run_job", fake_run)
    monkeypatch.setattr(ls, "ProcessPoolExecutor", _SerialExecutor)
    return seen


def test_main_uses_the_documented_defaults_and_archives_one_file_per_problem_and_rule(
    cli, tmp_path, capsys
):
    assert ls.main(["--output", str(tmp_path / "out")]) == 0
    assert cli["registry"] == ls.ROOT / "verification" / "evidence" / "dataset_registry"
    assert cli["pool"] == ls.ROOT / "data" / "pool"
    assert cli["rules"] == ["R1", "R2", "R3", "R4", "R5"]
    assert _SerialExecutor.workers == 4
    assert cli["methods"] == ls.lb.METHODS
    files = sorted(p.name for p in (tmp_path / "out").iterdir())
    assert files == sorted(f"uci_{i}_R{r}.json" for i in (1, 2) for r in range(1, 6))
    raw = (tmp_path / "out" / "uci_1_R1.json").read_text()
    assert (
        raw
        == json.dumps(
            {"not_applicable": "no", "problem": "uci:1", "rule": "R1"}, indent=1, sort_keys=True
        )
        + "\n"
    )
    lines = capsys.readouterr().out.splitlines()
    assert lines[:2] == ["uci:1 R1 no", "uci:1 R2 no"]
    assert lines[5:7] == ["uci:2 R1 boom", "uci:2 R2 boom"]
    assert len(lines) == 10


def test_main_prints_ok_for_a_finished_problem(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ls, "jobs", lambda *a: [{"problem": "uci:3", "rule": "R1"}])
    monkeypatch.setattr(ls, "run_job", lambda job, methods=None: {**job, "rows": 5})
    monkeypatch.setattr(ls, "ProcessPoolExecutor", _SerialExecutor)
    assert ls.main(["--output", str(tmp_path), "--workers", "2"]) == 0
    assert capsys.readouterr().out == "uci:3 R1 ok\n"
    assert _SerialExecutor.workers == 2


def test_main_restricts_rules_problems_and_methods_and_skips_existing_outputs(
    cli, tmp_path, capsys
):
    out = tmp_path / "out"
    out.mkdir()
    (out / "uci_1_R2.json").write_text("{}")
    code = ls.main(
        ["--output", str(out), "--rules", "R1", "R2", "--only", "uci:1", "--methods", "deep"]
    )
    assert code == 0
    assert cli["rules"] == ["R1", "R2"]
    assert cli["methods"] == list(ls.DEEP_NAMES)
    assert capsys.readouterr().out == "uci:1 R1 no\n"
    assert sorted(p.name for p in out.iterdir()) == ["uci_1_R1.json", "uci_1_R2.json"]
    assert (out / "uci_1_R2.json").read_text() == "{}"


def test_main_rejects_an_unknown_method_family(cli, tmp_path):
    with pytest.raises(SystemExit):
        ls.main(["--output", str(tmp_path), "--methods", "quantum"])


ANOMALY_ROWS_R1 = [380, 381, 384, 385, 387, 388, 391, 399]


def test_the_parser_reads_paths_numbers_and_choices_with_the_documented_defaults():
    parser = ls.build_parser()
    assert parser.description == ls.__doc__
    args = parser.parse_args(["--output", "out"])
    assert args.output == Path("out") and isinstance(args.output, Path)
    assert args.registry == ls.ROOT / "verification" / "evidence" / "dataset_registry"
    assert args.pool == ls.ROOT / "data" / "pool"
    assert args.workers == 4 and args.rules == list(ls.RULES)
    assert args.only is None and args.methods == "classical"
    custom = parser.parse_args(
        [
            "--output", "o", "--registry", "r", "--pool", "p", "--workers", "2",
            "--rules", "R1", "R2", "--only", "uci:1", "uci:2", "--methods", "deep",
        ]
    )  # fmt: skip
    assert custom.registry == Path("r") and isinstance(custom.registry, Path)
    assert custom.pool == Path("p") and isinstance(custom.pool, Path)
    assert custom.workers == 2 and custom.rules == ["R1", "R2"]
    assert custom.only == ["uci:1", "uci:2"] and custom.methods == "deep"
    assert parser.parse_args(["--output", "o", "--only"]).only == []
    assert parser.parse_args(["--output", "o", "--rules"]).rules == []


def test_the_output_directory_is_required_and_the_help_names_the_options():
    parser = ls.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
    help_text = parser.format_help()
    assert "problem ids, for a quick check" in help_text
    assert "--output OUTPUT" in help_text.replace("\n", " ") and "[--output" not in help_text
    assert "{classical,deep}" in help_text


def test_main_creates_missing_parent_directories_of_the_output(cli, tmp_path):
    out = tmp_path / "a" / "b" / "out"
    assert ls.main(["--output", str(out)]) == 0
    assert out.is_dir()


def test_the_rarest_class_is_the_anomaly_even_with_three_classes():
    frame = _frame(A=300, B=40, C=25)
    features, labels, info = ls.derive_rule(frame, META, "R3")
    assert info["anomaly_class"] == "C" and info["anomalies"] == 25
    assert set(frame.loc[features["row"][labels == 1], "t"]) == {"C"}
    assert info["rows"] == 365
