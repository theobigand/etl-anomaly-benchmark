"""The coverage matrix of a small synthetic evidence tree equals the hand-checked snapshot.

The snapshot in tests/golden/coverage was generated once and reviewed by hand: every status,
reason, decision and count was compared with the fixture. Regenerate it only after reviewing a
deliberate behaviour change (run ``coverage_matrix.main`` on ``coverage_fixture.build``).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import coverage_fixture as cf  # noqa: E402
import coverage_matrix as cm  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden" / "coverage"


def produce(tmp_path: Path) -> Path:
    """Run in each test, not in a shared fixture, so a mutation is attributed to every test."""
    root = cf.build(tmp_path / "evidence")
    out = tmp_path / "out"
    assert cm.main(["--evidence", str(root), "--out", str(out)]) == 0
    return out


@pytest.mark.parametrize(
    "name", ["coverage_matrix.json", "coverage_matrix.md", "dataset_inventory.csv"]
)
def test_generated_files_equal_the_reviewed_snapshot(tmp_path, name):
    assert (produce(tmp_path) / name).read_text() == (GOLDEN / name).read_text()


def test_a_partly_failed_run_without_a_later_rerun_is_not_called_repaired(tmp_path):
    cells = cm.build(cf.build(tmp_path))["datasets"]
    by_id = {d["id"]: d for d in cells}
    etl = by_id["uci:146"]["protocols"]["etl_pipeline"]
    assert etl["status"] == cm.OK and "repaired_from" not in etl
    assert etl["methods_failed"] == {"isolation_forest": "boom"}
    repaired = by_id["uci:3"]["protocols"]["etl_pipeline"]
    assert repaired["repaired_from"] == "all-missing" and repaired["run"].startswith(
        "pool_extension_v2"
    )
    assert by_id["uci:357"]["protocols"]["etl_pipeline"]["status"] == cm.FAILED
