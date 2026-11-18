# ruff: noqa: E501
"""The appendix of full matrices: its text, the drift row it drops, and where it is written."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paper_appendix as pa  # noqa: E402


def _matrix(rows):
    return pd.DataFrame(0.5, index=rows, columns=["a"])


@pytest.fixture
def stubs(monkeypatch):
    seen = {"tables": []}
    customer = _matrix(["zscore"])
    monkeypatch.setattr(
        pa.fs,
        "synthetic_matrix",
        lambda evidence, out: seen.update(syn=(evidence, out)) or customer,
    )
    monkeypatch.setattr(
        pa.fs,
        "schema_matrices",
        lambda multi, deep: (
            seen.update(schema=(multi, deep))
            or {"transactions": _matrix(["zscore", "drift"]), "sensors": _matrix(["iqr", "drift"])}
        ),
    )
    monkeypatch.setattr(
        pa.fs,
        "merged_typed",
        lambda classical, deep: seen.update(typed=(classical, deep)) or {"d": 1},
    )
    monkeypatch.setattr(pa.ts, "pooled", lambda typed: {"median": _matrix(["pca"])})
    monkeypatch.setattr(pa.fs, "ordered", lambda frame: frame)
    monkeypatch.setattr(
        pa.pt,
        "matrix_table",
        lambda frame, caption, label: (
            seen["tables"].append((list(frame.index), caption, label)) or f"TABLE {label}"
        ),
    )
    seen["customer"] = customer
    return seen


def test_the_section_reads_the_archived_folders_of_the_registry_study(stubs, tmp_path):
    pa.section(tmp_path)
    out = tmp_path / "full_registry"
    assert stubs["syn"] == (tmp_path, out)
    assert stubs["schema"] == (tmp_path / "multi_schema", out / "schemas_deep")
    assert stubs["typed"] == (tmp_path / "typed_injection" / "runs", out / "typed_deep" / "runs")


def test_the_four_tables_come_in_order_with_their_captions_labels_and_without_the_drift_row(
    stubs, tmp_path
):
    pa.section(tmp_path)
    assert stubs["tables"] == [
        (["zscore"], "Synthetic customer table, mean recall over five seeds.", "tab:m-customer"),
        (
            ["zscore"],
            "Synthetic card transactions, mean recall over five seeds.",
            "tab:m-transactions",
        ),
        (["iqr"], "Synthetic sensor readings, mean recall over five seeds.", "tab:m-sensors"),
        (
            ["pca"],
            r"Typed injection into $42$ real tables, median recall over the tables.",
            "tab:m-typed",
        ),
    ]


def test_a_schema_without_a_drift_row_is_still_accepted(stubs, monkeypatch, tmp_path):
    monkeypatch.setattr(
        pa.fs,
        "schema_matrices",
        lambda multi, deep: {"transactions": _matrix(["zscore"]), "sensors": _matrix(["iqr"])},
    )
    pa.section(tmp_path)
    assert stubs["tables"][1][0] == ["zscore"] and stubs["tables"][2][0] == ["iqr"]


def test_the_section_text_is_its_heading_label_introduction_and_the_tables(stubs, tmp_path):
    text = pa.section(tmp_path)
    lines = text.split("\n")
    assert lines[0] == r"\section{Full per-type matrices}" and lines[1] == r"\label{app:matrices}"
    assert lines[2] == (
        "The tables below give the mean recall of every detector of the registry on each "
        "injected type, over five seeds for the synthetic tables and as the median over the "
        r"$42$ real tables for the last one. The best value of each column among the detectors "
        "of the registry is in bold."
    )
    assert lines[3:] == [
        "", "TABLE tab:m-customer", "", "TABLE tab:m-transactions", "", "TABLE tab:m-sensors", "",
        "TABLE tab:m-typed", "",
    ]  # fmt: skip
    assert text.endswith("TABLE tab:m-typed\n")


def _tex(tmp_path, body):
    path = tmp_path / "main.tex"
    path.write_text(body)
    return path


def test_the_block_is_inserted_before_the_first_bibliography_style_once(stubs, tmp_path):
    tex = _tex(tmp_path, "head\n\\bibliographystyle{a}\nmiddle\n\\bibliographystyle{b}\nend\n")
    pa.write(tex, tmp_path)
    body = tex.read_text()
    block = pa.START + pa.section(tmp_path) + pa.END
    assert (
        body == "head\n" + block + "\n\\bibliographystyle{a}\nmiddle\n\\bibliographystyle{b}\nend\n"
    )


def test_an_existing_block_is_replaced_and_what_surrounds_it_is_kept(stubs, tmp_path):
    old = pa.START + "old text\n" + pa.END
    tex = _tex(tmp_path, f"before\n{old}after\n% END generated matrices\nlast\n")
    pa.write(tex, tmp_path)
    block = pa.START + pa.section(tmp_path) + pa.END
    assert tex.read_text() == f"before\n{block}after\n% END generated matrices\nlast\n"


def test_writing_twice_gives_the_same_file(stubs, tmp_path):
    tex = _tex(tmp_path, "head\n\\bibliographystyle{a}\ntail\n")
    pa.write(tex, tmp_path)
    once = tex.read_text()
    pa.write(tex, tmp_path)
    assert tex.read_text() == once and once.count(pa.START) == 1


def test_the_markers_are_comment_lines_ending_with_a_newline():
    assert pa.START == "% BEGIN generated matrices\n" and pa.END == "% END generated matrices\n"
