"""Coverage matrix: a dataset counts as evaluated only when a result holds a measurement."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import coverage_matrix as cm  # noqa: E402


def test_adbench_twins_share_the_independent_source_of_their_uci_original():
    assert cm.source_key("adbench:satellite") == cm.source_key("adbench:landsat") == "uci:146"
    assert cm.source_key("uci:146") == "uci:146"
    assert cm.source_key("adbench:fraud") == "adbench:fraud"


def test_missing_detector_scores_are_absent_not_zero():
    runs = {
        "a": [{"metrics": {"pr_auc": 0.5}}, {"metrics": {"pr_auc": 0.3}}],
        "b": [{"metrics": {}}],
    }
    assert cm._mean_metric(runs, "pr_auc") == {"a": 0.4}


def test_absent_cells_carry_a_status_and_a_reason():
    row = {"has_labels": False, "time_candidates": []}
    cell = cm._absent(
        "typed_injection_classical",
        row,
        {"eligible": False, "reason": "only 0 continuous columns"},
        {},
    )
    assert cell["status"] == cm.UNSUITABLE and "continuous" in cell["reason"]
    assert cm._absent("chronological", row, None, {})["status"] == cm.UNSUITABLE
    assert (
        cm._absent("labelled_deep", row, None, {"label_refused": "fewer than 2 classes"})["status"]
        == cm.UNSUITABLE
    )


def test_summary_separates_timing_only_datasets_from_detector_quality_evidence():
    def ds(i, ok):
        return {
            "id": i,
            "source_family": "uci",
            "has_labels": False,
            "independent_source": i,
            "valid_measurements": ok,
            "protocols": {
                p: {"status": cm.OK if p in ok else cm.NOT_EVALUATED} for p in cm.PROTOCOLS
            },
        }

    s = cm.summarise(
        [
            ds("uci:1", ["etl_pipeline"]),
            ds("uci:2", ["etl_pipeline", "labelled_classical"]),
            ds("uci:3", []),
        ]
    )
    assert s["with_any_valid_measurement"] == 2
    assert s["with_detector_quality_measurement"] == 1
    assert s["etl_pipeline_only_ids"] == ["uci:1"]
    assert s["without_detector_quality_measurement"] == ["uci:1", "uci:3"]


def test_archived_evidence_yields_one_row_per_catalog_dataset():
    matrix = cm.build()
    assert len(matrix["datasets"]) == 152
    assert all(set(d["protocols"]) == set(cm.PROTOCOLS) for d in matrix["datasets"])
    assert all(
        c["status"] in cm.STATUSES for d in matrix["datasets"] for c in d["protocols"].values()
    )
