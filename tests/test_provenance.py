import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import provenance  # noqa: E402


def test_record_binds_data_seed_protocol_and_outputs(tmp_path):
    dataset = tmp_path / "data.csv"
    dataset.write_text("x,label\n1,0\n2,1\n")
    output = tmp_path / "run.json"
    provenance.write_record(
        output,
        experiment="benchmark",
        seeds=[4, 5],
        dataset="toy",
        data_path=dataset,
        settings={"split": [0.7, 0.15, 0.15]},
        outputs=["metrics.csv"],
    )
    record = json.loads(output.read_text())
    assert record["seeds"] == [4, 5]
    assert record["dataset"]["sha256"] == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert record["settings"]["split"] == [0.7, 0.15, 0.15]
    assert record["outputs"] == ["metrics.csv"]
    assert record["source_revision"]
    assert record["python"]
