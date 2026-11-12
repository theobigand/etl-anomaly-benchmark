"""pool_typed: jobs, carriers, eligibility records, aggregation and the command line (stubbed)."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import injection as inj  # noqa: E402
import pool_typed as pt  # noqa: E402
import typed_benchmark as tb  # noqa: E402
import typed_run as tr  # noqa: E402

from etl_benchmark.registry import DEEP_NAMES  # noqa: E402


def _registry(tmp_path):
    reg = tmp_path / "reg"
    reg.mkdir()
    metas = [{"uci_id": i, "name": f"u{i}"} for i in (1, 2)]
    (reg / "uci_curated.json").write_text(json.dumps({"kept": metas}))
    (reg / "uci_pool.json").write_text(json.dumps({"rows": [{"uci_id": 2}, {"uci_id": 1}]}))
    names = [t["name"] for t in pt.dr.ADBENCH_TABULAR][:3]
    report = {names[2]: {}, names[0]: {}, names[1]: {}}  # unsorted on purpose
    (reg / "adbench_normalisation_report.json").write_text(json.dumps(report))
    return reg, metas, names


def test_jobs_list_the_uci_rows_in_pool_order_then_the_adbench_sets_sorted_by_name(tmp_path):
    reg, metas, names = _registry(tmp_path)
    out = pt.jobs(reg, tmp_path / "data", tmp_path / "ad")
    files = {t["name"]: t["file"] for t in pt.dr.ADBENCH_TABULAR}
    assert out[:2] == [
        {
            "id": f"uci:{i}",
            "source": "uci",
            "name": f"u{i}",
            "meta": metas[i - 1],
            "path": str(tmp_path / "data" / f"{i}.csv"),
        }
        for i in (2, 1)
    ]
    assert out[2:] == [
        {
            "id": f"adbench:{n}",
            "source": "adbench",
            "name": n,
            "path": str(tmp_path / "ad" / files[n]),
        }
        for n in sorted(names)
    ]


def test_a_uci_job_is_loaded_by_typed_run_with_the_given_seed(monkeypatch):
    seen = []
    monkeypatch.setattr(tr, "load_carrier", lambda m, p, s: seen.append((m, p, s)) or ("c", {}))
    job = {"source": "uci", "meta": {"uci_id": 3}, "path": "/x/3.csv"}
    assert pt.load_carrier(job) == ("c", {})
    pt.load_carrier(job, seed=9)
    assert seen == [({"uci_id": 3}, Path("/x/3.csv"), 0), ({"uci_id": 3}, Path("/x/3.csv"), 9)]


def test_an_adbench_carrier_keeps_only_the_normal_class_and_reports_the_source_rows(
    tmp_path, monkeypatch
):
    rng = np.random.default_rng(0)
    y = np.zeros(3664, dtype=int)
    y[::8] = 1
    x = np.column_stack(
        [
            np.arange(3664.0),
            rng.normal(size=(3664, 4)).T[0],
            rng.normal(size=3664),
            rng.normal(size=3664),
            rng.normal(size=3664),
        ]
    )
    path = tmp_path / "t.npz"
    np.savez(path, X=x, y=y)
    spied = []
    real = inj.prepare
    monkeypatch.setattr(
        inj, "prepare", lambda f, seed: spied.append((f, seed)) or real(f, seed=seed)
    )
    job = {"source": "adbench", "path": str(path)}
    carrier, report = pt.load_carrier(job, seed=4)
    frame, seed = spied[0]
    assert seed == 4 and list(frame.columns) == ["f0", "f1", "f2", "f3", "f4"]
    assert list(frame.index) == list(range(3206))  # reset after the filter
    assert (frame["f0"].to_numpy() == x[y == 0, 0]).all()  # the normal rows, in order
    assert report["source_rows"] == 3206 and isinstance(report["source_rows"], int)
    assert report["normal_class_only"] is True
    assert pt.load_carrier(job)[1]["source_rows"] == 3206


def test_eligibility_records_the_reason_or_the_size_and_report(monkeypatch):
    job = {"id": "uci:1", "name": "u1", "source": "uci"}

    def raise_not_eligible(j):
        raise inj.NotEligible("only 2 continuous columns")

    def raise_other(j):
        raise ValueError("bad file")

    monkeypatch.setattr(pt, "load_carrier", raise_not_eligible)
    assert pt.eligibility(job) == {**job, "eligible": False, "reason": "only 2 continuous columns"}
    monkeypatch.setattr(pt, "load_carrier", raise_other)
    assert pt.eligibility(job)["reason"] == "load failed: ValueError('bad file')"
    monkeypatch.setattr(
        pt, "load_carrier", lambda j: (pd.DataFrame({"a": [1.0, 2.0, 3.0]}), {"k": 1})
    )
    assert pt.eligibility(job) == {**job, "eligible": True, "rows": 3, "report": {"k": 1}}


def _frames(k):
    index = pd.Index(["zscore", "transform_dedup"], name="method")
    cols = ["univariate_outlier", "multivariate_outlier", "temporal_drift", "duplicate"]
    recall = pd.DataFrame(
        [[0.1 * k, 0.2, 0.3, 0.4], [0.5, 0.5 * k, 0.5, 1.0]], index=index, columns=cols
    )
    precision = pd.DataFrame([[0.2 * k] * 4, [0.6] * 4], index=index, columns=cols)
    return {
        "recall": recall,
        "precision": precision,
        "fpr": pd.Series([0.01 * k, 0.02], index=index),
    }


@pytest.fixture
def stubbed(monkeypatch):
    seen = {"inject": [], "evaluate": []}
    carrier = pd.DataFrame({"a": [1.0], "b": [2.0]})
    jobs_seen = seen.setdefault("jobs", [])
    monkeypatch.setattr(
        pt, "load_carrier", lambda job: jobs_seen.append(job) or (carrier, {"rows_in": 1})
    )
    monkeypatch.setattr(pt, "SEEDS", (7, 8, 9))

    def inject(frame, seed, **kw):
        assert frame is carrier
        seen["inject"].append((seed, kw))
        return f"df-{seed}-{kw.get('severity')}"

    def evaluate(df, cols, seed, names):
        seen["evaluate"].append((df, cols, seed, names))
        return _frames(len(seen["evaluate"]))

    monkeypatch.setattr(inj, "inject", inject)
    monkeypatch.setattr(tb, "evaluate", evaluate)
    return seen


JOB = {"id": "adbench:toy", "name": "toy", "source": "adbench", "path": "p"}


def test_the_reference_run_averages_recall_precision_and_fpr_over_the_five_seeds(stubbed):
    out = pt.run_reference(JOB, names=["zscore"])
    assert stubbed["jobs"] == [JOB]
    assert (out["id"], out["name"], out["carrier"], out["seeds"]) == (
        "adbench:toy",
        "toy",
        {"rows_in": 1},
        [7, 8, 9],
    )
    assert stubbed["inject"] == [(7, {}), (8, {}), (9, {})]
    assert [(e[0], e[1], e[2], e[3]) for e in stubbed["evaluate"]] == [
        (f"df-{s}-None", ["a", "b"], s, ["zscore"]) for s in (7, 8, 9)
    ]
    r = out["recall_mean"]
    assert r["index"] == ["zscore", "transform_dedup"] and r["columns"][-1] == "duplicate"
    assert r["data"][0] == pytest.approx([0.2, 0.2, 0.3, 0.4])
    assert out["precision_mean"]["data"][0] == pytest.approx([0.4] * 4)
    assert out["fpr_mean"] == {
        "zscore": pytest.approx(0.02),
        "transform_dedup": pytest.approx(0.02),
    }


def test_the_severity_sweep_reports_the_three_magnitude_types_for_every_multiplier(stubbed):
    pt.run_severity(JOB, names=["zscore"], severities=(1.0,), seeds=(3,))
    assert stubbed["evaluate"][0][3] == ["zscore"]
    stubbed["evaluate"].clear()
    stubbed["inject"].clear()
    stubbed["jobs"].clear()
    out = pt.run_severity(JOB, severities=(0.5, 2.0), seeds=(1, 2))
    assert out["seeds"] == [1, 2] and out["severities"] == [0.5, 2.0]
    assert stubbed["inject"] == [
        (1, {"severity": 0.5}),
        (2, {"severity": 0.5}),
        (1, {"severity": 2.0}),
        (2, {"severity": 2.0}),
    ]
    assert set(out["recall_by_severity"]) == {"0.5", "2.0"}
    block = out["recall_by_severity"]["0.5"]
    assert block["columns"] == list(pt.MAGNITUDE_TYPES) and block["index"] == [
        "zscore",
        "transform_dedup",
    ]
    assert block["data"][0] == pytest.approx([0.15, 0.2, 0.3])  # k = 1, 2
    assert (out["id"], out["name"], out["carrier"]) == ("adbench:toy", "toy", {"rows_in": 1})
    assert stubbed["jobs"] == [JOB]
    assert [(e[1], e[2], e[3]) for e in stubbed["evaluate"]][:2] == [
        (["a", "b"], 1, None),
        (["a", "b"], 2, None),
    ]
    default = pt.run_severity(JOB)
    assert default["severities"] == list(pt.SEVERITIES) and default["seeds"] == list(pt.SWEEP_SEEDS)


def test_the_constants_match_the_protocol():
    assert pt.SWEEP_SEEDS == (42, 1, 2) and pt.SEVERITIES == (0.5, 1.0, 2.0, 4.0)
    assert pt.MAGNITUDE_TYPES == ("univariate_outlier", "multivariate_outlier", "temporal_drift")
    assert pt.SEEDS == tr.SEEDS


class _Serial:
    workers = []

    def __init__(self, max_workers):
        _Serial.workers.append(max_workers)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def map(self, fn, items):
        return [fn(i) for i in items]


@pytest.fixture
def cli(tmp_path, monkeypatch):
    jobs = [
        {"id": "uci:1", "source": "uci", "name": "u1"},
        {"id": "uci:2", "source": "uci", "name": "u2"},
        {"id": "adbench:a", "source": "adbench", "name": "a"},
        {"id": "adbench:b", "source": "adbench", "name": "b"},
    ]
    calls = {"jobs": [], "work": []}
    monkeypatch.setattr(pt, "jobs", lambda r, d, a: calls["jobs"].append((r, d, a)) or jobs)
    monkeypatch.setattr(pt, "ProcessPoolExecutor", _Serial)
    _Serial.workers = []
    monkeypatch.setattr(
        pt, "eligibility", lambda j: {"id": j["id"], "eligible": j["id"] != "uci:2"}
    )
    monkeypatch.setattr(
        pt,
        "run_reference",
        lambda j, names=None: (
            calls["work"].append(("ref", j["id"], names)) or {"b": 1, "a": j["id"]}
        ),
    )
    monkeypatch.setattr(
        pt,
        "run_severity",
        lambda j, names=None: (
            calls["work"].append(("sev", j["id"], names)) or {"b": 1, "a": j["id"]}
        ),
    )
    out = tmp_path / "run" / "sub"
    return out, calls


def test_the_eligibility_command_writes_one_json_and_counts_the_eligible_sets(cli, capsys):
    out, calls = cli
    assert pt.main(["eligibility", "--output", str(out), "--workers", "2"]) == 0
    rows = json.loads((out / "eligibility.json").read_text())
    assert [r["id"] for r in rows] == ["uci:1", "uci:2", "adbench:a", "adbench:b"]
    assert (out / "eligibility.json").read_text() == json.dumps(rows, indent=1) + "\n"
    assert capsys.readouterr().out == "3 eligible of 4\n" and _Serial.workers == [2]
    root = Path(pt.__file__).resolve().parents[1]
    assert calls["jobs"] == [
        (
            root / "verification/evidence/dataset_registry",
            root / "data" / "pool",
            root / "data" / "adbench",
        )
    ]
    pt.main(["eligibility", "--output", str(out), "--only", "adbench:a"])
    assert [r["id"] for r in json.loads((out / "eligibility.json").read_text())] == ["adbench:a"]


def _eligible(out, ids):
    out.parent.mkdir(parents=True, exist_ok=True)
    (out.parent / "eligibility.json").write_text(
        json.dumps([{"id": i, "eligible": e} for i, e in ids.items()])
    )


def test_the_reference_command_runs_the_eligible_adbench_sets_only(cli, capsys):
    out, calls = cli
    _eligible(out, {"uci:1": True, "uci:2": False, "adbench:a": True, "adbench:b": False})
    assert pt.main(["reference", "--output", str(out)]) == 0
    assert calls["work"] == [("ref", "adbench:a", None)]
    assert capsys.readouterr().out == "adbench:a\n"
    written = out / "adbench_a.json"
    assert written.read_text() == json.dumps({"b": 1, "a": "adbench:a"}, sort_keys=True) + "\n"


def test_the_severity_command_runs_every_eligible_set_and_honours_resume_and_methods(cli, capsys):
    out, calls = cli
    _eligible(out, {"uci:1": True, "uci:2": False, "adbench:a": True, "adbench:b": True})
    assert pt.main(["severity", "--output", str(out), "--methods", "deep"]) == 0
    assert [c[1] for c in calls["work"]] == ["uci:1", "adbench:a", "adbench:b"]
    assert all(c[2] == list(DEEP_NAMES) for c in calls["work"])
    assert sorted(p.name for p in out.glob("*.json")) == [
        "adbench_a.json",
        "adbench_b.json",
        "uci_1.json",
    ]
    calls["work"].clear()
    (out / "adbench_a.json").unlink()
    pt.main(["severity", "--output", str(out), "--resume"])
    assert calls["work"] == [("sev", "adbench:a", None)]
    calls["work"].clear()
    pt.main(["severity", "--output", str(out), "--only", "adbench:b"])
    assert [c[1] for c in calls["work"]] == ["adbench:b"]
    capsys.readouterr()


def test_the_command_line_refuses_unknown_commands_and_methods(tmp_path, capsys):
    with pytest.raises(SystemExit):
        pt.main(["nonsense", "--output", str(tmp_path)])
    with pytest.raises(SystemExit):
        pt.main(["severity", "--output", str(tmp_path), "--methods", "quantum"])
    with pytest.raises(SystemExit):
        pt.main(["severity"])
    err = capsys.readouterr().err
    assert "invalid choice" in err and "--output" in err
    with pytest.raises(SystemExit):
        pt.main(["--help"])
    assert "Typed injection and severity sweep" in capsys.readouterr().out


def test_eligibility_passes_the_job_to_the_loader_and_marks_a_failed_load_not_eligible(monkeypatch):
    seen = []
    job = {"id": "uci:1", "name": "u1", "source": "uci"}

    def load(j):
        seen.append(j)
        raise OSError("gone")

    monkeypatch.setattr(pt, "load_carrier", load)
    assert pt.eligibility(job) == {
        **job,
        "eligible": False,
        "reason": "load failed: OSError('gone')",
    }
    assert seen == [job]


def test_the_registry_files_are_read_by_their_exact_names(tmp_path, monkeypatch):
    reg, _, _ = _registry(tmp_path)
    reads = []
    real = Path.read_text
    monkeypatch.setattr(
        Path, "read_text", lambda self, *a, **k: reads.append(self.name) or real(self, *a, **k)
    )
    pt.jobs(reg, tmp_path / "d", tmp_path / "a")
    assert reads == ["uci_curated.json", "uci_pool.json", "adbench_normalisation_report.json"]


def test_main_reads_and_writes_eligibility_json_by_that_exact_name(cli, monkeypatch):
    out, calls = cli
    seen = []
    real = Path.read_text
    monkeypatch.setattr(
        Path, "read_text", lambda self, *a, **k: seen.append(self.name) or real(self, *a, **k)
    )
    pt.main(["eligibility", "--output", str(out)])
    assert (out / "eligibility.json").is_file()
    assert sorted(p.name for p in out.iterdir()) == ["eligibility.json"]
    _eligible(out, {"adbench:a": True})
    seen.clear()
    pt.main(["severity", "--output", str(out)])
    assert "eligibility.json" in seen


def test_a_worker_that_returns_fewer_results_than_jobs_is_an_error_not_a_silent_drop(
    cli, monkeypatch
):
    out, calls = cli

    class Short(_Serial):
        def map(self, fn, items):
            return [fn(i) for i in items][:-1]

    monkeypatch.setattr(pt, "ProcessPoolExecutor", Short)
    _eligible(out, {"uci:1": True, "adbench:a": True})
    with pytest.raises(ValueError):
        pt.main(["severity", "--output", str(out)])


def test_default_workers_methods_and_choices_progress_flush_and_help(cli, monkeypatch, capsys):
    out, calls = cli
    _eligible(out, {"adbench:a": True})
    flushes = []
    monkeypatch.setattr(pt, "print", lambda *a, **k: flushes.append(k.get("flush")), raising=False)
    pt.main(["reference", "--output", str(out), "--methods", "classical"])
    assert (
        _Serial.workers == [4]
        and calls["work"] == [("ref", "adbench:a", None)]
        and flushes == [True]
    )
    monkeypatch.undo()
    with pytest.raises(SystemExit):
        pt.main(["reference", "--output", str(out), "--methods", "CLASSICAL"])
    with pytest.raises(SystemExit):
        pt.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "{classical,deep}" in text and "dataset ids, for a quick check" in text
    assert "XXdataset" not in text and "DATASET IDS" not in text
    assert "--only [ONLY ...]" in text and "--workers WORKERS" in text
