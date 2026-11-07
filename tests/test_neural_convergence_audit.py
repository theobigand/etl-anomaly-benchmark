"""The convergence limitation must remain explicit in the remediation record."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_neural_convergence_audit_covers_all_comparable_neural_detectors():
    text = (ROOT / "docs/thesis-remediation/NEURAL_CONVERGENCE_AUDIT_2026-11-07.md").read_text()

    for name in ("`autoencoder`", "`vae`", "`deep_svdd`", "`dif`", "`ae1svm`", "`lunar`"):
        assert name in text
    assert "ne conservent pas leurs réglages effectifs" in text
    assert "ne présente plus ce constat comme une preuve de convergence" in text


def test_archived_neural_runs_distinguish_empty_errors_from_convergence_data():
    full = sorted((ROOT / "verification/evidence/full_registry/pool_deep/runs").glob("*.json"))
    extension = sorted(
        (ROOT / "verification/evidence/pool_extension/pool_full_deep/runs").glob("*.json")
    )
    assert len(full) == len(extension) == 100

    assert all(json.loads(path.read_text())["errors"] == {} for path in full)
    payloads = [json.loads(path.read_text()) for path in extension]
    assert all(payload["errors"] == {} for payload in payloads)
    runs = [row for payload in payloads for rows in payload["runs"].values() for row in rows]
    assert len(runs) == 3_000
    assert all("error" not in row and "settings" not in row for row in runs)
