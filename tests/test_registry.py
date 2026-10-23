import pytest

from etl_benchmark import config, registry
from etl_benchmark.quality import Detector
from etl_benchmark.registry import (
    ALL_NAMES,
    DEEP_NAMES,
    DETECTOR_NAMES,
    ML_NAMES,
    RULE_NAMES,
    all_detectors,
    clip_contamination,
    get_detector,
)


def test_get_detector_returns_named_instance():
    for name in DETECTOR_NAMES:
        det = get_detector(name)
        assert isinstance(det, Detector)
        assert det.name == name


def test_get_detector_unknown_raises():
    with pytest.raises(ValueError, match="unknown detector 'does_not_exist'; choose from"):
        get_detector("does_not_exist")


def test_all_detectors_covers_registry():
    assert {d.name for d in all_detectors()} == set(DETECTOR_NAMES)
    assert set(RULE_NAMES) | set(ML_NAMES) == set(DETECTOR_NAMES)


def test_drift_is_opt_in_not_in_the_default_sweep():
    assert "drift" not in DETECTOR_NAMES
    assert ALL_NAMES[-1] == "drift"
    assert ALL_NAMES[:-1] == DETECTOR_NAMES
    assert get_detector("drift").name == "drift"


def test_all_detectors_can_select_a_subset():
    dets = all_detectors(names=RULE_NAMES)
    assert [d.name for d in dets] == RULE_NAMES


def test_ml_contamination_flows_to_ml_detectors_only():
    dets = {d.name: d for d in all_detectors(ml_contamination=0.02)}
    for name in ML_NAMES:
        assert dets[name].contamination == 0.02
    # rule-based detectors have no contamination attribute
    assert not hasattr(dets["zscore"], "contamination")


def test_clip_contamination_stays_in_pyod_bounds():
    lo, hi = config.ML_CONTAMINATION_BOUNDS
    assert clip_contamination(0.0) == lo
    assert clip_contamination(0.9) == hi
    assert clip_contamination(1.0) == hi
    assert clip_contamination(None) == config.ML_CONTAMINATION
    assert clip_contamination(0.017) == pytest.approx(0.017)


def test_fixed_calibration_does_not_use_training_labels():
    assert registry.calibrate_contamination([0, 1, 1, 1], policy="fixed", fixed=0.02) == 0.02
    assert registry.calibrate_contamination([0, 0, 0, 1], policy="fixed", fixed=0.02) == 0.02
    assert registry.calibrate_contamination([0, 1, 1, 1], policy="train_prevalence") == 0.5


def test_calibration_defaults_to_the_training_prevalence():
    assert registry.calibrate_contamination([0, 0, 0, 1, 0, 0, 0, 0]) == 0.125


def test_fixed_calibration_accepts_both_ends_of_the_allowed_range():
    lo, hi = config.ML_CONTAMINATION_BOUNDS
    assert registry.calibrate_contamination([0, 1], policy="fixed", fixed=lo) == lo
    assert registry.calibrate_contamination([0, 1], policy="fixed", fixed=hi) == hi


@pytest.mark.parametrize("value", [None, 0, -0.1, 0.9, float("nan")])
def test_fixed_calibration_rejects_missing_or_out_of_range_value(value):
    with pytest.raises(ValueError, match="fixed contamination"):
        registry.calibrate_contamination([0, 1], policy="fixed", fixed=value)


@pytest.mark.parametrize("labels", [[], [2], [0, float("nan")]])
def test_train_prevalence_rejects_empty_or_nonbinary_labels(labels):
    with pytest.raises(ValueError, match="^training labels must be nonempty and binary$"):
        registry.calibrate_contamination(labels, policy="train_prevalence")


def test_calibration_rejects_unknown_policy():
    with pytest.raises(ValueError, match="unknown calibration policy"):
        registry.calibrate_contamination([0, 1], policy="test_prevalence")


@pytest.mark.parametrize("prevalence", [-0.1, 1.1, float("nan"), float("inf")])
def test_clip_contamination_rejects_invalid_prevalence(prevalence):
    with pytest.raises(ValueError, match="^prevalence must be finite and between 0 and 1$"):
        clip_contamination(prevalence)


def test_a_fixed_contamination_is_validated_without_any_labels():
    lo, hi = config.ML_CONTAMINATION_BOUNDS
    assert registry.fixed_contamination(0.02) == 0.02
    assert registry.fixed_contamination(lo) == lo and registry.fixed_contamination(hi) == hi
    for bad in (None, float("nan"), float("inf"), lo / 2, hi * 2):
        with pytest.raises(
            ValueError, match=f"^fixed contamination must be between {lo} and {hi}$"
        ):
            registry.fixed_contamination(bad)


def test_the_registry_lists_the_classical_and_deep_families():
    assert ML_NAMES == [
        "isolation_forest",
        "lof",
        "ocsvm",
        "ecod",
        "copod",
        "hbos",
        "knn",
        "pca",
    ]
    assert DEEP_NAMES == ["autoencoder", "vae", "deep_svdd", "dif", "ae1svm", "lunar"]
    assert not set(DEEP_NAMES) & set(ALL_NAMES)


def test_every_registered_name_builds_a_detector_with_that_name():
    for name in [*ALL_NAMES, *DEEP_NAMES]:
        assert get_detector(name).name == name


def test_the_error_for_an_unknown_name_lists_the_deep_detectors_too():
    with pytest.raises(ValueError, match="vae"):
        get_detector("nope")
