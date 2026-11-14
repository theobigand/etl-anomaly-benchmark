# ruff: noqa: E501
"""The paper tables command and the rows that skip what a run did not produce."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paper_tables as pt  # noqa: E402


@pytest.fixture
def wired(monkeypatch):
    seen = {"rows": [], "replace": []}
    monkeypatch.setattr(pt, "TABLES", {"one": None, "two": None})
    monkeypatch.setattr(
        pt,
        "rows",
        lambda label, evidence: seen["rows"].append((label, evidence)) or f"body {label}",
    )
    monkeypatch.setattr(
        pt,
        "replace_body",
        lambda tex, label, body: seen["replace"].append((tex, label, body)) or f"{tex}+{label}",
    )
    return seen


def test_the_tables_are_rebuilt_in_order_from_the_given_evidence_and_written_into_the_tex(
    wired, tmp_path
):
    tex, evidence = tmp_path / "main.tex", tmp_path / "evidence"
    tex.write_text("start")
    assert pt.main(["--tex", str(tex), "--evidence", str(evidence)]) == 0
    assert wired["rows"] == [("one", evidence), ("two", evidence)]
    assert wired["replace"] == [("start", "one", "body one"), ("start+one", "two", "body two")]
    assert tex.read_text() == "start+one+two"


def test_the_print_option_prints_each_body_under_its_label_and_writes_nothing(
    wired, tmp_path, capsys
):
    tex = tmp_path / "main.tex"
    tex.write_text("start")
    assert pt.main(["--tex", str(tex), "--evidence", str(tmp_path), "--print"]) == 0
    assert capsys.readouterr().out == "== one\nbody one\n== two\nbody two\n"
    assert tex.read_text() == "start" and wired["replace"] == []


def test_the_defaults_are_the_paper_and_the_archived_evidence(wired, monkeypatch):
    seen = {}
    monkeypatch.setattr(Path, "read_text", lambda self: seen.setdefault("read", self) and "tex")
    monkeypatch.setattr(Path, "write_text", lambda self, text: seen.setdefault("wrote", self))
    pt.main([])
    assert (
        seen["read"] == pt.ROOT / "paper" / "main.tex"
        and seen["wrote"] == pt.ROOT / "paper" / "main.tex"
    )
    assert wired["rows"][0][1] == pt.EVIDENCE and isinstance(wired["rows"][0][1], Path)


def test_the_help_describes_the_options(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "300")
    with pytest.raises(SystemExit):
        pt.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "--print print the rows instead of writing" in text
    assert "--tex TEX" in text and "--evidence EVIDENCE" in text


def _pilot(names):
    entry = {
        "pr_auc": 0.5,
        "pr_auc_ci": {"ci_low": 0.1, "ci_high": 0.9},
        "roc_auc": 0.7,
        "flagged_pct": 1.5,
    }
    strat = {"pr_auc": {"mean": 0.4, "std": 0.05}}
    return {"chronological": {n: entry for n in names}, "stratified": {n: strat for n in names}}


def test_a_detector_missing_from_the_pilot_does_not_hide_the_ones_after_it(tmp_path):
    names = list(pt.NAMES)
    folder = tmp_path / "temporal_pilot"
    folder.mkdir()
    (folder / "temporal_pilot.json").write_text(json.dumps(_pilot(names[1:4])))
    lines = pt.chrono_rows(tmp_path).split("\n")
    rows = [line for line in lines if line != r"\midrule"]
    assert [line.split("&")[0].strip() for line in rows] == [pt.NAMES[n] for n in names[1:4]]
    assert r"\midrule" in lines


def test_a_run_without_metrics_adds_nothing_to_the_counts_and_does_not_stop_the_count(
    tmp_path, monkeypatch
):
    names = [f"n{i}" for i in range(11)]
    monkeypatch.setattr(pt, "NAMES", {n: n.upper() for n in names})
    pool = tmp_path / "labelled_pool"
    (pool / "runs").mkdir(parents=True)
    (tmp_path / "full_registry" / "pool_deep" / "runs").mkdir(parents=True)
    (pool / "runs" / "1.json").write_text(json.dumps({"problem": "p"}))
    (pool / "runs" / "2.json").write_text(json.dumps({"metrics": {n: [1] for n in names}}))

    def frame(subset, value):
        return {
            "data": [[value, 0.2, 0.9]] * len(subset), "index": subset,
            "columns": ["median", "lo", "hi"],
        }  # fmt: skip

    first, second = names[:6], names[6:]
    (pool / "labelled_results.json").write_text(
        json.dumps(
            {
                "pr_auc": frame(first, 0.5),
                "roc_auc": frame(first, 0.6),
                "deep": {"pr_auc": frame(second, 0.3), "roc_auc": frame(second, 0.4)},
                "median_rank_all": {n: 1.0 for n in names},
            }
        )
    )
    lines = pt.pool_rows(tmp_path).split("\n")
    assert lines[0].startswith("N0") and " & 1 & 0.500 [0.200, 0.900] & 0.600 & 1.0" in lines[0]
    assert lines[3] == r"\midrule" and lines[-1] == r"\midrule" and lines[-2].startswith("N10")
    assert [line.split("&")[0].strip() for line in lines if line != r"\midrule"] == [
        n.upper() for n in names
    ]
    assert lines.count(r"\midrule") == 2
