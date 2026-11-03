"""Constructed defects must violate the train-only contracts in isolated copies."""

import pytest

from tests.test_fault_matrix import _copy, _run

pytestmark = pytest.mark.fault


@pytest.mark.parametrize(
    ("module", "before", "after", "test"),
    [
        (
            "pool_preprocessing.py",
            '    train = frame.iloc[partitions["train"]]',
            "    train = frame",
            "test_evaluation_values_cannot_change_fitted_schema_or_training_matrix",
        ),
        (
            "pool_preprocessing.py",
            "    scaler = StandardScaler().fit(matrix(train))",
            "    scaler = StandardScaler().fit(matrix(frame))",
            "test_evaluation_values_cannot_change_fitted_schema_or_training_matrix",
        ),
        (
            "pool_train_only.py",
            '    contamination = clip_contamination(float(y[partitions["train"]].mean()))',
            "    contamination = clip_contamination(float(y.mean()))",
            "test_evaluation_labels_change_only_metrics_not_fitting_scores_or_decisions",
        ),
    ],
    ids=["schema_reads_evaluation", "scaler_reads_evaluation", "threshold_reads_evaluation_labels"],
)
def test_train_only_guard_rejects_deliberate_scientific_defect(
    module, before, after, test, tmp_path
):
    clean, broken = tmp_path / "clean", tmp_path / "broken"
    clean.mkdir()
    broken.mkdir()
    _copy(clean)
    _copy(broken)
    selected = (f"tests/test_pool_preprocessing.py::{test}",)
    assert _run(clean, selected)[0] == 0
    target = broken / "research" / module
    source = target.read_text()
    assert source.count(before) == 1
    target.write_text(source.replace(before, after))
    status, failed = _run(broken, selected)
    assert status != 0 and test in failed, (module, status, failed)
