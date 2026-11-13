"""Registry order, table text, merging rules and the pooled report of the complete registry.

The archived runs are copied, summarised and compared with digests of the output: the committed
``full_registry/summary.md`` and ``synthetic_results.*`` predate later archives (58 typed datasets
rather than 42, re-archived neural seeds), so the regenerated report is what is pinned here.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import full_registry as fr  # noqa: E402
import full_registry_summary as fs  # noqa: E402

SUMMARY_SHA = "a78ea56f978ca62752ee531799ae912bc564efb3b4fc2449a30fbfbeabf3d069"
RESULTS_MD_SHA = "94242492855dd1a52e8a18bf2babaae5900c3341f7ae60f11aca66a5a393d4d0"
RESULTS_JSON_SHA = "5e3352e20ed482a9e904e47d6336eb446bfe9ccd853bc37ac97a6a32de6f07cd"


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _round(value):
    if isinstance(value, float):
        return round(value, 9)
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_round(v) for v in value]
    return value


@pytest.fixture(scope="module")
def archive(tmp_path_factory):
    root = tmp_path_factory.mktemp("evidence-copy")
    source = fs.EVIDENCE
    shutil.copytree(source / "full_registry", root / "evidence" / "full_registry")
    for name in ("typed_injection", "multi_schema", "pool_extension", "deep_typed"):
        shutil.copytree(source / name, root / "evidence" / name)
    for csv in source.glob("*.csv"):
        shutil.copy(csv, root / "evidence" / csv.name)
    (root / "figures").mkdir()
    return root


def test_the_report_over_the_archived_runs_is_unchanged_and_its_figures_are_written(archive):
    summary = fs.build(archive / "evidence", archive / "figures")
    assert summary["typed_datasets"] == 58 and summary["synthetic_rows"][:3] == [
        "zscore", "iqr", "great_expectations",
    ]  # fmt: skip
    text = (archive / "evidence" / "full_registry" / "summary.md").read_text()
    assert _sha(text) == SUMMARY_SHA
    assert text.startswith("### Typed injection, median recall over 58 real datasets\n")
    assert (archive / "figures" / "heatmap_full.png").stat().st_size > 0
    assert (archive / "figures" / "typed_pooled.png").stat().st_size > 0


def test_the_summary_command_prints_the_counts_and_the_hypothesis_report_is_unchanged(
    archive, capsys, tmp_path
):
    assert (
        fs.main(["--evidence", str(archive / "evidence"), "--figures", str(archive / "figures")])
        == 0
    )
    printed = json.loads(capsys.readouterr().out)
    assert set(printed) == {"typed_datasets", "synthetic_rows"} and printed["typed_datasets"] == 58
    out = tmp_path / "o"
    runs = archive / "evidence" / "full_registry"
    assert fr.main(["summary", "--output", str(out), "--deep-runs", str(runs)]) == 0
    assert _sha((out / "synthetic_results.md").read_text()) == RESULTS_MD_SHA
    stored = json.loads((out / "synthetic_results.json").read_text())
    assert _sha(json.dumps(_round(stored), sort_keys=True)) == RESULTS_JSON_SHA


def test_rows_follow_the_registry_order_and_unknown_names_go_last():
    frame = pd.DataFrame({"a": [1, 2, 3, 4]}, index=["lunar", "mystery", "zscore", "drift"])
    assert fs.ordered(frame).index.tolist() == ["zscore", "lunar", "drift", "mystery"]


def test_a_table_is_written_in_markdown_with_digits_or_with_an_interval():
    frame = pd.DataFrame([[0.5, 0.25]], index=["m"], columns=["a", "b"])
    assert fs.table_md(frame) == "| method | a | b |\n|---|---|---|\n| m | 0.50 | 0.25 |\n"
    assert fs.table_md(frame, digits=3).splitlines()[2] == "| m | 0.500 | 0.250 |"
    low, high = frame - 0.125, frame + 0.125
    banded = fs.table_md(frame, low, high).splitlines()[2]
    assert banded == "| m | 0.50 [0.38, 0.62] | 0.25 [0.12, 0.38] |"


def test_neural_rows_join_the_classical_ones_without_a_second_duplicate_row(tmp_path):
    classical, deep = tmp_path / "c", tmp_path / "d"
    classical.mkdir()
    deep.mkdir()

    def payload(name, index):
        frame = pd.DataFrame(0.5, index=index, columns=fs.TYPES)
        return {"name": name, "recall_mean": json.loads(frame.to_json(orient="split"))}

    (classical / "x.json").write_text(json.dumps(payload("X", ["zscore", "transform_dedup"])))
    (classical / "y.json").write_text(json.dumps(payload("Y", ["zscore"])))
    (deep / "x.json").write_text(json.dumps(payload("X", ["vae", "transform_dedup"])))
    merged = fs.merged_typed(classical, deep)
    assert list(merged) == ["X", "Y"]
    assert merged["X"].index.tolist() == ["zscore", "vae", "transform_dedup"]
    assert merged["Y"].index.tolist() == ["zscore"]


def test_the_clean_row_rates_pool_the_classical_and_neural_files_per_method(tmp_path):
    classical, deep = tmp_path / "c", tmp_path / "d"
    classical.mkdir()
    deep.mkdir()
    for i, rate in enumerate((0.1, 0.3)):
        (classical / f"{i}.json").write_text(json.dumps({"fpr_mean": {"zscore": rate, "lof": 0.5}}))
    (deep / "0.json").write_text(json.dumps({"fpr_mean": {"vae": 0.2}}))
    table = fs.typed_fpr(classical, deep)
    assert table.index.tolist() == ["zscore", "lof", "vae"]
    assert table.loc["zscore"].tolist() == [pytest.approx(0.2), 0.3]
    assert table.loc["vae"].tolist() == [0.2, 0.2]


def test_the_mean_over_neural_seed_files_follows_the_first_file_order(tmp_path):
    for seed, value in ((1, 0.2), (2, 0.4)):
        frame = pd.DataFrame(value, index=["vae", "dif"], columns=fs.TYPES)
        payload = {"recall": json.loads(frame.to_json(orient="split"))}
        (tmp_path / f"synthetic_seed_{seed}.json").write_text(json.dumps(payload))
    mean = fs.deep_mean(tmp_path, "synthetic_seed_*.json")
    assert mean.index.tolist() == ["vae", "dif"]
    assert np.allclose(mean.to_numpy(), 0.3)


def test_a_real_table_stacks_the_neural_means_under_the_classical_rows(tmp_path):
    cols = ["precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct"]
    base = pd.DataFrame({f"{c}_mean": [0.5] for c in cols}, index=["zscore"])
    csv = tmp_path / "b.csv"
    base.to_csv(csv)

    def run(value):
        return {"methods": {"vae": {c: value for c in cols}, "lunar": {"error": "x"}}}

    deep = tmp_path / "d.json"
    deep.write_text(json.dumps({"runs": [run(0.2), run(0.4)]}))
    table = fs.real_table(csv, deep)
    assert table.index.tolist() == ["zscore", "vae"] and list(table.columns) == cols
    assert table.loc["vae"].tolist() == [pytest.approx(0.3)] * 6


def test_a_neural_row_that_has_no_deduplication_row_is_merged_as_it_is(tmp_path):
    classical, deep = tmp_path / "c", tmp_path / "d"
    classical.mkdir()
    deep.mkdir()
    frame = pd.DataFrame(0.5, index=["zscore"], columns=fs.TYPES)
    body = {"name": "X", "recall_mean": json.loads(frame.to_json(orient="split"))}
    (classical / "x.json").write_text(json.dumps(body))
    neural = pd.DataFrame(0.25, index=["vae"], columns=fs.TYPES)
    body["recall_mean"] = json.loads(neural.to_json(orient="split"))
    (deep / "x.json").write_text(json.dumps(body))
    assert fs.merged_typed(classical, deep)["X"].index.tolist() == ["zscore", "vae"]


def test_a_figure_is_drawn_with_the_height_of_its_rows_titled_saved_at_160_dpi_and_closed(
    monkeypatch, tmp_path
):
    calls = {}
    real = fs.plt.subplots

    def subplots(**kwargs):
        calls["subplots"] = kwargs
        fig, ax = real(**kwargs)
        original = fig.savefig
        fig.savefig = lambda path, **kw: calls.update(save=(path, kw)) or original(path, **kw)
        calls["fig"] = fig
        return fig, ax

    monkeypatch.setattr(fs.plt, "subplots", subplots)
    monkeypatch.setattr(fs.tf, "_draw", lambda ax, frame, title: calls.update(draw=(frame, title)))
    monkeypatch.setattr(fs.plt, "close", lambda fig: calls.update(closed=fig))
    frame = pd.DataFrame(0.5, index=["a", "b", "c", "d"], columns=["x"])
    fs.figure(frame, "A title", tmp_path / "f.png")
    assert calls["subplots"] == {"figsize": (7, 0.3 * 4 + 1.6)}
    assert calls["draw"][0] is frame and calls["draw"][1] == "A title"
    assert calls["save"] == (tmp_path / "f.png", {"dpi": 160})
    assert calls["closed"] is calls["fig"]
    assert (tmp_path / "f.png").stat().st_size > 0
