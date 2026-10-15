"""Exact outputs of the small verification scripts (mutation gate and real-data check)."""

import hashlib
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import check_mutation  # noqa: E402
import verify_real  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.datasets import DatasetSpec  # noqa: E402


def _message(text):
    return f"^{re.escape(text)}$"


def _outcomes(**counts):
    result = {key: 0 for key in check_mutation.OUTCOMES}
    result.update(counts)
    return result


def test_mutation_gate_names_the_failed_contract():
    with pytest.raises(ValueError, match=_message("missing mutation outcomes")):
        check_mutation.classify({})
    with pytest.raises(ValueError, match=_message("missing mutation outcomes")):
        check_mutation.classify({"killed": 1})
    with pytest.raises(ValueError, match=_message("incomplete or inconsistent mutation outcomes")):
        check_mutation.classify(_outcomes(total=2, killed=1))


def test_a_single_killed_mutant_is_a_complete_campaign():
    assert check_mutation.classify(_outcomes(total=1, killed=1)) == ("PASS", 100.0)


def test_mutation_gate_prints_status_and_score(tmp_path, monkeypatch, capsys):
    stats = tmp_path / "mutation.json"
    stats.write_text(json.dumps(_outcomes(total=40, killed=38, survived=2)))
    monkeypatch.setattr(sys, "argv", ["check_mutation", str(stats)])
    assert check_mutation.main() == 0
    assert capsys.readouterr().out == "mutation gate: PASS (95.00% killed)\n"


def test_mutation_gate_help_shows_its_purpose(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["check_mutation", "--help"])
    with pytest.raises(SystemExit):
        check_mutation.main()
    assert "Fail-closed interpretation of a mutation campaign." in capsys.readouterr().out


def _csv(tmp_path, frame=None):
    csv = tmp_path / "toy.csv"
    (
        frame if frame is not None else pd.DataFrame({"x": [1.0, 2.0, 2.0], "Class": [0, 1, 1]})
    ).to_csv(csv, index=False)
    return csv


def test_inspection_record_lists_every_field_of_a_present_dataset(tmp_path):
    csv = _csv(tmp_path)
    record = verify_real.inspect_dataset(DatasetSpec("toy", csv, "Class", 1))
    assert record == {
        "dataset": "toy",
        "status": "PASS",
        "path": str(csv),
        "sha256": hashlib.sha256(csv.read_bytes()).hexdigest(),
        "bytes": csv.stat().st_size,
        "raw_rows": 3,
        "rows_after_transform": 2,
        "deduplicated_rows": 1,
        "anomalies": 1,
        "positive_value": 1,
        "label_column": "Class",
        "features": ["x"],
        "missing_by_feature": {"x": 0},
    }


def test_inspection_counts_missing_values_per_feature(tmp_path):
    frame = pd.DataFrame({"x": [1.0, None, 3.0], "y": [None, None, 1.0], "Class": [0, 1, 0]})
    record = verify_real.inspect_dataset(DatasetSpec("toy", _csv(tmp_path, frame), "Class", 1))
    assert record["missing_by_feature"] == {"x": 1, "y": 2}


def test_absent_and_failing_datasets_keep_their_identity(tmp_path):
    absent = verify_real.inspect_dataset(DatasetSpec("gone", tmp_path / "gone.csv", "Class", 1))
    assert absent == {
        "dataset": "gone",
        "status": "NOT_RUN",
        "reason": "dataset file absent",
        "path": str(tmp_path / "gone.csv"),
    }
    csv = _csv(tmp_path)
    failed = verify_real.inspect_dataset(
        DatasetSpec("toy", csv, "Class", 1), expected={"raw_rows": 99}
    )
    assert failed == {
        "dataset": "toy",
        "status": "FAIL",
        "reason": "raw_rows differs from the reference",
        "path": str(csv),
    }


def test_checksum_mismatch_is_reported_as_a_checksum(tmp_path):
    result = verify_real.inspect_dataset(
        DatasetSpec("toy", _csv(tmp_path), "Class", 1), expected={"sha256": "0" * 64}
    )
    assert result["reason"] == "checksum differs from the reference"


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame({"x": [1.0, 2.0], "Class": [0, 0]}),
        pd.DataFrame({"Class": [0, 1]}),
        pd.DataFrame({"x": [], "Class": []}),
    ],
    ids=["one class", "no feature", "no rows"],
)
def test_unusable_datasets_fail_with_the_same_reason(tmp_path, frame):
    result = verify_real.inspect_dataset(DatasetSpec("toy", _csv(tmp_path, frame), "Class", 1))
    assert result["status"] == "FAIL"
    assert result["reason"] == "dataset must have rows, features and both label classes"


def _reference(csv, **changes):
    reference = {
        "sha256": hashlib.sha256(csv.read_bytes()).hexdigest(),
        "raw_rows": 3,
        "rows_after_transform": 2,
        "anomalies": 1,
        "positive_value": 1,
    }
    return {**reference, **changes}


def test_command_writes_a_stable_report_and_prints_one_line_per_dataset(
    tmp_path, monkeypatch, capsys
):
    csv = _csv(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"datasets": {"toy": _reference(csv)}}))
    output = tmp_path / "nested" / "deeper" / "report.json"
    monkeypatch.setattr(verify_real, "DATASETS", {"toy": DatasetSpec("toy", csv, "Class", 1)})
    monkeypatch.setattr(verify_real, "MANIFEST", manifest)
    monkeypatch.setattr(sys, "argv", ["verify_real", "--output", str(output)])
    assert verify_real.main() == 0
    assert capsys.readouterr().out == "toy: PASS\n"
    text = output.read_text()
    report = json.loads(text)
    assert text == json.dumps(report, indent=2, sort_keys=True) + "\n"
    captured = datetime.fromisoformat(report["captured_at"])
    assert captured.utcoffset() == timedelta(0)
    assert report["datasets"][0]["status"] == "PASS"


def test_command_compares_every_run_with_the_reference(tmp_path, monkeypatch):
    csv = _csv(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"datasets": {"toy": _reference(csv, anomalies=2)}}))
    output = tmp_path / "report.json"
    monkeypatch.setattr(verify_real, "DATASETS", {"toy": DatasetSpec("toy", csv, "Class", 1)})
    monkeypatch.setattr(verify_real, "MANIFEST", manifest)
    monkeypatch.setattr(sys, "argv", ["verify_real", "--output", str(output)])
    assert verify_real.main() == 1
    assert json.loads(output.read_text())["datasets"][0]["reason"] == (
        "anomalies differs from the reference"
    )


def test_command_defaults_to_the_results_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(verify_real, "DATASETS", {})
    monkeypatch.setattr(verify_real, "MANIFEST", tmp_path / "absent.json")
    monkeypatch.setattr(sys, "argv", ["verify_real"])
    assert verify_real.main() == 0
    assert [path.name for path in (tmp_path / "results").iterdir()] == ["real_verification.json"]


def test_command_help_shows_its_purpose(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["verify_real", "--help"])
    with pytest.raises(SystemExit):
        verify_real.main()
    assert "Inspect available real datasets" in capsys.readouterr().out
