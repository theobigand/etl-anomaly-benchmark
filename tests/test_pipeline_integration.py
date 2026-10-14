import pandas as pd
import pytest

from etl_benchmark.pipeline import run_pipeline
from etl_benchmark.quality import ZScoreDetector

pytestmark = pytest.mark.integration


def test_pipeline_reads_deduplicates_and_persists_partition(tmp_path):
    csv = tmp_path / "input.csv"
    frame = pd.DataFrame(
        {"x": [float(i) for i in range(20)] + [100.0, 0.0], "Class": [0] * 20 + [1, 0]}
    )
    frame.to_csv(csv, index=False)
    output = tmp_path / "result"
    cleaned, result = run_pipeline(csv, ZScoreDetector(threshold=3), dump_dir=output)
    normal = pd.read_csv(output / "pipeline_clean.csv")
    anomalies = pd.read_csv(output / "pipeline_anomalies.csv")
    assert len(cleaned) == 21
    assert len(normal) + len(anomalies) == len(cleaned)
    assert sorted(pd.concat([normal, anomalies]).x) == sorted(cleaned.x)
    assert anomalies["x"].tolist() == [100.0]
    assert anomalies["Class"].tolist() == [1]
    assert result.detect_s >= 0


def test_pipeline_reports_missing_input_path(tmp_path):
    with pytest.raises(FileNotFoundError, match="Dataset not found"):
        run_pipeline(tmp_path / "absent.csv", ZScoreDetector())


def test_pipeline_can_return_results_without_writing_files(tmp_path):
    source = tmp_path / "input.csv"
    pd.DataFrame({"x": [0.0, 1.0, 2.0, 100.0], "Class": [0, 0, 0, 1]}).to_csv(source, index=False)
    cleaned, result = run_pipeline(source, ZScoreDetector(threshold=1), dump_dir=None)
    assert len(cleaned) == len(result.flags) == 4
    assert not list(tmp_path.glob("pipeline_*.csv"))


def test_unwritable_output_location_fails_loudly(tmp_path):
    source = tmp_path / "input.csv"
    pd.DataFrame({"x": [0.0, 1.0, 2.0, 100.0], "Class": [0, 0, 0, 1]}).to_csv(source, index=False)
    blocker = tmp_path / "occupied"
    blocker.write_text("a file where a directory is needed")
    with pytest.raises(OSError):
        run_pipeline(source, ZScoreDetector(threshold=1), dump_dir=blocker / "out")
    assert blocker.read_text() == "a file where a directory is needed"


def test_pipeline_does_not_write_when_the_detector_fails(tmp_path):
    source = tmp_path / "input.csv"
    pd.DataFrame({"x": [0.0, 1.0, 2.0], "Class": [0, 0, 1]}).to_csv(source, index=False)
    broken = pd.DataFrame({"name": ["a", "b", "c"]})
    broken.to_csv(source, index=False)
    with pytest.raises(ValueError, match="at least one numeric feature"):
        run_pipeline(source, ZScoreDetector(), dump_dir=tmp_path / "out")
    assert not (tmp_path / "out").exists()
