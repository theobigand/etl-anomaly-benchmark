"""Generated manuscript blocks quote the archived numbers exactly and fail on a missing one."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import coverage_paper as cp  # noqa: E402

PROTOCOLS = list(cp.PROTOCOL_LABEL)


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _evidence(tmp_path: Path, deep: bool = True) -> Path:
    by_protocol = {
        p: {
            "executed": 10 + i,
            "scientifically_unsuitable": 2 + i,
            "not_applicable": 3,
            "failed": 1,
        }
        for i, p in enumerate(PROTOCOLS)
    }
    matrix = {
        "summary": {
            "datasets": 150,
            "with_detector_quality_measurement": 140,
            "independent_sources_with_detector_quality_measurement": 111,
            "with_labels": 90,
            "decisions": {"retired": 2},
            "by_protocol": by_protocol,
        },
        "diversity": {
            "effective_sample": {"independent_sources": 120, "entries_in_multi_entry_sources": 33}
        },
    }
    mixed = {
        "datasets": 70,
        "sources": 66,
        "M1": {"mean": 0.8123},
        "M2": {
            "invalid_code": {"rules": 0.0812, "distance_density": 0.2912},
            "cross_column_swap": {"rules": 0.2512, "distance_density": 0.7712},
        },
        "M3": {"a": {"p_holm": 0.01}, "b": {"p_holm": 0.5}, "c": {"p_holm": 0.04}},
        "medians": [
            {"method": "knn", "type": "invalid_code", "median": 0.333},
            {"method": "knn", "type": "missing_value", "median": 0.1},
            {"method": "zscore", "type": "invalid_code", "median": 0.4},
            {"method": "zscore", "type": "missing_value", "median": 0.25},
        ],
    }
    chrono = {
        "C1_median_detector_fpr_difference": 0.0151,
        "C2_median_detector_recall_difference": -0.0149,
        "C3_mean_rank_correlation": 0.9712,
        "detectors": {
            "knn": {
                "fpr_median_difference": 0.1634,
                "fpr_ci": [0.052, 0.839],
                "recall_median_difference": -0.0791,
                "recall_ci": [-0.1, 0.235],
            }
        },
    }
    v2 = tmp_path / "pool_extension_v2"
    _write(tmp_path / "coverage" / "coverage_matrix.json", matrix)
    _write(v2 / "typed_mixed" / "summary_classical" / "summary.json", mixed)
    _write(v2 / "typed_mixed" / "summary_deep" / "summary.json", {})
    _write(v2 / "chrono_injected" / "summary_classical" / "summary.json", chrono)
    if deep:
        deep_summary = {
            "C1_median_detector_fpr_difference": 0.0589,
            "C3_mean_rank_correlation": 0.8812,
        }
        _write(v2 / "chrono_injected" / "summary_deep" / "summary.json", deep_summary)
    return tmp_path


def test_main_block_quotes_every_archived_number(tmp_path):
    text = cp.main_block(_evidence(tmp_path))
    assert "<<" not in text
    assert "A catalog of 150 tables" in text
    assert "comes from 120 independent sources, because 33 entries" in text
    assert "140 of 150 tables now have at least one" in text
    assert "from 111 sources; before the extensions below, 30 tables" in text
    assert "2 table (Student Academics Performance" in text
    assert "The labels of the 90 labelled problems" in text
    assert "makes 70 of them eligible, from 66 sources" in text
    assert "(mean rank correlation $0.81$" in text
    assert (
        "(median recall $0.08$ against $0.29$ for invalid codes and $0.25$ against $0.77$" in text
    )
    assert "(2 of 3 detectors differ after Holm correction" in text
    assert "false-positive difference is $+0.015$" in text
    assert "the recall difference is $-0.015$" in text
    assert "(rank correlation $0.97$)." in text
    assert "median false-positive difference of $+0.059$ and a rank correlation of $0.88$" in text
    assert "140 tables instead of 120 have" in text


def test_the_neural_sentence_is_left_out_while_the_neural_study_is_missing(tmp_path):
    text = cp.main_block(_evidence(tmp_path, deep=False))
    assert "neural detectors give" not in text
    assert "(rank correlation $0.97$). With the four" in text


def test_status_rows_count_executed_unsuitable_and_every_other_outcome():
    by = {p: {} for p in PROTOCOLS}
    by["labelled_classical"] = {
        "executed": 5,
        "scientifically_unsuitable": 2,
        "not_applicable": 3,
        "failed": 4,
    }
    rows = cp.status_rows(by).split("\n")
    assert rows[0] == "Labelled problems & 5 & 2 & 7 \\\\"
    assert rows[-1] == "End-to-end pipeline & 0 & 0 & 0 \\\\"
    assert len(rows) == len(PROTOCOLS)


def test_appendix_tables_list_detectors_and_types_in_the_fixed_order(tmp_path):
    text = cp.appendix_block(_evidence(tmp_path))
    assert "median recall over 66 independent sources" in text
    assert "\\begin{tabular}{lrr}\n\\toprule\nDetector & Missing & Inv. code \\\\" in text
    assert "knn & 0.10 & 0.33 \\\\\nzscore & 0.25 & 0.40 \\\\" in text
    assert "knn & $+0.163$ [+0.05, +0.84] & $-0.079$ [-0.10, +0.23] \\\\" in text


def test_fill_refuses_a_value_that_was_not_provided():
    assert cp.fill("a <<x>> b", {"x": 3}) == "a 3 b"
    with pytest.raises(KeyError):
        cp.fill("a <<y>>", {"x": 3})


def test_tex_escapes_underscore_ampersand_and_percent():
    assert cp._tex("a_b&c%d") == "a\\_b\\&c\\%d"


def test_blocks_are_inserted_after_their_anchor_and_replaced_in_place(tmp_path):
    evidence = _evidence(tmp_path / "ev")
    tex = tmp_path / "main.tex"
    tex.write_text(f"head\n{cp.ANCHOR}\nmid\n{cp.APP_ANCHOR}\ntail\n")
    cp.write(tex, evidence)
    once = tex.read_text()
    assert once.index(cp.ANCHOR) < once.index(cp.START) < once.index(cp.END) < once.index("\nmid\n")
    assert once.index(cp.APP_ANCHOR) < once.index(cp.APP_START) < once.index("\ntail\n")
    cp.write(tex, evidence)
    assert tex.read_text() == once
    assert once.count(cp.START) == 1 and once.count(cp.APP_START) == 1


def test_facts_load_the_five_archives_and_tolerate_a_missing_neural_chronology(tmp_path):
    evidence = _evidence(tmp_path, deep=False)
    f = cp.facts(evidence)
    assert set(f) == {"matrix", "mixed", "mixed_deep", "chrono", "chrono_deep"}
    assert f["chrono_deep"] is None and f["mixed_deep"] == {} and f["mixed"]["datasets"] == 70
    assert (
        f["matrix"]["summary"]["datasets"] == 150
        and f["chrono"]["C3_mean_rank_correlation"] == 0.9712
    )
    assert (
        cp.facts(_evidence(tmp_path / "again"))["chrono_deep"]["C3_mean_rank_correlation"] == 0.8812
    )


def test_counts_default_to_zero_retired_and_use_strict_holm_threshold(tmp_path):
    evidence = _evidence(tmp_path)
    path = evidence / "coverage" / "coverage_matrix.json"
    matrix = json.loads(path.read_text())
    del matrix["summary"]["decisions"]["retired"]
    path.write_text(json.dumps(matrix))
    mixed = evidence / "pool_extension_v2" / "typed_mixed" / "summary_classical" / "summary.json"
    summary = json.loads(mixed.read_text())
    summary["M3"] = {"a": {"p_holm": 0.05}, "b": {"p_holm": 0.0499}}
    mixed.write_text(json.dumps(summary))
    text = cp.main_block(evidence)
    assert "0 table (Student Academics Performance" in text
    assert "(1 of 2 detectors differ after Holm correction" in text


def test_appendix_rows_are_one_line_per_detector(tmp_path):
    evidence = _evidence(tmp_path)
    path = evidence / "pool_extension_v2" / "chrono_injected" / "summary_classical" / "summary.json"
    summary = json.loads(path.read_text())
    summary["detectors"]["zscore"] = dict(summary["detectors"]["knn"])
    path.write_text(json.dumps(summary))
    text = cp.appendix_block(evidence)
    lines = [ln for ln in text.splitlines() if ln.startswith(("knn &", "zscore &")) and "$" in ln]
    assert len(lines) == 2 and all(ln.endswith("\\\\") for ln in lines)
    assert lines[0].split(" & ")[0] == "knn" and lines[1].split(" & ")[0] == "zscore"
    assert text.index(lines[0]) < text.index(lines[1]) and "\n".join(lines) in text


def test_insert_replaces_only_the_first_block_and_keeps_later_text(tmp_path):
    marker_start, marker_end = "<S>\n", "<E>\n"
    body = f"a\n{marker_start}old1{marker_end}b\n{marker_start}old2{marker_end}c\n"
    out = cp._insert(body, "ANCHOR\n", marker_start, marker_end, "new\n")
    assert out == f"a\n{marker_start}new\n{marker_end}b\n{marker_start}old2{marker_end}c\n"
    fresh = "x\nANCHOR\ny\nANCHOR\nz\n"
    inserted = cp._insert(fresh, "ANCHOR\n", marker_start, marker_end, "new\n")
    assert inserted == f"x\nANCHOR\n\n{marker_start}new\n{marker_end}y\nANCHOR\nz\n"
    twice = f"{marker_start}one{marker_end}mid{marker_end}tail"
    assert cp._insert(twice, "ANCHOR\n", marker_start, marker_end, "N") == (
        f"{marker_start}N{marker_end}mid{marker_end}tail"
    )
