import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import verify_real  # noqa: E402

from etl_benchmark.datasets import DatasetSpec  # noqa: E402


def test_real_dataset_record_distinguishes_present_from_missing(tmp_path):
    csv = tmp_path / "present.csv"
    pd.DataFrame({"x": [1.0, 2.0], "Class": [0, 1]}).to_csv(csv, index=False)
    present = verify_real.inspect_dataset(DatasetSpec("toy", csv, "Class", 1))
    missing = verify_real.inspect_dataset(DatasetSpec("missing", tmp_path / "none.csv", "Class", 1))
    assert present["status"] == "PASS"
    assert present["raw_rows"] == 2
    assert present["anomalies"] == 1
    assert len(present["sha256"]) == 64
    assert missing["status"] == "NOT_RUN"
    assert "reason" in missing


def test_real_dataset_rejects_a_changed_source_file(tmp_path):
    csv = tmp_path / "present.csv"
    pd.DataFrame({"x": [1.0, 2.0], "Class": [0, 1]}).to_csv(csv, index=False)
    original = hashlib.sha256(csv.read_bytes()).hexdigest()
    spec = DatasetSpec("toy", csv, "Class", 1)
    assert verify_real.inspect_dataset(spec, expected={"sha256": original})["status"] == "PASS"
    pd.DataFrame({"x": [1.0, 9.0], "Class": [0, 1]}).to_csv(csv, index=False)
    changed = verify_real.inspect_dataset(spec, expected={"sha256": original})
    assert changed["status"] == "FAIL"
    assert "checksum" in changed["reason"]


def test_real_dataset_rejects_changed_population_or_positive_mapping(tmp_path):
    csv = tmp_path / "present.csv"
    pd.DataFrame({"x": [1.0, 2.0], "Class": [0, 1]}).to_csv(csv, index=False)
    spec = DatasetSpec("toy", csv, "Class", 1)
    changed = verify_real.inspect_dataset(
        spec, expected={"raw_rows": 3, "anomalies": 1, "positive_value": 1}
    )
    assert changed["status"] == "FAIL"
    assert "raw_rows" in changed["reason"]
    changed = verify_real.inspect_dataset(spec, expected={"positive_value": 0})
    assert changed["status"] == "FAIL"
    assert "positive_value" in changed["reason"]
