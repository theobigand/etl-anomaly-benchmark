import hashlib
import json
import runpy
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import verify_real  # noqa: E402

from etl_benchmark import config, datasets  # noqa: E402
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


def test_real_dataset_rejects_unknown_reference_field(tmp_path):
    csv = tmp_path / "present.csv"
    pd.DataFrame({"x": [1.0, 2.0], "Class": [0, 1]}).to_csv(csv, index=False)
    result = verify_real.inspect_dataset(
        DatasetSpec("toy", csv, "Class", 1), expected={"not_a_record_field": 1}
    )
    assert result["status"] == "FAIL"
    assert "unknown reference field" in result["reason"]


def test_real_verification_command_fails_closed_on_reference_errors(tmp_path, monkeypatch):
    csv = tmp_path / "present.csv"
    pd.DataFrame({"x": [1.0, 2.0], "Class": [0, 1]}).to_csv(csv, index=False)
    monkeypatch.setattr(verify_real, "DATASETS", {"toy": DatasetSpec("toy", csv, "Class", 1)})
    manifest = tmp_path / "manifest.json"
    output = tmp_path / "report.json"
    monkeypatch.setattr(verify_real, "MANIFEST", manifest)
    monkeypatch.setattr(sys, "argv", ["verify_real", "--output", str(output)])

    assert verify_real.main() == 1
    assert json.loads(output.read_text())["datasets"][0]["status"] == "FAIL"

    manifest.write_text(json.dumps({"datasets": {"toy": {"sha256": "wrong"}}}))
    assert verify_real.main() == 1
    assert "reference missing" in json.loads(output.read_text())["datasets"][0]["reason"]

    expected = {
        "sha256": hashlib.sha256(csv.read_bytes()).hexdigest(),
        "raw_rows": 2,
        "rows_after_transform": 2,
        "anomalies": 1,
        "positive_value": 1,
    }
    manifest.write_text(json.dumps({"datasets": {"toy": expected}}))
    assert verify_real.main() == 0
    assert json.loads(output.read_text())["datasets"][0]["status"] == "PASS"

    csv.write_text("x,Class\n1,0\n2,0\n")
    assert verify_real.main() == 1
    assert json.loads(output.read_text())["datasets"][0]["status"] == "FAIL"


def test_real_verification_module_entrypoint_uses_local_reference(tmp_path, monkeypatch):
    csv = tmp_path / "toy.csv"
    pd.DataFrame({"measure": [1.0, 2.0], "Class": [0, 1]}).to_csv(csv, index=False)
    spec = DatasetSpec("toy", csv, "Class", 1)
    reference = {
        "sha256": hashlib.sha256(csv.read_bytes()).hexdigest(),
        "raw_rows": 2,
        "rows_after_transform": 2,
        "anomalies": 1,
        "positive_value": 1,
    }
    manifest = tmp_path / "verification/evidence/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"datasets": {"toy": reference}}))
    output = tmp_path / "real.json"
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(datasets, "DATASETS", {"toy": spec})
    monkeypatch.setattr(sys, "argv", ["verify_real", "--output", str(output)])
    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(Path(verify_real.__file__)), run_name="__main__")
    assert stopped.value.code == 0
    assert json.loads(output.read_text())["datasets"][0]["status"] == "PASS"
