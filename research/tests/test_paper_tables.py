"""The benchmark tables of the paper are the rows written from the archived results."""

import json
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
    assert f"== labelled\n{pt.pool_rows()}" in out
    assert f"== examples\n{pt.example_rows()}" in out
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
    def block(body):
        return "\\label{tab:a}\n\\midrule\n" + body + "\n\\bottomrule"

    tex = block("old") + "\n" + block("keep")
    out = pt.replace_body(tex, "a", "new")
    assert out == block("new") + "\n" + block("keep")
    with pytest.raises(ValueError) as refused:
        pt.replace_body(tex, "b", "x")
    assert str(refused.value) == "table b not found"


def _evidence_with_timing(tmp_path, times):
    (tmp_path / "full_registry").mkdir()
    shutil.copy(pt.EVIDENCE / "benchmark_credit_card.csv", tmp_path)
    shutil.copy(pt.EVIDENCE / "full_registry" / "real_credit_card.json", tmp_path / "full_registry")
    if times is not None:
        (tmp_path / "neural_timing").mkdir()
        mean = {"credit_card": dict.fromkeys(pt.NEURAL, times)}
        (tmp_path / "neural_timing" / "neural_times.json").write_text(
            json.dumps({"mean_detect_s": mean})
        )
    return tmp_path


def test_neural_times_come_from_the_separate_run_are_footnoted_and_never_ranked(tmp_path):
    lines = pt.rows("fraud", _evidence_with_timing(tmp_path, 0.001)).split("\n")
    neural = [line for line in lines if line.split("&")[0].strip() in pt.NAMES.values()][-6:]
    assert [line.split("&")[-1].strip() for line in neural] == [r"0.00$^{c}$ \\"] * 6
    assert not any("textbf" in line.split("&")[-1] for line in neural)
    zscore = next(line for line in lines if line.startswith("Z-score"))
    assert zscore.split("&")[-1].strip() == r"\textbf{0.03} \\"  # fastest of the classical rows


def test_without_a_timing_run_the_neural_time_cells_stay_empty(tmp_path):
    lines = pt.rows("fraud", _evidence_with_timing(tmp_path, None)).split("\n")
    neural = [line for line in lines if line.split("&")[0].strip() in pt.NAMES.values()][-6:]
    assert [line.split("&")[-1].strip() for line in neural] == [r"-- \\"] * 6


def test_cost_table_in_the_manuscript_equals_the_rows_of_the_cost_archives():
    tex = TEX.read_text()
    assert pt.replace_body(tex, "cost", pt.cost_rows()) == tex


def test_significant_figures_and_memory_unit_of_the_cost_rows():
    assert pt.sig(0.002022, 3) == "0.00202" and pt.sig(133.088, 3) == "133"
    assert pt.sig(18.031, 3) == "18.0" and pt.sig(3.2034, 3) == "3.20" and pt.sig(0.0129, 3) == "0.0129"
    rows = {line.split("&")[0].strip(): line for line in pt.cost_rows().split("\n") if "&" in line}
    zscore = [cell.strip() for cell in rows["Z-score"].rstrip(" \\").split("&")]
    assert zscore == ["Z-score", "0.00202 s", "0.0126 s", "0.0391 s", "0.64", "67"]  # MiB


def _summary(sizes, largest, failures):
    points = {
        str(n): {"detect_s_median": float(n) / 1000, "rss_delta_bytes_median": 2.0**20 * 10}
        for n in sizes
    }
    return {"points": points, "growth_exponent": 1.0, "largest_measured": largest, "failures": failures}


def _cells(row):
    return [c.strip() for c in row.rstrip(" \\").split("&")]


def test_a_size_past_a_timeout_is_over_budget_and_the_following_ones_were_not_run():
    summary = _summary((1_000, 3_000, 10_000, 30_000), 30_000, {"TIMEOUT": 1, "SKIPPED": 1})
    cells = _cells(pt.cost_row("X", summary))
    assert cells[1:4] == ["10.0 s", "$>300$ s", "not run"] and cells[5] == "10$^{a}$"
    summary = _summary((10_000, 30_000, 100_000), 100_000, {"TIMEOUT": 1})
    cells = _cells(pt.cost_row("Y", summary))
    assert cells[1:4] == ["10.0 s", "100 s", "$>300$ s"] and cells[5] == "10$^{b}$"
    summary = _summary((10_000, 100_000, 300_000), 300_000, {})
    assert _cells(pt.cost_row("Z", summary))[1:] == ["10.0 s", "100 s", "300 s", "1.00", "10"]


@pytest.mark.parametrize(
    "label,rows",
    [
        ("contamination", "contamination_rows"),
        ("fixed-calibration", "fixed_rows"),
        ("clustered", "clustered_rows"),
    ],
)
def test_the_remaining_measured_tables_equal_the_rows_of_their_archives(label, rows):
    tex = TEX.read_text()
    assert pt.replace_body(tex, label, getattr(pt, rows)()) == tex


def test_the_command_also_rewrites_the_pilot_table_from_its_archive(tmp_path):
    copy = tmp_path / "main.tex"
    shutil.copy(TEX, copy)
    assert pt.main(["--tex", str(copy)]) == 0
    assert pt.chrono_rows() in copy.read_text()


def test_contamination_cells_follow_one_format_for_every_row():
    rows = pt.contamination_rows().split("\n")
    assert rows[0].split("&")[1].strip() == "0.001" and rows[1].split("&")[1].strip() == "0.10"
    assert any(r"prev.\ 0.5 " in r for r in rows) and "midrule" in "".join(rows)
    assert pt.pct(0.101) == "0.10" and pt.pct(10.204) == "10.2" and pt.pct(0.9999) == "1.0"


def test_signed_intervals_use_an_explicit_plus_and_the_holm_value_has_three_decimals():
    assert pt.signed(0.0162) == "+0.016" and pt.signed(-0.035) == "-0.035" and pt.signed(0.0) == "+0.000"
    first = pt.clustered_rows().split("\n")[0].split("&")
    assert first[0].strip() == r"ECOD $-$ Isolation Forest" and first[-1].strip() == r"1.000 \\"


def test_percentages_round_at_two_decimals_before_choosing_the_format():
    assert pt.pct(0.6) == "0.60" and pt.pct(0.996) == "1.0" and pt.pct(0.994) == "0.99" and pt.pct(12.34) == "12.3"


def test_zero_has_no_decimals_and_one_keeps_its_significant_figures():
    assert pt.sig(0, 3) == "0" and pt.sig(1, 3) == "1.00" and pt.sig(-0.5, 2) == "-0.50"


def test_the_fixed_contamination_rows_name_each_dataset():
    labels = [line.split("&")[0].strip() for line in pt.fixed_rows().split("\n")]
    assert labels == ["Credit Card Fraud", "Cardio", "Water Quality"]


def test_the_command_help_starts_with_the_module_description(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "300")
    with pytest.raises(SystemExit):
        pt.main(["--help"])
    assert "LaTeX rows of the four benchmark tables of the paper" in " ".join(capsys.readouterr().out.split())
