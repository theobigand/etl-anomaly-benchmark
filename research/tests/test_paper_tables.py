"""The benchmark tables of the paper are the rows written from the archived results."""

import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paper_tables as pt  # noqa: E402

TEX = pt.ROOT / "paper" / "main.tex"


@pytest.mark.parametrize("label", list(pt.TABLES))
def test_each_benchmark_table_of_the_manuscript_equals_the_rows_of_its_archive(label):
    tex = TEX.read_text()
    assert pt.replace_body(tex, label, pt.rows(label)) == tex


def test_the_pool_chronology_and_example_rows_are_in_the_manuscript():
    tex = TEX.read_text()
    for body in (pt.pool_rows(), pt.chrono_rows(), pt.example_rows()):
        assert body and body in tex


def test_the_command_rewrites_a_copy_to_the_same_text_and_prints_each_table_on_request(
    tmp_path, capsys
):
    copy = tmp_path / "main.tex"
    shutil.copy(TEX, copy)
    assert pt.main(["--tex", str(copy)]) == 0
    assert copy.read_text() == TEX.read_text()
    assert pt.main(["--tex", str(copy), "--print"]) == 0
    out = capsys.readouterr().out
    for label in pt.TABLES:
        assert f"== {label}\n{pt.rows(label)}" in out
    assert copy.read_text() == TEX.read_text()


def test_the_rows_follow_the_registry_order_and_carry_one_cell_per_column():
    order = list(pt.NAMES.values())
    for label, columns in pt.COLUMNS.items():
        lines = [line for line in pt.rows(label).split("\n") if line != r"\midrule"]
        assert lines and all(line.endswith(r"\\") for line in lines)
        assert all(line.count("&") == len(columns) for line in lines)
        labels = [line.split("&")[0].strip() for line in lines]
        positions = [order.index(name) for name in labels]
        assert positions == sorted(positions)


def test_a_table_body_is_replaced_once_and_an_unknown_table_is_refused():
    block = "\\label{tab:a}\n\\midrule\n{}\n\\bottomrule"
    tex = block.format("old") + "\n" + block.format("keep")
    out = pt.replace_body(tex, "a", "new")
    assert out == block.format("new") + "\n" + block.format("keep")
    with pytest.raises(ValueError) as refused:
        pt.replace_body(tex, "b", "x")
    assert str(refused.value) == "table b not found"
