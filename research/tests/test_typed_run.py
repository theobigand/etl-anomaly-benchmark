"""typed_run: aggregation over seeds, job selection and the command line, with a stub evaluator."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import injection as inj  # noqa: E402
import typed_benchmark as tb  # noqa: E402
import typed_run as tr  # noqa: E402

from etl_benchmark.registry import DEEP_NAMES  # noqa: E402


def _frames(k):
    """Per-seed result: recall and precision depend on the seed index k, fpr likewise."""
    index = pd.Index(["zscore", "transform_dedup"], name="method")
    recall = pd.DataFrame({"duplicate": [0.1 * k, 1.0], "drift": [0.2, 0.5 * k]}, index=index)
    precision = pd.DataFrame({"duplicate": [0.3, 0.4 * k], "drift": [0.0, 0.6]}, index=index)
    fpr = pd.Series([0.01 * k, 0.02], index=["zscore", "transform_dedup"])
    return {"recall": recall, "precision": precision, "fpr": fpr}


@pytest.fixture
def stubbed(monkeypatch):
    seen = {"inject": [], "evaluate": [], "carrier": []}
    carrier = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    monkeypatch.setattr(tr, "SEEDS", (7, 8, 9))

    def load(meta, path, seed):
        seen["carrier"].append((meta["uci_id"], path, seed))
        return carrier, {"rows_in": 2}

    def inject(frame, seed):
        assert frame is carrier
        seen["inject"].append(seed)
        return f"injected-{seed}"

    def evaluate(df, cols, seed, names):
        seen["evaluate"].append((df, cols, seed, names))
        return _frames(len(seen["evaluate"]))

    monkeypatch.setattr(tr, "load_carrier", load)
    monkeypatch.setattr(inj, "inject", inject)
    monkeypatch.setattr(tb, "evaluate", evaluate)
    return seen


def test_run_one_averages_recall_precision_and_fpr_over_the_seeds(stubbed):
    meta = {"uci_id": 5, "name": "Toy"}
    out = tr.run_one((meta, "/data/5.csv", "ab" * 32), names=["zscore"])
    assert out["uci_id"] == 5 and out["name"] == "Toy" and out["sha256"] == "ab" * 32
    assert out["carrier"] == {"rows_in": 2} and out["seeds"] == [7, 8, 9]
    assert stubbed["carrier"] == [(5, Path("/data/5.csv"), 0)]
    assert stubbed["inject"] == [7, 8, 9]
    assert [(e[0], e[1], e[2], e[3]) for e in stubbed["evaluate"]] == [
        (f"injected-{s}", ["a", "b"], s, ["zscore"]) for s in (7, 8, 9)
    ]
    mean = out["recall_mean"]
    assert mean["index"] == ["zscore", "transform_dedup"]
    assert mean["columns"] == ["duplicate", "drift"]
    assert mean["data"] == [pytest.approx([0.2, 0.2]), pytest.approx([1.0, 1.0])]
    # recall(k) = [0.1 k, 0.5 k] for the second method on 'drift', k = 1, 2, 3 -> mean 1.0
    assert out["precision_mean"]["data"] == [
        pytest.approx([0.3, 0.0]),
        pytest.approx([0.8, 0.6]),
    ]
    assert out["fpr_mean"] == {
        "zscore": pytest.approx(0.02),
        "transform_dedup": pytest.approx(0.02),
    }
    assert len(out["recall_seeds"]) == 3
    assert out["recall_seeds"][2]["data"][0] == pytest.approx([0.3, 0.2])


def test_run_one_defaults_to_every_detector_when_no_names_are_given(stubbed):
    tr.run_one(({"uci_id": 1, "name": "x"}, "p.csv", "00"))
    assert all(e[3] is None for e in stubbed["evaluate"])


def _registry(tmp_path):
    metas = [{"uci_id": i, "name": f"d{i}"} for i in (1, 2, 3, 4)]
    curated = tmp_path / "curated.json"
    curated.write_text(json.dumps({"kept": metas}))
    rows = [
        {"uci_id": 1, "roles": ["carrier", "labelled"], "sha256": "s1"},
        {"uci_id": 2, "roles": ["labelled"], "sha256": "s2"},  # no carrier role: skipped
        {"uci_id": 3, "roles": ["carrier"], "sha256": "s3"},  # not eligible: skipped
        {"uci_id": 4, "roles": ["carrier"], "sha256": "s4"},
    ]
    pool = tmp_path / "pool.json"
    pool.write_text(json.dumps({"rows": rows}))
    return curated, pool, metas


def test_jobs_keep_the_eligible_carriers_in_pool_order_with_their_path_and_digest(
    tmp_path, monkeypatch
):
    curated, pool, metas = _registry(tmp_path)
    checked = []

    def load(meta, path, seed):
        checked.append((meta["uci_id"], path, seed))
        if meta["uci_id"] == 3:
            raise inj.NotEligible("too few columns")
        return None, {}

    monkeypatch.setattr(tr, "load_carrier", load)
    out = tr.jobs(curated, pool, tmp_path / "data")
    assert out == [
        (metas[0], str(tmp_path / "data" / "1.csv"), "s1"),
        (metas[3], str(tmp_path / "data" / "4.csv"), "s4"),
    ]
    assert [c[0] for c in checked] == [1, 3, 4] and all(c[2] == 0 for c in checked)


class _Serial:
    """Stands in for ProcessPoolExecutor: records the worker count, maps in the calling process."""

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
    curated, pool, metas = _registry(tmp_path)
    ran = []

    def run_one(job, names=None):
        ran.append((job[0]["uci_id"], names))
        return {"uci_id": job[0]["uci_id"], "name": job[0]["name"], "b": 1, "a": 2}

    monkeypatch.setattr(tr, "ProcessPoolExecutor", _Serial)
    monkeypatch.setattr(tr, "run_one", run_one)
    monkeypatch.setattr(tr, "load_carrier", lambda m, p, seed: (None, {}))
    _Serial.workers = []

    def invoke(*extra):
        args = ["--curated", str(curated), "--pool", str(pool), "--data", str(tmp_path / "d")]
        return tr.main([*args, "--output", str(tmp_path / "out" / "x"), *extra])

    return invoke, ran, tmp_path / "out" / "x"


def test_main_writes_one_sorted_json_per_dataset_and_reports_the_count(cli, capsys):
    invoke, ran, out = cli
    assert invoke() == 0
    assert [r[0] for r in ran] == [1, 3, 4] and all(r[1] is None for r in ran)
    assert sorted(p.name for p in out.glob("*.json")) == ["1.json", "3.json", "4.json"]
    text = (out / "1.json").read_text()
    assert (
        text
        == json.dumps({"uci_id": 1, "name": "d1", "b": 1, "a": 2}, indent=1, sort_keys=True) + "\n"
    )
    assert capsys.readouterr().out == "d1\nd3\nd4\n3 datasets\n"
    assert _Serial.workers == [4]


def test_main_only_resume_workers_and_methods_options(cli, capsys):
    invoke, ran, out = cli
    assert invoke("--only", "3", "4", "--workers", "2", "--methods", "deep") == 0
    assert ran == [(3, list(DEEP_NAMES)), (4, list(DEEP_NAMES))]
    assert _Serial.workers == [2] and capsys.readouterr().out.endswith("2 datasets\n")
    ran.clear()
    assert invoke("--resume") == 0
    assert ran == [(1, None)]  # 3 and 4 are already written
    assert capsys.readouterr().out == "d1\n1 datasets\n"


def test_main_refuses_unknown_methods_and_a_missing_output(tmp_path, capsys):
    with pytest.raises(SystemExit):
        tr.main(["--output", str(tmp_path), "--methods", "quantum"])
    with pytest.raises(SystemExit):
        tr.main([])
    err = capsys.readouterr().err
    assert "invalid choice" in err and "--output" in err
    with pytest.raises(SystemExit):
        tr.main(["--help"])
    assert "typed-injection benchmark" in capsys.readouterr().out


def test_the_default_paths_point_at_the_registry_and_the_pool_data(monkeypatch, tmp_path):
    seen = {}

    def spy(curated, pool, data):
        seen.update(curated=curated, pool=pool, data=data)
        return []

    monkeypatch.setattr(tr, "jobs", spy)
    monkeypatch.setattr(tr, "ProcessPoolExecutor", _Serial)
    tr.main(["--output", str(tmp_path / "o")])
    root = Path(tr.__file__).resolve().parents[1]
    assert seen["curated"] == root / "verification/evidence/dataset_registry/uci_curated.json"
    assert seen["pool"] == root / "verification/evidence/dataset_registry/uci_pool.json"
    assert seen["data"] == root / "data" / "pool"


def test_the_protocol_seeds_are_the_five_registered_ones():
    assert tr.SEEDS == (42, 1, 2, 3, 4)


def test_the_carrier_is_prepared_with_the_fixed_seed_zero(tmp_path, monkeypatch):
    rng = np.random.default_rng(0)
    table = pd.DataFrame({f"x{i}": rng.normal(size=4000) for i in range(5)})
    path = tmp_path / "1.csv"
    table.to_csv(path, index=False)
    seeds = []
    real = inj.prepare
    monkeypatch.setattr(inj, "prepare", lambda f, seed: seeds.append(seed) or real(f, seed=seed))
    meta = {"uci_id": 1, "tasks": ["Regression"], "target_col": [], "variables": []}
    tr.load_carrier(meta, path, seed=5)
    assert seeds == [0]


def test_jobs_check_the_carrier_at_the_pool_path(tmp_path, monkeypatch):
    curated, pool, _ = _registry(tmp_path)
    paths = []
    monkeypatch.setattr(tr, "load_carrier", lambda m, p, seed: paths.append(p) or (None, {}))
    tr.jobs(curated, pool, tmp_path / "data")
    assert paths == [
        tmp_path / "data" / "1.csv",
        tmp_path / "data" / "3.csv",
        tmp_path / "data" / "4.csv",
    ]


def test_progress_lines_are_flushed_and_the_help_documents_the_options(cli, monkeypatch, capsys):
    invoke, ran, out = cli
    flushes = []
    monkeypatch.setattr(tr, "print", lambda *a, **k: flushes.append(k.get("flush")), raising=False)
    invoke("--only", "1")
    assert flushes == [True, None]  # one line per dataset, then the count
    monkeypatch.undo()
    with pytest.raises(SystemExit):
        tr.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    for phrase in (
        "UCI ids, for a quick check",
        "skip the datasets whose result is already written",
        "the registry sweep with drift, or the neural detectors",
    ):
        assert phrase in text
        assert "XX" + phrase not in text and phrase.upper() not in text


def _parsed_namespaces(monkeypatch):
    import argparse

    seen = []
    real = argparse.ArgumentParser.parse_args

    def spy(self, *args, **kwargs):
        namespace = real(self, *args, **kwargs)
        seen.append(namespace)
        return namespace

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", spy)
    return seen


def test_the_default_method_set_is_classical_and_both_named_sets_are_accepted(cli, monkeypatch):
    invoke, ran, _ = cli
    seen = _parsed_namespaces(monkeypatch)
    assert invoke() == 0 and seen[-1].methods == "classical"
    assert invoke("--methods", "classical") == 0 and seen[-1].methods == "classical"
    assert invoke("--methods", "deep") == 0 and seen[-1].methods == "deep"
