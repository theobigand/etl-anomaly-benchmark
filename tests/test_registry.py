import pytest

from etl_benchmark import config
from etl_benchmark.quality import Detector
from etl_benchmark.registry import (
    ALL_NAMES,
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
    with pytest.raises(ValueError):
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
    assert clip_contamination(None) == config.ML_CONTAMINATION
    assert clip_contamination(0.017) == pytest.approx(0.017)
