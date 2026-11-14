"""Canonical production sources must not escape the prospective classification."""

import json
from pathlib import Path

from verification.mutation_policy import validate_policy

ROOT = Path(__file__).resolve().parents[1]


def test_actual_production_inventory_has_no_missing_or_stale_classifications():
    policy = json.loads((ROOT / "verification/mutation_risk_policy.json").read_text())
    assert set(policy["roots"]) == {"src/etl_benchmark", "experiments", "research", "verification"}
    validate_policy(policy, ROOT)


def test_critical_label_metric_and_evidence_controls_are_not_downgraded():
    policy = json.loads((ROOT / "verification/mutation_risk_policy.json").read_text())
    for name in [
        "src/etl_benchmark/split.py",
        "src/etl_benchmark/metrics.py",
        "research/pool_preprocessing.py",
        "research/pool_train_only.py",
        "verification/mutation_policy.py",
        "verification/mutation_catalog.py",
        "verification/evidence_schema.py",
        "verification/release.py",
    ]:
        assert policy["units"][name]["level"] == "L4", name
