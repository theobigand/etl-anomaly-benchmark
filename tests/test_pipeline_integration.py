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
