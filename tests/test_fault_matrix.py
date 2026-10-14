"""Deliberate scientific defects, each applied to a throw-away copy of the code.

For every defect the targeted tests run in a subprocess on the modified copy;
at least one expected test must fail there while the same tests pass on an
unmodified copy. Nothing in the repository is touched. The tests are slow
(each starts a pytest session) and run with ``make verify-faults``, not FAST.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.fault

ROOT = Path(__file__).resolve().parents[1]
COPIED = ("src", "experiments", "tests", "pyproject.toml", "environment.yml")


@dataclass(frozen=True)
class Fault:
    name: str
    description: str
    path: str
    old: str
    new: str
    test_files: tuple[str, ...]
    expected: tuple[str, ...]


FAULTS = [
    Fault(
        "fit_on_evaluation_data",
        "the ML scaler and imputer are refitted on the rows being scored",
        "src/etl_benchmark/quality/ml.py",
        "        return self._scaler.transform(self._imputer.transform(x))",
        "        return StandardScaler().fit_transform(\n"
        '            SimpleImputer(strategy="median").fit_transform(x)\n'
        "        )",
        ("tests/test_detector_protocol.py", "tests/test_detector_contracts.py"),
        ("test_a_rows_score_does_not_depend_on_the_rest_of_the_evaluated_batch",),
    ),
    Fault(
        "fit_ignores_training_frame",
        "the detector is fitted on the evaluated rows instead of the training frame",
        "src/etl_benchmark/pipeline.py",
        "    detector.fit(fit_features)",
        "    detector.fit(features)",
        ("tests/test_detector_protocol.py",),
        ("test_held_out_values_do_not_affect_fitted_rule_statistics",),
    ),
    Fault(
        "label_as_feature",
        "the ground-truth column is passed to the detector as a feature",
        "src/etl_benchmark/pipeline.py",
        "    return df.drop(columns=[label_column]) if label_column in df.columns else df",
        "    return df",
        ("tests/test_pipeline.py",),
        ("test_detect_excludes_label_from_features",),
    ),
    Fault(
        "test_labels_set_contamination",
        "the detector threshold is read from the held-out labels",
        "experiments/run_benchmark.py",
        "        train[ANOMALY_COLUMN], policy=calibration, fixed=fixed_contamination",
        "        test[ANOMALY_COLUMN], policy=calibration, fixed=fixed_contamination",
        ("tests/test_run_benchmark.py",),
        (
            "test_calibration_uses_train_only_and_ignores_fit_sample",
            "test_test_labels_cannot_change_detector_calibration",
        ),
    ),
    Fault(
        "train_test_overlap",
        "five training rows are copied into the held-out partition",
        "src/etl_benchmark/split.py",
        "        test_df.reset_index(drop=True),\n    )\n\n\ndef chronological_split",
        "        pd.concat([test_df, train_df.head(5)]).reset_index(drop=True),\n    )\n\n\n"
        "def chronological_split",
        ("tests/test_split.py",),
        ("test_split_is_a_partition", "test_split_sizes_match_ratios"),
    ),
    Fault(
        "customer_copies_cross_partitions",
        "synthetic rows are split one by one, so a copied customer can span train and test",
        "experiments/run_synthetic_benchmark.py",
        '    group_parts = stratified_split(groups, "stratum", config.SPLIT_RATIOS, seed)\n'
        "    return tuple(\n"
        '        df[df["customer_id"].isin(group_part["customer_id"])].reset_index(drop=True)\n'
        "        for group_part in group_parts\n"
        "    )",
        "    rows = df.reset_index(drop=True)\n"
        '    return stratified_split(rows, "anomaly_type", config.SPLIT_RATIOS, seed)',
        ("tests/test_scientific_contracts.py",),
        ("test_synthetic_groups_never_cross_partitions",),
    ),
    Fault(
        "wrong_positive_class",
        "the anomaly flag marks every row except the declared positive class",
        "src/etl_benchmark/datasets.py",
        "(df[self.label_column] == self.positive_value)",
        "(df[self.label_column] != self.positive_value)",
        ("tests/test_datasets.py", "tests/test_dataset_contract.py"),
        ("test_features_drops_label_and_anomaly_columns",),
    ),
    Fault(
        "binary_flags_as_scores",
        "the pipeline hands the 0/1 flags to the metrics instead of the detector scores",
        "src/etl_benchmark/pipeline.py",
        "    scores = detector.score(features)",
        "    scores = detector.predict(features).astype(float)",
        ("tests/test_pipeline.py", "tests/test_pipeline_contracts.py"),
        ("test_detect_keeps_the_graded_scores_of_the_detector",),
    ),
    Fault(
        "inverted_score_orientation",
        "the z-score detector reports high values for normal rows",
        "src/etl_benchmark/quality/rules.py",
        "        return self._zscores(df).max(axis=1).fillna(0.0)",
        "        return -self._zscores(df).max(axis=1).fillna(0.0)",
        ("tests/test_zscore.py", "tests/test_detector_contracts.py"),
        ("test_zscore_uses_a_standard_deviation_of_exactly_one",),
    ),
    Fault(
        "per_type_denominator",
        "per-type precision counts every other anomaly type as a negative",
        "experiments/run_synthetic_benchmark.py",
        "        keep = is_type | clean",
        "        keep = is_type | ~is_type",
        ("tests/test_scientific_contracts.py",),
        ("test_per_type_golden_denominators",),
    ),
    Fault(
        "first_seed_only",
        "the seed aggregate reports the first seed instead of the mean",
        "experiments/run_benchmark.py",
        "    return grouped.mean(), grouped.std()",
        "    return grouped.first(), grouped.std()",
        ("tests/test_run_benchmark.py",),
        ("test_two_seed_mean_and_sample_standard_deviation",),
    ),
    Fault(
        "dropped_detector_run",
        "one detector silently disappears from the results table",
        "experiments/run_benchmark.py",
        "        rows.append(row)",
        '        if det.name != "iqr":\n            rows.append(row)',
        ("tests/test_run_benchmark.py",),
        ("test_every_requested_detector_appears_in_the_results",),
    ),
    Fault(
        "flags_as_pr_auc_input",
        "average precision is computed from the boolean flags, not the scores",
        "src/etl_benchmark/metrics.py",
        "average_precision_score(y, scores)",
        "average_precision_score(y, flags)",
        ("tests/test_metric_contract.py",),
        ("test_golden_metrics_use_continuous_scores",),
    ),
    Fault(
        "synthetic_calibration_on_test",
        "the synthetic benchmark sets contamination from the test partition",
        "experiments/run_synthetic_benchmark.py",
        '    contamination = float(train["anomaly"].mean())',
        '    contamination = float(test["anomaly"].mean())',
        ("tests/test_scientific_contracts.py", "tests/test_synthetic_benchmark.py"),
        ("test_synthetic_calibration_ignores_held_out_labels",),
    ),
]

_RESULTS: list[dict] = []


def _run(workdir: Path, files: tuple[str, ...]) -> tuple[int, set[str]]:
    env = {**os.environ, "PYTHONPATH": str(workdir / "src")}
    env.pop("COVERAGE_PROCESS_START", None)
    command = [sys.executable, "-m", "pytest", "-m", "not real and not fault", "-q", "-rf"]
    command += ["-p", "no:cacheprovider", "--no-header", *files]
    done = subprocess.run(
        command, cwd=workdir, env=env, capture_output=True, text=True, timeout=600, check=False
    )
    failed = set(re.findall(r"^FAILED \S+::(\w+)", done.stdout, flags=re.MULTILINE))
    return done.returncode, failed


def _copy(destination: Path) -> None:
    for name in COPIED:
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(
                source, destination / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
        else:
            shutil.copy2(source, destination / name)


@pytest.fixture(scope="module", autouse=True)
def _write_matrix():
    yield
    if not _RESULTS:
        return
    target = ROOT / "experiments" / "results" / "fault_matrix.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(_RESULTS, indent=2, ensure_ascii=False) + "\n")


@pytest.mark.parametrize("fault", FAULTS, ids=lambda fault: fault.name)
def test_deliberate_defect_is_caught(fault, tmp_path):
    clean = tmp_path / "clean"
    broken = tmp_path / "broken"
    clean.mkdir()
    broken.mkdir()
    _copy(clean)
    _copy(broken)

    target = broken / fault.path
    text = target.read_text()
    assert text.count(fault.old) == 1, f"anchor for {fault.name} must match exactly once"
    target.write_text(text.replace(fault.old, fault.new))

    control_code, control_failed = _run(clean, fault.test_files)
    code, failed = _run(broken, fault.test_files)
    detected = sorted(failed & set(fault.expected))
    _RESULTS.append(
        {
            "defect": fault.name,
            "description": fault.description,
            "expected": list(fault.expected),
            "observed_failures": sorted(failed),
            "caught_by_expected_test": bool(detected),
        }
    )
    assert control_code == 0 and not control_failed, "the unmodified copy must pass"
    assert code != 0, f"{fault.name}: the defect went unnoticed"
    assert detected, f"{fault.name}: failed {sorted(failed)}, expected one of {fault.expected}"
