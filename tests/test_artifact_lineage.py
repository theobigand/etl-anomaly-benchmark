import hashlib
import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.end_to_end


def test_archived_tables_and_figures_match_manifest():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "verification/evidence/manifest.json").read_text())
    assert manifest["datasets"]
    assert manifest["artifacts"]
    for name, expected in manifest["artifacts"].items():
        artifact = root / name
        assert artifact.is_file(), name
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == expected, name


def test_archived_runs_match_current_scientific_source():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "experiments"))
    from provenance import _source_fingerprint

    current = _source_fingerprint()
    for name in (
        "run_synthetic",
        "run_severity",
        "run_curves",
        "run_benchmark_credit_card",
        "run_benchmark_water_quality",
        "run_benchmark_cardio",
    ):
        record = json.loads((root / "verification/evidence" / f"{name}.json").read_text())
        assert record["source_fingerprint"] == current, name
